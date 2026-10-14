import requests

r = requests.get(
    "https://api.github.com/repos/gopal735/ScholarZone/actions/runs",
    headers={"Accept": "application/vnd.github.v3+json", "X-GitHub-Api-Version": "2022-11-28"},
    timeout=30,
)
print(f"GitHub API status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    runs = data.get("workflow_runs", [])
    print(f"Total workflow runs: {data.get('total_count', 0)}")
    for run in runs[:10]:
        name = run.get("name", "")
        status = run.get("status", "")
        conclusion = run.get("conclusion", "")
        created = run.get("created_at", "")
        html_url = run.get("html_url", "")
        print(f"  - {name}: {status}/{conclusion} at {created}")
        print(f"    URL: {html_url}")
elif r.status_code == 403:
    print(f"Rate limited or requires auth: {r.text[:300]}")
    # Also check raw response for rate limit info
    for k, v in r.headers.items():
        if "ratelimit" in k.lower():
            print(f"  {k}: {v}")
