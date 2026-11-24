"""Project-level tests for the PostgreSQL database configuration (Phase 1).

Phase 1 removes SQLite from the code path and makes PostgreSQL the database in
every environment, resolved from ``DATABASE_URL``. These tests pin that claim
from three angles: the settings that load, the modules' source, and the
docker-compose service a fresh checkout depends on. Settings are evaluated once,
at import, so the scenarios that need a different environment start a fresh
interpreter, exactly as ``tests/test_production_settings.py`` does.
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connection

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Any non-empty key satisfies the settings module; django.setup() is all these
# probes need.
SECRET_KEY = 'pytest-database-config-key-9f3c1a7e5b2d8046c9f1a3e7'

# Prints the resolved default database connection as JSON.
_DUMP_DB = """
import json

import dotenv

# The test owns the environment. load_dotenv(override=False) would re-inject
# .env values for any key _db() cleared, so a developer's .env would silently
# stand in for the settings fallback. Disable it before settings import.
dotenv.load_dotenv = lambda *a, **k: None

import django

django.setup()
from django.conf import settings

db = settings.DATABASES["default"]
print("__DB__" + json.dumps({
    "ENGINE": db["ENGINE"],
    "NAME": db["NAME"],
    "USER": db.get("USER"),
    "HOST": db.get("HOST"),
    "PORT": str(db.get("PORT")),
    "OPTIONS": db.get("OPTIONS", {}),
}))
"""


def _db(**overrides):
    """Return the resolved default database for a fresh interpreter.

    Every environment variable the settings module reads is pinned first, so the
    result never depends on a developer's ``.env`` or shell. ``DATABASE_URL`` and
    ``STACK`` are cleared by default; each test opts back in to what it exercises.
    """
    env = os.environ.copy()
    env['DJANGO_SECRET_KEY'] = SECRET_KEY
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'
    env['DJANGO_DEBUG'] = 'True'
    env['DJANGO_ALLOWED_HOSTS'] = ''
    env.pop('STACK', None)
    env.pop('DATABASE_URL', None)
    env.update(overrides)

    result = subprocess.run(
        [sys.executable, '-c', _DUMP_DB],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    line = next(
        line for line in result.stdout.splitlines() if line.startswith('__DB__')
    )
    return json.loads(line[len('__DB__'):])


def test_loaded_settings_use_postgresql():
    """The suite's own DATABASES must be PostgreSQL, never SQLite."""
    assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'


def _code_strings(tree):
    """Yield string constants in a module tree, excluding docstrings.

    Prose ("no SQLite path") is fine; an executable reference to the SQLite
    backend is not. Comments are absent from the AST already, and docstrings are
    skipped here so documentation that names the thing we removed does not fail.
    """
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                yield node.value


def _sqlite_offenders(source: str) -> list[str]:
    """Return the ways this module reaches for SQLite, if any.

    Only code-path markers count: a ``.sqlite3`` string (the Django backend
    ``django.db.backends.sqlite3`` or a ``db.sqlite3`` filename), a ``sqlite://``
    URL (what ``dj-database-url`` would parse into that backend), and a direct
    ``sqlite3`` import. Prose that merely names SQLite does not.
    """
    tree = ast.parse(source)
    strings = list(_code_strings(tree))
    found = []
    if any('.sqlite3' in text for text in strings):
        found.append('sqlite backend or filename literal')
    if any('sqlite://' in text for text in strings):
        found.append('sqlite database URL')
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any('sqlite3' in alias.name.split('.') for alias in node.names):
                found.append('import sqlite3')
        elif isinstance(node, ast.ImportFrom):
            if node.module and 'sqlite3' in node.module.split('.'):
                found.append('from sqlite3 import ...')
    return found


def test_sqlite_detector_catches_backend_and_url_forms():
    """The scanner must not pass a real reintroduction. Every shape is covered.

    This is the guard on the guard: it proves ``test_no_python_source_references
    _sqlite`` would fail if SQLite came back via the Django backend name, a
    ``dj-database-url`` connection string, or an import of the backend module.
    """
    backend = "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3'}}"
    url = "DATABASE_URL = 'sqlite:///:memory:'"
    imp = 'import sqlite3'
    dotted_import = 'from django.db.backends.sqlite3 import DatabaseWrapper'

    assert _sqlite_offenders(backend) == ['sqlite backend or filename literal']
    assert _sqlite_offenders(url) == ['sqlite database URL']
    assert _sqlite_offenders(imp) == ['import sqlite3']
    assert _sqlite_offenders(dotted_import) == ['from sqlite3 import ...']
    # Prose alone is not a code path and must stay clean.
    assert _sqlite_offenders('"""No SQLite here."""\nx = 1') == []


def test_no_python_source_references_sqlite():
    """No module in the project may reach for SQLite (Phase 1 acceptance)."""
    this_file = Path(__file__).resolve()
    offenders = {}
    for path in PROJECT_ROOT.rglob('*.py'):
        # Skip virtualenvs and tooling caches; only project source is inspected.
        if any(part in {'.venv', 'll_env', 'venv', 'env', '__pycache__'} for part in path.parts):
            continue
        # This probe names the markers it searches for, so it always matches
        # itself; scanning it would be a false positive.
        if path.resolve() == this_file:
            continue
        found = _sqlite_offenders(path.read_text(encoding='utf-8'))
        if found:
            offenders[str(path.relative_to(PROJECT_ROOT))] = found
    assert offenders == {}, f'SQLite still referenced by: {offenders}'


def test_database_url_environment_variable_is_honoured():
    data = _db(DATABASE_URL='postgres://alice:s3cret@db.example.com:6543/proddb')

    assert data['ENGINE'] == 'django.db.backends.postgresql'
    assert data['NAME'] == 'proddb'
    assert data['USER'] == 'alice'
    assert data['HOST'] == 'db.example.com'
    assert data['PORT'] == '6543'


def test_unset_database_url_falls_back_to_the_compose_default():
    """A fresh checkout with no DATABASE_URL targets the docker-compose service."""
    data = _db()

    assert data['ENGINE'] == 'django.db.backends.postgresql'
    assert data['NAME'] == 'maarifa'
    assert data['USER'] == 'maarifa'
    assert data['HOST'] == '127.0.0.1'
    assert data['PORT'] == '5433'


def test_compose_service_matches_the_settings_default():
    """The compose service and the settings fallback must not drift apart.

    If they disagree, a fresh clone follows the README, starts a container, and
    still cannot connect. Keeping this invariant tested is the cheap fix.
    """
    compose = (PROJECT_ROOT / 'docker-compose.yml').read_text(encoding='utf-8')
    default = _db()

    port_match = re.search(r'\$\{POSTGRES_PORT:-(\d+)\}', compose)
    assert port_match, 'docker-compose.yml must publish a default POSTGRES_PORT'
    assert port_match.group(1) == default['PORT']

    db_match = re.search(r'^\s*POSTGRES_DB:\s*(\S+)', compose, re.MULTILINE)
    assert db_match, 'docker-compose.yml must set POSTGRES_DB'
    assert db_match.group(1) == default['NAME']

    user_match = re.search(r'^\s*POSTGRES_USER:\s*(\S+)', compose, re.MULTILINE)
    assert user_match, 'docker-compose.yml must set POSTGRES_USER'
    assert user_match.group(1) == default['USER']


def test_compose_uses_the_pgvector_image():
    compose = (PROJECT_ROOT / 'docker-compose.yml').read_text(encoding='utf-8')

    assert 'image: pgvector/pgvector:pg17' in compose
    assert 'healthcheck:' in compose, 'compose needs a healthcheck for CI readiness'


def test_init_script_enables_the_vector_extension():
    init_sql = (PROJECT_ROOT / 'docker' / 'postgres' / 'init.sql').read_text(encoding='utf-8')

    assert 'CREATE EXTENSION IF NOT EXISTS vector;' in init_sql


@pytest.mark.django_db
def test_pgvector_extension_is_available_where_supported():
    """The extension must be installable on the server running the suite.

    Plan Phase 1 asks for pgvector "where available", so a server without it is
    skipped rather than failed; a server that ships it must let us enable it.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        if cursor.fetchone() is None:
            pytest.skip('pgvector is not installed on this PostgreSQL server')

        cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cursor.fetchone() is not None
