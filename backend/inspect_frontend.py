import requests
import re

url = 'https://gopal735.github.io/ScholarZone/'
r = requests.get(url, timeout=15, headers={'Cache-Control': 'no-cache'})
print('HTML content:')
print(r.text)
print('---')

# Find script src
scripts = re.findall(r'<script[^>]+src=["\'](.*?)["\']', r.text)
print(f'Script tags: {scripts}')
for s in scripts:
    full = requests.compat.urljoin(url, s)
    print(f'Fetching: {full}')
    sr = requests.get(full, timeout=15)
    print(f'  Status: {sr.status_code}, Size: {len(sr.text)} bytes')
    if 'scholarzone-api-2ee2d' in sr.text:
        print('  -> Contains production API URL')
    if 'localhost' in sr.text or '127.0.0.1' in sr.text:
        print('  -> WARNING: Contains localhost/127.0.0.1')
