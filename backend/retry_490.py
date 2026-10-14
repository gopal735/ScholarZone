import requests
import time

base = 'https://scholarzone-api-2ee2d.containers.snapdeploy.app'

# Retry 490 a few times
for i in range(5):
    r = requests.get(f'{base}/scholarships/490', timeout=15, headers={'Cache-Control':'no-cache'})
    print(f'Attempt {i+1}: HTTP {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        print(f'  id={data.get("id")}, title={data.get("title", data.get("name", "?"))[:60]}')
        print(f'  eligibility={data.get("eligibility")!r}')
        print(f'  application_method={data.get("application_method")!r}')
        break
    time.sleep(2)
