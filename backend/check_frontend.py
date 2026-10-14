import requests
import json

# Check frontend homepage
url = 'https://gopal735.github.io/ScholarZone/'
r = requests.get(url, timeout=15, headers={'Cache-Control': 'no-cache'})
print(f'Frontend homepage: HTTP {r.status_code}')
print(f'Content-Type: {r.headers.get("Content-Type")}')
print(f'Body length: {len(r.text)}')

# Look for API base URL in the HTML/JS
if 'scholarzone-api-2ee2d' in r.text:
    print('Found production API URL in frontend')
elif 'localhost' in r.text:
    print('WARNING: Found localhost in frontend')
elif '127.0.0.1' in r.text:
    print('WARNING: Found 127.0.0.1 in frontend')

# Check for React/SPA indicators
if '<div id="root">' in r.text or 'main.jsx' in r.text:
    print('SPA root found')

# Try to get main JS
for asset in ['/assets/main.js', '/main.js', '/static/js/main.js', '/assets/index.js']:
    ar = requests.get(f'https://gopal735.github.io/ScholarZone{asset}', timeout=10)
    if ar.status_code == 200:
        print(f'Found JS at {asset}: {len(ar.text)} bytes')
        if 'scholarzone-api-2ee2d' in ar.text:
            print(f'  -> Contains production API URL')
        if '/api' in ar.text:
            print(f'  -> Contains relative /api path')
        break
