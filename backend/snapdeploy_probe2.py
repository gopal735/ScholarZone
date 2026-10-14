import requests

base = 'https://snapdeploy.dev'
subdomain = 'scholarzone-api-2ee2d'
container_id = '777fe5ec-4f6d-4f73-b809-1d2ee49097fd'

endpoints = [
    ('POST', f'/api/public/containers/{subdomain}/restart', {}),
    ('POST', f'/api/public/containers/{subdomain}/wake', {}),
    ('GET', f'/api/public/containers/{subdomain}', None),
    ('GET', f'/api/public/containers/{subdomain}/status', None),
    ('GET', f'/api/public/containers/{subdomain}/builds', None),
    ('POST', f'/api/v1/containers/{container_id}/rebuild', {}),
    ('POST', f'/api/v1/containers/{container_id}/redeploy', {}),
]

for method, ep, payload in endpoints:
    url = base + ep
    try:
        if method == 'GET':
            r = requests.get(url, timeout=15, headers={'Accept': 'application/json'})
        else:
            r = requests.request(method, url, timeout=15, json=payload, headers={'Accept': 'application/json'})
        ct = r.headers.get('Content-Type', '')[:40]
        print(f'{method} {ep}: {r.status_code} CT={ct}')
        if r.status_code == 200:
            print(f'  Body: {r.text[:400]}')
        elif r.status_code not in (404, 405):
            print(f'  Body: {r.text[:200]}')
    except Exception as e:
        print(f'{method} {ep}: Error - {e}')
    print()
