import requests
import sys

r = requests.get('https://scholarzone-api-2ee2d.containers.snapdeploy.app/health', timeout=20)
# Write response to file for safe handling
with open('wake_page_response.html', 'w', encoding='utf-8') as f:
    f.write(r.text)
print(f"Saved wake page to wake_page_response.html ({len(r.text)} bytes)")
print(f"Status: {r.status_code}")
for k, v in r.headers.items():
    print(f"  {k}: {v[:200]}")
