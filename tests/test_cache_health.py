"""Behavioral tests for the cache and its health probe (Phase 2).

These talk to the real Redis started by docker compose, because the claims are
"the cache works" and "its health check reports the truth" — a fake backend can
prove neither. The single case that must simulate a failure mocks the cache, so
the "down" branch is exercised deterministically instead of by stopping Redis.
"""

import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from django.conf import settings
from django.core.cache import cache, caches

from ll_project import health

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _unique_key() -> str:
    return f'health:test:{uuid.uuid4().hex}'


def test_cache_round_trip_and_invalidation():
    """A value written is read back, and delete invalidates it."""
    key = _unique_key()
    assert cache.get(key) is None

    cache.set(key, 'value', 30)
    assert cache.get(key) == 'value'

    cache.delete(key)
    assert cache.get(key) is None


def test_a_cached_value_survives_a_process_restart():
    """The value lives in Redis, not in this process's memory.

    A fresh interpreter writes the value and exits; this process then reads it
    back. A process-local cache (LocMemCache) would have lost it, so the hit is
    proof the value outlives the process that wrote it — the acceptance wording.
    """
    key = _unique_key()
    value = uuid.uuid4().hex

    location = settings.CACHES['default']['LOCATION']
    if isinstance(location, (list, tuple)):
        location = location[0]

    env = os.environ.copy()
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'
    env.setdefault('DJANGO_SECRET_KEY', 'django-insecure-test-only-key')
    # Pin the same Redis this process resolved, whatever .env or the shell set.
    env['REDIS_URL'] = location

    writer = (
        'import django; django.setup();'
        'from django.core.cache import cache;'
        f'cache.set({key!r}, {value!r}, 30);'
    )
    result = subprocess.run(
        [sys.executable, '-c', writer],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    try:
        assert cache.get(key) == value
    finally:
        cache.delete(key)


def test_check_cache_reports_up():
    result = health.check_cache()

    assert result.name == 'cache'
    assert result.ok is True
    assert result.detail == ''


def test_check_cache_reports_down_without_raising(monkeypatch):
    """A dead Redis is a reported state, not an exception to the caller."""
    backend = caches['default']

    def boom(*args, **kwargs):
        raise ConnectionError('connection refused')

    # The health probe fetches the same cached backend instance, so patching its
    # set() makes the round-trip fail exactly as an unreachable Redis would.
    monkeypatch.setattr(backend, 'set', boom)

    result = health.check_cache()

    assert result.name == 'cache'
    assert result.ok is False
    assert 'ConnectionError' in result.detail


def test_concurrent_probes_do_not_report_a_false_down():
    """The probe holds no shared state, so parallel probes cannot clobber it.

    Several workers polling the health endpoint at once is the Phase 24 shape. A
    single fixed sentinel key, deleted in a finally block, would let one probe
    delete another's value mid-round-trip and report a false down; a unique key
    per call removes that. The failure is a race, so it takes contention to
    surface — hence real threads and many iterations.
    """
    outcomes = []

    def probe_repeatedly():
        for _ in range(25):
            outcomes.append(health.check_cache().ok)

    threads = [threading.Thread(target=probe_repeatedly) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(outcomes) == 200
    assert all(outcomes), 'a concurrent probe reported the cache as down'
