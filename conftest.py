"""Pytest bootstrap for the Maarifa project.

``ll_project.settings`` raises ``ImproperlyConfigured`` when
``DJANGO_SECRET_KEY`` is missing, and loads a local ``.env`` when present.
Tests must not depend on a developer's ``.env``, so a deterministic throwaway
key is provided only when the environment has none. This module is imported
before pytest-django configures Django, so the fallback is in place by the time
settings are read.
"""

import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'django-insecure-test-only-key')
