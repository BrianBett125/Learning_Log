"""Maarifa project package."""

# Importing the app here makes ``shared_task`` use the configured project app
# for web processes, workers, management commands, and tests alike.
from .celery import app as celery_app

__all__ = ('celery_app',)
