import requests
import time
import os
import sys
import subprocess
import webbrowser

# Step 1: Request a device code from GitHub
client_id = "Iv1.8e97b4b1a8637ed5"  # GitHub CLI client ID (might change)
resp = requests.post(
    "https://github.com/login/device/code",
    data={
        "client_id": client_id,
        "scope": "repo",
        "request": "device_code",
    },
    headers={"Accept": "application/json"},
)
print(f"Device code request: {resp.status_code}")
print(f"Headers: {dict(resp.headers)}")
print(f"Body: {resp.text[:500]}")
