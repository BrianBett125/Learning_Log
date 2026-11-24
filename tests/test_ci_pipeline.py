"""Phase 5 gate and corpus checks for the GitHub Actions pipeline."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = PROJECT_ROOT / '.github' / 'workflows' / 'ci.yml'


def _workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_ci_workflow_runs_for_pushes_and_pull_requests():
    workflow = _workflow()

    assert '  push:' in workflow
    assert '  pull_request:' in workflow
    assert 'actions/checkout@v4' in workflow
    assert 'actions/setup-python@v5' in workflow


def test_ci_workflow_provisions_postgres_and_redis():
    workflow = _workflow()

    assert 'postgres:' in workflow
    assert 'image: pgvector/pgvector:pg17' in workflow
    assert 'pg_isready -U maarifa -d maarifa' in workflow
    assert 'redis:' in workflow
    assert 'image: redis:7-alpine' in workflow
    assert 'redis-cli ping' in workflow
    assert 'DATABASE_URL: postgres://maarifa:maarifa@127.0.0.1:5432/maarifa' in workflow
    assert 'REDIS_URL: redis://127.0.0.1:6379/0' in workflow


def test_ci_workflow_blocks_on_lint_migration_drift_and_tests():
    workflow = _workflow()
    test_job = workflow.split('\n  deploy:', maxsplit=1)[0]

    assert 'ruff check .' in test_job
    assert 'python manage.py makemigrations --check --dry-run' in test_job
    assert 'run: pytest' in test_job
    assert 'continue-on-error: true' not in test_job


def test_deploy_template_waits_for_a_successful_main_push():
    workflow = _workflow()
    deploy_job = workflow.split('\n  deploy:', maxsplit=1)[1]

    assert 'needs: test' in deploy_job
    assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" in deploy_job
    assert 'environment: production' in deploy_job


def test_requirements_pin_the_ci_linter():
    requirements = (PROJECT_ROOT / 'requirements.txt').read_text(encoding='utf-8')

    assert 'ruff==' in requirements


def test_migration_guard_fails_for_uncommitted_model_changes(tmp_path):
    """The command CI runs exits non-zero when a model lacks a migration."""
    checkout = tmp_path / 'checkout'
    shutil.copytree(
        PROJECT_ROOT,
        checkout,
        ignore=shutil.ignore_patterns('.git', '.venv', '__pycache__', '.pytest_cache'),
    )
    models = checkout / 'learning_logs' / 'models.py'
    models.write_text(
        models.read_text(encoding='utf-8')
        + '\n\nclass MigrationGuardProbe(models.Model):\n'
        "    name = models.CharField(max_length=32)\n",
        encoding='utf-8',
    )
    env = os.environ.copy()
    env['DJANGO_SECRET_KEY'] = 'ci-test-only-secret-key-9f3c1a7e5b2d8046c9f1a3e7'
    env['DJANGO_SETTINGS_MODULE'] = 'll_project.settings'

    result = subprocess.run(
        [sys.executable, 'manage.py', 'makemigrations', '--check', '--dry-run'],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert 'MigrationGuardProbe' in result.stdout
