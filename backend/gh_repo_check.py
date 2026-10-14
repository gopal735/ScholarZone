import requests

# Try the repo info endpoint to check if it's public
r = requests.get(
    "https://api.github.com/repos/gopal735/ScholarZone",
    headers={"Accept": "application/vnd.github.v3+json", "X-GitHub-Api-Version": "2022-11-28"},
    timeout=30,
)
print(f"Repo info: HTTP {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  Name: {data.get('full_name')}")
    print(f"  Private: {data.get('private')}")
    print(f"  Default branch: {data.get('default_branch')}")
    print(f"  Pushed at: {data.get('pushed_at')}")

# Try workflow runs
r2 = requests.get(
    "https://api.github.com/repos/gopal735/ScholarZone/actions/runs",
    headers={"Accept": "application/vnd.github.v3+json", "X-GitHub-Api-Version": "2022-11-28"},
    timeout=30,
)
print(f"\nWorkflow runs: HTTP {r2.status_code}")
if r2.status_code == 200:
    data = r2.json()
    print(f"  Total runs: {data.get('total_count', 0)}")
    for run in data.get("workflow_runs", [])[:10]:
        name = run.get("name", "")
        status = run.get("status", "")
        conclusion = run.get("conclusion", "")
        created = run.get("created_at", "")
        branch = run.get("head_branch", "")
        print(f"  - {name}: status={status}, conclusion={conclusion}, branch={branch}, at={created}")
elif r2.status_code == 404:
    print(f"  Not found: {r2.text[:200]}")
elif r2.status_code == 403:
    print(f"  Forbidden: {r2.text[:200]}")
    for k, v in r2.headers.items():
        if "ratelimit" in k.lower():
            print(f"  {k}: {v}")
