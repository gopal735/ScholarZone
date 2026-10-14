import requests

# Try different casing
repos = [
    "gopal735/ScholarZone",
    "gopal735/scholarzone",
    "scholarzone/ScholarZone",
    "scholarzone/scholarzone",
]

for repo in repos:
    r = requests.get(
        f"https://api.github.com/repos/{repo}",
        headers={"Accept": "application/vnd.github.v3+json"},
        timeout=10,
    )
    print(f"{repo}: HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Found! full_name={data.get('full_name')}, private={data.get('private')}")
