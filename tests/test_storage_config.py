"""Phase 4 checks for local and S3-compatible media storage selection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import override_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRET_KEY = 'pytest-storage-config-key-9f3c1a7e5b2d8046c9f1a3e7'
S3_ENV_VARS = (
    'S3_BUCKET_NAME',
    'S3_ACCESS_KEY_ID',
    'S3_SECRET_ACCESS_KEY',
    'S3_ENDPOINT_URL',
    'S3_REGION_NAME',
    'S3_CUSTOM_DOMAIN',
)

_DUMP_STORAGE = """
import json
import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: None

import django

django.setup()
from django.conf import settings

storage = settings.STORAGES['default']
print('__STORAGE__' + json.dumps({
    'BACKEND': storage['BACKEND'],
    'OPTIONS': storage.get('OPTIONS', {}),
    'MEDIA_URL': settings.MEDIA_URL,
    'MEDIA_ROOT': str(settings.MEDIA_ROOT),
}, default=str))
"""


def _storage_settings(**overrides):
    """Load media settings in a fresh, environment-controlled interpreter."""
    env = os.environ.copy()
    env['DJANGO_SECRET_KEY'] = SECRET_KEY
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'
    env['DJANGO_DEBUG'] = 'True'
    env['DJANGO_ALLOWED_HOSTS'] = ''
    for name in S3_ENV_VARS:
        env.pop(name, None)
    env.update(overrides)

    result = subprocess.run(
        [sys.executable, '-c', _DUMP_STORAGE],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    marker = '__STORAGE__'
    line = next(line for line in result.stdout.splitlines() if line.startswith(marker))
    return json.loads(line[len(marker):])


def test_local_development_uses_filesystem_media_storage():
    data = _storage_settings()

    assert data['BACKEND'] == 'django.core.files.storage.FileSystemStorage'
    assert data['MEDIA_URL'] == '/media/'
    assert data['MEDIA_ROOT'].endswith('/media')


def test_complete_s3_environment_selects_the_s3_backend():
    data = _storage_settings(
        S3_BUCKET_NAME='maarifa-media',
        S3_ACCESS_KEY_ID='access-key',
        S3_SECRET_ACCESS_KEY='secret-key',
        S3_ENDPOINT_URL='https://objects.example.test',
        S3_REGION_NAME='af-south-1',
        S3_CUSTOM_DOMAIN='media.example.test',
    )

    assert data['BACKEND'] == 'storages.backends.s3.S3Storage'
    assert data['OPTIONS'] == {
        'access_key': 'access-key',
        'secret_key': 'secret-key',
        'bucket_name': 'maarifa-media',
        'endpoint_url': 'https://objects.example.test',
        'region_name': 'af-south-1',
        'custom_domain': 'media.example.test',
    }


def test_partial_s3_configuration_fails_loudly():
    env = os.environ.copy()
    env['DJANGO_SECRET_KEY'] = SECRET_KEY
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'
    env['S3_BUCKET_NAME'] = 'maarifa-media'
    for name in S3_ENV_VARS[1:]:
        env.pop(name, None)

    result = subprocess.run(
        [sys.executable, '-c', 'import django; django.setup()'],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert 'S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY' in result.stderr


def test_file_upload_round_trips_through_the_configured_local_backend(tmp_path):
    """The local storage backend writes a file and returns its original bytes."""
    storage_settings = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
            'OPTIONS': {
                'location': str(tmp_path),
                'base_url': '/media/',
            },
        },
        'staticfiles': settings.STORAGES['staticfiles'],
    }
    with override_settings(STORAGES=storage_settings):
        name = default_storage.save('phase4/smoke.txt', ContentFile(b'maarifa'))
        try:
            with default_storage.open(name, 'rb') as uploaded:
                assert uploaded.read() == b'maarifa'
        finally:
            default_storage.delete(name)

    assert not (tmp_path / 'phase4' / 'smoke.txt').exists()


def test_s3_storage_dependencies_are_pinned():
    requirements = (PROJECT_ROOT / 'requirements.txt').read_text(encoding='utf-8')

    assert 'django-storages==' in requirements
    assert 'boto3==' in requirements
