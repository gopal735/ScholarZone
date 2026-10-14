import requests

client_ids = [
    "Iv1.8e97b4b1a8637ed5",
    "Iv23c8dbb3c1d3db59",
    "Iv1.2776b9b63e1011ff",
    "012a59a18637ed5",
]

for cid in client_ids:
    resp = requests.post(
        "https://github.com/login/device/code",
        data={"client_id": cid, "scope": "repo"},
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    print(f"Client ID: {cid} -> HTTP {resp.status_code}: {resp.text[:200]}")
    if resp.status_code == 200:
        print("  SUCCESS!")
        print(f"  Full response: {resp.text}")
        break
