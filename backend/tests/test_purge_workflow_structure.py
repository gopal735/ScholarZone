import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "closed-scholarship-auto-purge.yml"

def test_workflow_yaml_parses():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "jobs" in data
    assert len(data["jobs"]) > 0

def test_needs_references_valid():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    for job_id, job in jobs.items():
        needs = job.get("needs")
        if isinstance(needs, str):
            needs = [needs]
        elif needs is None:
            needs = []
        for dep in needs:
            deps = dep if isinstance(dep, list) else [dep]
            for d in deps:
                assert d in jobs, f"{job_id} references unknown job {d}"

def test_no_dependency_cycle():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    # Build adjacency
    graph = {}
    for job_id, job in jobs.items():
        needs = job.get("needs") or []
        if isinstance(needs, str):
            needs = [needs]
        graph[job_id] = list(needs)
    # Kahn's algorithm
    from collections import deque
    indeg = {n: 0 for n in graph}
    for n, deps in graph.items():
        for d in deps:
            indeg[n] += 1
    # Actually indegree should count incoming edges; recompute properly
    indeg = {n: 0 for n in graph}
    for n, deps in graph.items():
        for d in deps:
            indeg[n] += 1
    q = deque([n for n in graph if indeg[n] == 0])
    visited = 0
    while q:
        n = q.popleft()
        visited += 1
        for m, deps in graph.items():
            if n in deps:
                indeg[m] -= 1
                if indeg[m] == 0:
                    q.append(m)
    assert visited == len(graph), "Dependency cycle detected"

def test_executor_depends_on_summary_and_validation():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    exec_job = jobs["execute-deletion"]
    needs = exec_job.get("needs") or []
    if isinstance(needs, str):
        needs = [needs]
    assert "preflight-summary" in needs
    assert "validate-manifest" in needs

def test_no_run_and_uses_same_step():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job_id, job in data["jobs"].items():
        for step in job.get("steps", []):
            if isinstance(step, dict):
                assert not ("run" in step and "uses" in step), f"Malformed step in {job_id}"


def test_verify_merge_trigger_checks_out_before_verifier():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["verify-merge-trigger"]
    steps = job.get("steps", [])
    checkout_index = None
    verifier_index = None
    for index, step in enumerate(steps):
        if isinstance(step, dict) and step.get("uses", "").startswith("actions/checkout@"):
            checkout_index = index
        if isinstance(step, dict) and "verify_pr_merge_trigger.py" in str(step.get("run", "")):
            verifier_index = index
    assert checkout_index is not None, "verify-merge-trigger must check out the repository"
    assert verifier_index is not None, "verify-merge-trigger must run the verifier"
    assert checkout_index < verifier_index, "checkout must precede verifier execution"

    checkout_step = steps[checkout_index]
    assert checkout_step["uses"].startswith("actions/checkout@v4")
    assert checkout_step.get("with", {}).get("fetch-depth") == 0

def test_verify_merge_trigger_has_python_runtime():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["verify-merge-trigger"]
    steps = job.get("steps", [])
    assert any(
        isinstance(step, dict)
        and step.get("uses", "").startswith("actions/setup-python@")
        for step in steps
    ), "verify-merge-trigger must set up Python"

def test_verify_merge_trigger_has_least_privilege_permissions():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["verify-merge-trigger"]
    permissions = job.get("permissions", {})
    assert permissions.get("contents") == "read"
    assert permissions.get("pull-requests") == "read"


def test_execute_deletion_needs_backup_job():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    exec_job = data["jobs"]["execute-deletion"]
    needs = exec_job.get("needs") or []
    if isinstance(needs, str):
        needs = [needs]
    assert "preflight-gate4-backup" in needs, "execute-deletion must explicitly depend on backup verification"


def test_execute_deletion_requires_backup_success():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    exec_job = data["jobs"]["execute-deletion"]
    condition = str(exec_job.get("if", ""))
    assert "preflight-gate4-backup.result == 'success'" in condition, (
        "execute-deletion must not run unless backup verification succeeded"
    )
