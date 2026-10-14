import requests

base = 'https://scholarzone-api-2ee2d.containers.snapdeploy.app'
origin = 'https://gopal735.github.io'

print('=== Simulating Frontend API Calls ===')

# 1. Fetch stats
r = requests.get(f'{base}/scholarships/stats', headers={'Origin': origin, 'Cache-Control': 'no-cache'}, timeout=15)
print(f'GET /scholarships/stats: HTTP {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'  total={data.get("total")}, open={data.get("open")}, verified={data.get("verified_active")}')

# 2. Fetch scholarships page 1
r = requests.get(f'{base}/scholarships?page=1&limit=12', headers={'Origin': origin, 'Cache-Control': 'no-cache'}, timeout=15)
print(f'GET /scholarships: HTTP {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'  items={len(data.get("items", []))}, pagination={data.get("pagination", {})}')

# 3. Fetch scholarship 1
r = requests.get(f'{base}/scholarships/1', headers={'Origin': origin, 'Cache-Control': 'no-cache'}, timeout=15)
print(f'GET /scholarships/1: HTTP {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'  title={data.get("title", data.get("name", "?"))[:50]}')

# 4. Fetch scholarship 489
r = requests.get(f'{base}/scholarships/489', headers={'Origin': origin, 'Cache-Control': 'no-cache'}, timeout=15)
print(f'GET /scholarships/489: HTTP {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'  title={data.get("title", data.get("name", "?"))[:50]}')
    print(f'  eligibility={data.get("eligibility")!r}')

# 5. Fetch scholarship 490
r = requests.get(f'{base}/scholarships/490', headers={'Origin': origin, 'Cache-Control': 'no-cache'}, timeout=15)
print(f'GET /scholarships/490: HTTP {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'  title={data.get("title", data.get("name", "?"))[:50]}')
    print(f'  eligibility={data.get("eligibility")!r}')
