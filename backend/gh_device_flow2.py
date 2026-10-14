import requests
import time
import subprocess
import os
import threading

# Start gh auth login and capture the verification URI
proc = subprocess.Popen(
    ["gh", "auth", "login", "--web", "--hostname", "github.com", "--scopes", "repo"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
)

# Give it time to request device code
time.sleep(5)

# Read initial output
import select
timeout = 10
start = time.monotonic()
output = ""
while time.monological() - start < timeout if hasattr(time, 'monological') else time.monotonic() - start < timeout:
    if proc.poll() is not None:
        break
    ready, _, _ = select.select([proc.stderr], [], [], 0.5)
    if ready:
        line = proc.stderr.readline()
        output += line
        print(f"GH: {line.strip()}")
        if "code:" in line:
            # Extract the code
            code = line.strip().split("code:")[1].strip()
            print(f"Extracted code: {code}")
            break
    time.sleep(0.5)

# Also check stdout
ready, _, _ = select.select([proc.stdout], [], [], 2)
if ready:
    line = proc.stdout.readline()
    output += line
    print(f"STDOUT: {line.strip()}")

proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()

# Now try to get device code directly from GitHub API
# GitHub CLI OAuth App client ID
gh_client_id = "Iv1.8e97b4b1a8637ed5"
resp = requests.post(
    "https://github.com/login/device/code",
    data={"client_id": gh_client_id, "scope": "repo"},
    headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
)
print(f"\nDevice code request: HTTP {resp.status_code}")
if resp.status_code == 200:
    print(f"Response: {resp.text}")
else:
    print(f"Response: {resp.text[:300]}")
    print("Trying alternative client IDs...")
    alts = ["Iv23c8dbb3c1d3db59", "Iv1.2776b9b63e1011ff", "012a59a18637ed5", "Iv1.8e97b4b1a8637ed5"]
    for cid in alts:
        r = requests.post(
            "https://github.com/login/device/code",
            data={"client_id": cid, "scope": "repo"},
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        )
        status = "✓" if r.status_code == 200 else "✗"
        print(f"  {status} {cid}: HTTP {r.status_code}")
