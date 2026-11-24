"""Project-level background tasks.

Tasks tied to a bounded product concern will live in their owning Django app.
This small task is intentionally project-level: it verifies the worker path is
alive before any product feature depends on it.
"""

from __future__ import annotations

from celery import shared_task


@shared_task(ignore_result=True)
def heartbeat() -> str:
    """Return a stable marker proving a queued task reached a worker."""
    return 'ok'
