import requests
import time

base = 'https://scholarzone-api-2ee2d.containers.snapdeploy.app'
origin = 'https://gopal735.github.io'

# Test CORS preflight
for path in ['/health', '/scholarships/stats', '/scholarships']:
    url = base + path
    r = requests.options(url, headers={
        'Origin': origin,
        'Access-Control-Request-Method': 'GET',
        'Cache-Control': 'no-cache',
    }, timeout=15)
    print(f'OPTIONS {path}: HTTP {r.status_code}')
    print(f'  ACAO: {r.headers.get("Access-Control-Allow-Origin", "MISSING")}')
    print(f'  ACAC: {r.headers.get("Access-Control-Allow-Credentials", "MISSING")}')
    print(f'  ACAM: {r.headers.get("Access-Control-Allow-Methods", "MISSING")}')
    print()
    time.sleep(0.5)

# Test actual GET with Origin header
for path in ['/scholarships/1', '/scholarships/489', '/scholarships/490']:
    url = base + path
    r = requests.get(url, headers={'Origin': origin, 'Cache-Control': 'no-cache'}, timeout=15)
    print(f'GET {path}: HTTP {r.status_code}')
    print(f'  ACAO: {r.headers.get("Access-Control-Allow-Origin", "MISSING")}')
    print(f'  ACAC: {r.headers.get("Access-Control-Allow-Credentials", "MISSING")}')
    time.sleep(0.5)
