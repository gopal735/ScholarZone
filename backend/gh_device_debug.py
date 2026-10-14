import requests
import urllib.parse

client_id = "178c6fc778ccc68e1d6a"

# Request device code with JSON accept
resp = requests.post(
    "https://github.com/login/device/code",
    data={"client_id": client_id, "scope": "repo"},
    headers={"Accept": "application/json"},
)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type')}")
print(f"Raw body: {repr(resp.text)}")

# Try JSON
try:
    data = resp.json()
    print(f"JSON: {data}")
except:
    data = urllib.parse.parse_qs(resp.text)
    data = {k: v[0] if v else None for k, v in data.items()}
    print(f"Form: {data}")
