"""Celery application configuration for Maarifa's background workers.

The app loads Django settings under the ``CELERY_`` namespace and discovers
tasks from installed Django apps. Product schedules intentionally do not live
here: Phase 11 will resolve them from ``ScheduleConfig`` database rows.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'll_project.settings')

app = Celery('ll_project', include=['ll_project.tasks'])
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
