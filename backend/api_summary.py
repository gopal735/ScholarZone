import requests
import json

base = 'https://scholarzone-api-2ee2d.containers.snapdeploy.app'

# Test all endpoints one more time with proper error handling
tests = [
    ('/health', 'GET', None),
    ('/scholarships/stats', 'GET', None),
    ('/scholarships', 'GET', None),
    ('/scholarships/1', 'GET', None),
    ('/scholarships/100', 'GET', None),
    ('/scholarships/306', 'GET', None),
    ('/scholarships/489', 'GET', None),
    ('/scholarships/490', 'GET', None),
]

all_pass = True
for path, method, _ in tests:
    url = base + path
    r = requests.request(method, url, timeout=15, headers={'Cache-Control':'no-cache'})
    status = 'PASS' if r.status_code == 200 else 'FAIL'
    if r.status_code != 200:
        all_pass = False
    print(f'{path}: {status} (HTTP {r.status_code})')
    if r.status_code == 200:
        try:
            data = r.json()
            if path == '/scholarships/stats':
                print(f'  stats: total={data.get("total")}, open={data.get("open")}, verified={data.get("verified_active")}')
            elif path == '/scholarships':
                print(f'  items: {len(data.get("items", []))}')
            elif path.startswith('/scholarships/'):
                print(f'  id={data.get("id")}, title={data.get("title", data.get("name", "?"))[:50]}')
        except:
            pass

print(f'\nAPI Tests: {"ALL PASS" if all_pass else "SOME FAILED"}')
