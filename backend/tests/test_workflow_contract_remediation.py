import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT_WORKFLOW = REPO / ".github" / "workflows" / "closed-scholarship-purge-preflight.yml"
PRODUCTION_WORKFLOW = REPO / ".github" / "workflows" / "production-purge-preflight.yml"
EXECUTE_WORKFLOW = REPO / ".github" / "workflows" / "closed-scholarship-purge-execute.yml"
WORKFLOW = PREFLIGHT_WORKFLOW


def _env_of_job(data, job_id):
    return data["jobs"][job_id].get("env", {}) or {}


def test_production_gate4_maps_expected_database_host():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    env = _env_of_job(data, "gate4-backup")
    assert env.get("EXPECTED_DATABASE_HOST") == "${{ secrets.EXPECTED_DATABASE_HOST }}"


def test_closed_gate4_maps_expected_database_host():
    data = yaml.safe_load(PREFLIGHT_WORKFLOW.read_text(encoding="utf-8"))
    env = _env_of_job(data, "preflight-gate4-backup")
    assert env.get("EXPECTED_DATABASE_HOST") == "${{ secrets.EXPECTED_DATABASE_HOST }}"


def test_production_gate4_provisions_gpg_keys():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["gate4-backup"].get("steps", [])
    assert any("Provision GPG keys" in str(s.get("name", "")) for s in steps if isinstance(s, dict))


def test_production_gate7_sets_stage1_master_sha():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    env = _env_of_job(data, "gate7-git-safety")
    assert env.get("STAGE1_MASTER_SHA") == "${{ github.sha }}"

import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT_WORKFLOW = REPO / ".github" / "workflows" / "closed-scholarship-purge-preflight.yml"
PRODUCTION_WORKFLOW = REPO / ".github" / "workflows" / "production-purge-preflight.yml"
EXECUTE_WORKFLOW = REPO / ".github" / "workflows" / "closed-scholarship-purge-execute.yml"


def test_production_workflow_gate7_verifies_repository_and_ref():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["gate7-git-safety"].get("steps", [])
    joined = "\n".join(str(s.get("run", "")) for s in steps if isinstance(s, dict))
    assert "github.ref" in joined and "refs/heads/master" in joined
    assert "github.repository" in joined


def test_production_workflow_gate7_checkout_uses_github_sha():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["gate7-git-safety"].get("steps", [])
    checkouts = [s for s in steps if isinstance(s, dict) and str(s.get("uses", "")).startswith("actions/checkout@")]
    assert checkouts
    assert checkouts[0].get("with", {}).get("ref") == "${{ github.sha }}"


def test_production_workflow_gate7_sets_stage1_master_sha_from_github_sha():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    env = data["jobs"]["gate7-git-safety"].get("env", {}) or {}
    assert env.get("STAGE1_MASTER_SHA") == "${{ github.sha }}"


def test_production_workflow_does_not_upload_trusted_stage1_artifacts():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    artifact_names = []
    for job in data["jobs"].values():
        for step in job.get("steps", []):
            if isinstance(step, dict) and "upload-artifact" in str(step.get("uses", "")):
                artifact_names.append(str(step.get("with", {}).get("name", "")))
    assert "preflight-summary" not in artifact_names
    assert "deletion-manifest" not in artifact_names


def test_closed_workflow_uploads_trusted_stage1_artifacts():
    data = yaml.safe_load(PREFLIGHT_WORKFLOW.read_text(encoding="utf-8"))
    artifact_names = []
    for job in data["jobs"].values():
        for step in job.get("steps", []):
            if isinstance(step, dict) and "upload-artifact" in str(step.get("uses", "")):
                artifact_names.append(str(step.get("with", {}).get("name", "")))
    assert ("preflight-summary" in artifact_names) or ("deletion-manifest" in artifact_names)


def test_verify_preflight_provenance_default_path_is_closed_workflow():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vpp", REPO / ".github" / "scripts" / "verify_preflight_provenance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.EXPECTED_WORKFLOW_PATH_DEFAULT == ".github/workflows/closed-scholarship-purge-preflight.yml"


def test_azure_oidc_permissions_scoped():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    gate7_perms = data["jobs"]["gate7-git-safety"].get("permissions", {}) or {}
    assert gate7_perms.get("id-token") != "write"
    steps = data["jobs"]["gate4-backup"].get("steps", [])
    assert any("azure/login" in str(s.get("uses", "")) for s in steps if isinstance(s, dict))


def test_azure_login_uses_oidc_fields():
    raw = PRODUCTION_WORKFLOW.read_text(encoding="utf-8")
    assert "client-id: ${{ secrets.AZURE_CLIENT_ID }}" in raw
    assert "tenant-id: ${{ secrets.AZURE_TENANT_ID }}" in raw
    assert "subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}" in raw


def test_no_client_secret_auth_in_workflows():
    for wf in (PRODUCTION_WORKFLOW, PREFLIGHT_WORKFLOW, EXECUTE_WORKFLOW):
        raw = wf.read_text(encoding="utf-8")
        assert "client-secret" not in raw.lower()
        assert "AZURE_CLIENT_SECRET" not in raw


def test_id_token_write_not_on_gate7():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    assert data["jobs"]["gate7-git-safety"].get("permissions", {}).get("id-token") != "write"


def test_production_gate7_not_using_environment():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    # gate7 has no environment (relies on ref check now)
    assert data["jobs"]["gate7-git-safety"].get("environment") is None


def test_production_gpg_provisioning_after_install():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["gate4-backup"].get("steps", [])
    names = [str(s.get("name", "")) for s in steps if isinstance(s, dict)]
    install_idx = next(i for i, n in enumerate(names) if "Install PostgreSQL client and GPG" in n)
    prov_idx = next(i for i, n in enumerate(names) if "Provision GPG keys" in n)
    assert install_idx < prov_idx


def test_production_gpg_cleanup_always():
    data = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["gate4-backup"].get("steps", [])
    cleanup = [s for s in steps if isinstance(s, dict) and "Clean up ephemeral GPG keyring" in str(s.get("name", ""))]
    assert cleanup
    assert cleanup[0].get("if") == "always()"
