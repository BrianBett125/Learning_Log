"""Liveness probes for the platform's runtime dependencies.

Phase 2 (plan §4) ships the Redis cache probe. Phase 24 (monitoring) is where
these become HTTP endpoints; a probe therefore returns data rather than printing
or exiting on its own.

Every probe has the same contract: it never raises. A dependency that is down is
a *reported* state (``ok=False`` with a short ``detail``), not an exception the
caller has to catch. That is what makes a probe safe to call from a health
endpoint, an operator command, or a test.
"""

from __future__ import annotations

import dataclasses
import uuid

from django.core.cache import caches

# The probe writes and reads back this value to prove the cache round-trips. The
# key is namespaced and made unique per call (below): two probes running at once
# — several workers polled by a load balancer — must not read or delete each
# other's sentinel and report a false "down".
CACHE_PROBE_KEY = 'health:cache:probe'
CACHE_PROBE_VALUE = 'ok'
CACHE_PROBE_TTL = 10


@dataclasses.dataclass(frozen=True)
class DependencyHealth:
    """The outcome of probing one dependency."""

    name: str
    ok: bool
    detail: str = ''


def check_cache(alias: str = 'default') -> DependencyHealth:
    """Prove the cache is usable by round-tripping a value through it.

    A read alone could be served from a backend that swallowed the write, and a
    write alone could be acknowledged and dropped. Writing a sentinel and reading
    it back exercises the connection, the selected Redis database, and the
    serializer together, which is what "the cache works" actually means.

    The sentinel carries a short TTL and is left to expire rather than deleted,
    so the probe holds no state that a second probe could clobber.
    """
    key = f'{CACHE_PROBE_KEY}:{uuid.uuid4().hex}'
    try:
        backend = caches[alias]
        backend.set(key, CACHE_PROBE_VALUE, CACHE_PROBE_TTL)
        if backend.get(key) == CACHE_PROBE_VALUE:
            return DependencyHealth(name='cache', ok=True)
        return DependencyHealth(
            name='cache',
            ok=False,
            detail='cache did not return the value it accepted',
        )
    except Exception as exc:  # a down Redis raises; a probe reports, never raises
        return DependencyHealth(
            name='cache',
            ok=False,
            detail=f'{type(exc).__name__}: {exc}',
        )
