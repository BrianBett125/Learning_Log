"""Project-level tests for the Redis cache configuration (Phase 2).

Phase 2 wires a single Redis as the cache, resolved from ``REDIS_URL``, with the
local service declared in docker-compose.yml. These tests pin the claim from
three angles, the same way ``tests/test_database_config.py`` does for PostgreSQL:
the settings that actually load, the URL being honoured, and the compose service
a fresh checkout depends on. Settings are evaluated once at import, so each
environment-varying case starts a fresh interpreter.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SECRET_KEY = 'pytest-cache-config-key-9f3c1a7e5b2d8046c9f1a3e7'

# The URL ll_project/settings.py falls back to when REDIS_URL is unset. Kept in
# lockstep with docker-compose.yml by test_compose_service_matches_the_cache_default.
DEFAULT_REDIS_URL = 'redis://127.0.0.1:6379/0'

# Prints the resolved default cache configuration as JSON.
_DUMP_CACHE = """
import json

import dotenv

# The test owns the environment. load_dotenv(override=False) would re-inject
# .env values for any key _cache() cleared, so a developer's .env would silently
# stand in for the settings fallback. Disable it before settings import.
dotenv.load_dotenv = lambda *a, **k: None

import django

django.setup()
from django.conf import settings

c = settings.CACHES["default"]
print("__CACHE__" + json.dumps({
    "BACKEND": c["BACKEND"],
    "LOCATION": c["LOCATION"],
    "KEY_PREFIX": c.get("KEY_PREFIX"),
    "OPTIONS": c.get("OPTIONS", {}),
}))
"""


def _cache(**overrides):
    """Return the resolved default cache for a fresh interpreter.

    Every environment variable the settings module reads is pinned first, so the
    result never depends on a developer's ``.env`` or shell. ``REDIS_URL`` is
    cleared by default; the honouring test opts back in.
    """
    env = os.environ.copy()
    env['DJANGO_SECRET_KEY'] = SECRET_KEY
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'
    env['DJANGO_DEBUG'] = 'True'
    env['DJANGO_ALLOWED_HOSTS'] = ''
    env.pop('REDIS_URL', None)
    env.update(overrides)

    result = subprocess.run(
        [sys.executable, '-c', _DUMP_CACHE],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    line = next(
        line for line in result.stdout.splitlines() if line.startswith('__CACHE__')
    )
    return json.loads(line[len('__CACHE__'):])


def test_loaded_settings_use_the_redis_backend():
    """The suite's own cache must be Redis, never process-local memory."""
    assert settings.CACHES['default']['BACKEND'] == (
        'django.core.cache.backends.redis.RedisCache'
    )


def test_redis_url_environment_variable_is_honoured():
    data = _cache(REDIS_URL='redis://cache.example.com:6380/2')

    assert data['LOCATION'] == 'redis://cache.example.com:6380/2'


def test_unset_redis_url_falls_back_to_the_compose_default():
    """A fresh checkout with no REDIS_URL targets the docker-compose service."""
    data = _cache()

    assert data['LOCATION'] == DEFAULT_REDIS_URL


def test_key_prefix_namespaces_the_cache():
    """One Redis may be shared, so keys must carry a project prefix."""
    assert _cache()['KEY_PREFIX'] == 'maarifa'


def test_socket_timeouts_make_the_cache_fail_fast():
    """A health probe must not hang on an unreachable Redis.

    Without socket timeouts a blackholed Redis (packets dropped, no RST) would
    block on the OS TCP timeout for minutes, so "reports down" would only ever
    be true for an instant refusal. These two options bound that wait.
    """
    options = _cache()['OPTIONS']

    assert options.get('socket_connect_timeout'), 'connect timeout must be set'
    assert options.get('socket_timeout'), 'read/write timeout must be set'
    assert options['socket_connect_timeout'] > 0
    assert options['socket_timeout'] > 0


def test_compose_service_matches_the_cache_default():
    """The compose redis service and the settings fallback must not drift apart.

    If they disagree, a fresh clone follows the README, starts a container, and
    still cannot cache. Keeping this invariant tested is the cheap fix.
    """
    compose = (PROJECT_ROOT / 'docker-compose.yml').read_text(encoding='utf-8')
    default = _cache()

    assert re.search(r'^\s*redis:\s*$', compose, re.MULTILINE), (
        'docker-compose.yml must define a redis service'
    )

    port_match = re.search(r'\$\{REDIS_PORT:-(\d+)\}', compose)
    assert port_match, 'docker-compose.yml must publish a default REDIS_PORT'
    assert port_match.group(1) == str(urlparse(DEFAULT_REDIS_URL).port)
    assert urlparse(default['LOCATION']).port == int(port_match.group(1))


def test_compose_redis_service_is_pinned_and_health_checked():
    compose = (PROJECT_ROOT / 'docker-compose.yml').read_text(encoding='utf-8')

    assert 'image: redis:7-alpine' in compose
    assert '["CMD", "redis-cli", "ping"]' in compose, (
        'compose needs a redis healthcheck for CI readiness'
    )
