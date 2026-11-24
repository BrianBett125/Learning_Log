"""Phase 3 checks for the Celery worker and its Redis broker wiring."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import override_settings

from ll_project.celery import app
from ll_project.tasks import heartbeat

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_heartbeat_runs_eagerly_in_tests():
    """A task can execute deterministically without starting a worker."""
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
        result = heartbeat.delay()

    assert result.get() == 'ok'


def test_heartbeat_is_registered_for_a_standalone_worker():
    """The worker imports project-level tasks as well as app-owned tasks."""
    assert heartbeat.name in app.tasks


def test_celery_uses_the_configured_redis_broker():
    """A broker connection can be opened against the configured Redis service."""
    assert app.conf.broker_url == settings.CELERY_BROKER_URL

    with app.connection_for_write() as connection:
        connection.ensure_connection(max_retries=1)
        assert connection.connected


def test_beat_schedule_is_empty_until_schedule_config_exists():
    """Product cadence must not be hardcoded before Phase 11."""
    assert settings.CELERY_BEAT_SCHEDULE == {}


def test_procfile_declares_worker_and_beat_processes():
    procfile = (PROJECT_ROOT / 'Procfile').read_text(encoding='utf-8')

    assert re.search(r'^worker: celery -A ll_project worker\b', procfile, re.MULTILINE)
    assert re.search(r'^beat: celery -A ll_project beat\b', procfile, re.MULTILINE)
