"""Project-level tests for the production and deployment configuration.

Settings are evaluated once, at import, so the only honest way to test what
happens under ``DJANGO_DEBUG=False`` or ``STACK=scalingo-XX`` is to start a fresh
interpreter with that environment. Each test below does exactly that, which is
also what a real deploy does.

These cover the claims Phase 9 makes: production hardening resolves the deploy
checks, local development is unaffected, the Scalingo branch switches the
database and static handling, and the deploy files the platform needs are
present and correct.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANAGE = PROJECT_ROOT / 'manage.py'

# Must satisfy Django's deploy check: >= 50 characters, >= 5 unique characters.
STRONG_SECRET_KEY = 'pytest-deploy-check-key-9f3c1a7e5b2d8046c9f1a3e7b5d20846'

# Reads the settings that Phase 9 is responsible for and prints them as JSON.
_DUMP_SETTINGS = """
import json
import django

django.setup()
from django.conf import settings

payload = {
    "DEBUG": settings.DEBUG,
    "DB_ENGINE": settings.DATABASES["default"]["ENGINE"],
    "MIDDLEWARE": settings.MIDDLEWARE,
    "STATICFILES_BACKEND": settings.STORAGES["staticfiles"]["BACKEND"],
    "STATIC_ROOT": str(settings.STATIC_ROOT),
    "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
    "SECURE_SSL_REDIRECT": settings.SECURE_SSL_REDIRECT,
    "SESSION_COOKIE_SECURE": settings.SESSION_COOKIE_SECURE,
    "CSRF_COOKIE_SECURE": settings.CSRF_COOKIE_SECURE,
    "SECURE_HSTS_SECONDS": settings.SECURE_HSTS_SECONDS,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "SECURE_HSTS_PRELOAD": settings.SECURE_HSTS_PRELOAD,
    "SECURE_PROXY_SSL_HEADER": settings.SECURE_PROXY_SSL_HEADER,
}
print("__SETTINGS__" + json.dumps(payload))
"""


def _env(**overrides):
    """A copy of the current environment with every relevant variable pinned.

    ``ll_project.settings`` calls ``load_dotenv(BASE_DIR / '.env')``, and
    ``load_dotenv`` does not override a variable that is already set. Setting
    each Django variable here to a known value therefore shields the scenario
    from whatever a developer happens to have in ``.env`` (or their shell); the
    tests must not depend on a machine's local configuration. Each test then
    overrides only the variables it means to exercise.
    """
    env = os.environ.copy()
    env['DJANGO_SECRET_KEY'] = STRONG_SECRET_KEY
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'
    env['DJANGO_DEBUG'] = 'True'        # the deterministic local default
    env['DJANGO_ALLOWED_HOSTS'] = ''    # no ambient hosts; tests set what they need
    env.pop('STACK', None)
    env.pop('DATABASE_URL', None)
    env.update(overrides)
    return env


def _run(args, env):
    return subprocess.run(
        [sys.executable, str(MANAGE), *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _settings(**overrides):
    """Return the settings snapshot for a fresh interpreter with these vars."""
    result = subprocess.run(
        [sys.executable, '-c', _DUMP_SETTINGS],
        cwd=PROJECT_ROOT,
        env=_env(**overrides),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    marker = '__SETTINGS__'
    line = next(
        line for line in result.stdout.splitlines() if line.startswith(marker)
    )
    return json.loads(line[len(marker):])


def test_check_deploy_reports_no_warnings():
    """`manage.py check --deploy` must be clean with production environment vars.

    This is the regression test for the five warnings Phase 8 deferred:
    W004 (HSTS), W008 (SSL redirect), W012 (session cookie), W016 (CSRF cookie)
    and W018 (DEBUG).
    """
    env = _env(DJANGO_DEBUG='False', DJANGO_ALLOWED_HOSTS='example.com')
    result = _run(['check', '--deploy', '--fail-level', 'WARNING'], env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'no issues' in (result.stdout + result.stderr)


def test_debug_false_turns_on_production_hardening():
    data = _settings(DJANGO_DEBUG='False', DJANGO_ALLOWED_HOSTS='example.com')

    assert data['DEBUG'] is False
    assert data['SECURE_SSL_REDIRECT'] is True
    assert data['SESSION_COOKIE_SECURE'] is True
    assert data['CSRF_COOKIE_SECURE'] is True
    assert data['SECURE_HSTS_SECONDS'] >= 31536000
    assert data['SECURE_HSTS_INCLUDE_SUBDOMAINS'] is True
    assert data['SECURE_HSTS_PRELOAD'] is True
    # Lets Django trust the host proxy's forwarded scheme, so SSL redirect
    # does not loop.
    assert data['SECURE_PROXY_SSL_HEADER'] == ['HTTP_X_FORWARDED_PROTO', 'https']


def test_local_development_is_unaffected():
    """The hardening must not leak into the default DEBUG=True configuration."""
    data = _settings(DJANGO_DEBUG='True')

    assert data['DEBUG'] is True
    assert data['DB_ENGINE'] == 'django.db.backends.sqlite3'
    assert data['SECURE_SSL_REDIRECT'] is False
    assert data['SESSION_COOKIE_SECURE'] is False
    assert data['CSRF_COOKIE_SECURE'] is False
    assert data['SECURE_HSTS_SECONDS'] == 0
    assert 'whitenoise.middleware.WhiteNoiseMiddleware' not in data['MIDDLEWARE']


def test_scalingo_environment_switches_to_postgres_and_whitenoise():
    data = _settings(
        STACK='scalingo-26',
        DATABASE_URL='postgres://user:pw@host:5432/appdb',
    )

    assert data['DEBUG'] is False
    assert data['DB_ENGINE'] == 'django.db.backends.postgresql'
    assert 'whitenoise.middleware.WhiteNoiseMiddleware' in data['MIDDLEWARE']
    assert data['STATICFILES_BACKEND'] == (
        'whitenoise.storage.CompressedManifestStaticFilesStorage'
    )
    assert data['STATIC_ROOT'].endswith('staticfiles')
    # No DJANGO_ALLOWED_HOSTS configured, so the platform default applies.
    assert data['ALLOWED_HOSTS'] == ['*']


def test_scalingo_respects_an_explicit_allowed_hosts():
    data = _settings(
        STACK='scalingo-26',
        DATABASE_URL='postgres://user:pw@host:5432/appdb',
        DJANGO_ALLOWED_HOSTS='maarifa.osc-fr1.scalingo.io',
    )

    assert data['ALLOWED_HOSTS'] == ['maarifa.osc-fr1.scalingo.io']


def test_scalingo_deploy_files_are_present():
    procfile = (PROJECT_ROOT / 'Procfile').read_text()
    assert 'web: gunicorn ll_project.wsgi --log-file -' in procfile
    assert 'postdeploy: bash bin/post_deploy.sh' in procfile

    post_deploy = PROJECT_ROOT / 'bin' / 'post_deploy.sh'
    assert post_deploy.is_file()
    assert os.access(post_deploy, os.X_OK), 'bin/post_deploy.sh must be executable'
    assert 'manage.py migrate' in post_deploy.read_text()

    assert (PROJECT_ROOT / '.python-version').read_text().strip() == '3.14'


def test_deployment_dependencies_are_pinned():
    lines = (PROJECT_ROOT / 'requirements.txt').read_text().splitlines()
    for package in ('gunicorn', 'whitenoise', 'dj-database-url', 'psycopg[binary]'):
        assert any(line.startswith(package + '==') for line in lines), package
