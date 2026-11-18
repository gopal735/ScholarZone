import os
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "student-dashboard-migration.yml"


def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_global_concurrency_group_preserved():
    text = workflow_text()
    assert "group: student-dashboard-migration-production" in text
    assert "cancel-in-progress: false" in text
    assert "group: ${{ github.workflow }}-${{ github.ref }}" not in text


def test_apply_defaults_false_and_is_gated():
    text = workflow_text()
    assert "default: false" in text
    assert "if: ${{ inputs.apply }}" in text


def test_production_environment_and_identity_gates():
    text = workflow_text()
    assert "environment: production" in text
    assert "SCHOLARZONE_EXPECTED_DB_IDENTIFIER" in text
    assert "SCHOLARZONE_EXPECTED_DB_HOST" in text


def test_backup_gate_and_commands_present():
    text = workflow_text()
    assert "SCHOLARZONE_BACKUP_VERIFIED" in text
    assert "python migrate_schema.py --dry-run --report" in text
    assert "python migrate_schema.py --validate-only --report" in text


def test_pipefail_prevents_hidden_failures():
    text = workflow_text()
    assert "shell: bash" in text
    assert "set -euo pipefail" in text or "pipefail" in text


def test_logs_uploaded_on_always():
    text = workflow_text()
    assert "if: always()" in text
    assert "upload-artifact" in text