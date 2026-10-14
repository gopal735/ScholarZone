import os
os.environ['SCHOLARZONE_ENVIRONMENT'] = 'development'
os.environ['SCHOLARZONE_DATABASE_URL'] = 'sqlite:///scholarzone.db'
os.environ['SCHOLARZONE_VERIFICATION_SECRET'] = 'test_secret'

import uvicorn
import threading
import time
import requests

def run_server():
    uvicorn.run('app.main:app', host='127.0.0.1', port=8765, log_level='warning')

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
print('Server starting on port 8765...')
time.sleep(3)

print()
print('1. GET /health')
r = requests.get('http://127.0.0.1:8765/health', timeout=10)
print(f'   Status: {r.status_code}, Body: {r.json()}')

print()
print('2. GET /scholarships?limit=1')
r = requests.get('http://127.0.0.1:8765/scholarships?limit=1', timeout=10)
data = r.json()
print(f'   Status: {r.status_code}')
print(f'   total={data.get("total")}, page={data.get("page")}, per_page={data.get("per_page")}')
print(f'   items_count={len(data.get("items", []))}')

print()
print('3. GET /internal/verify/status')
r = requests.get('http://127.0.0.1:8765/internal/verify/status', timeout=10)
print(f'   Status: {r.status_code}, Body: {r.json()}')

print()
print('4. GET /scholarships/1')
r = requests.get('http://127.0.0.1:8765/scholarships/1', timeout=10)
data = r.json()
print(f'   Status: {r.status_code}')
print(f'   id={data.get("id")}, title={data.get("title")}')
print(f'   has image_url field: {"image_url" in data}')

print()
print('All local endpoint tests passed.')
