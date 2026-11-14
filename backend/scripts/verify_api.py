"""Verify API returns for each country."""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.outbound_security import secure_get

countries = ['Belgium', 'Hungary', 'Poland', 'Czech Republic', 'Portugal']
base_url = 'http://localhost:8000/api/scholarships'

print('=== API VERIFICATION ===')
for country in countries:
    try:
        r = secure_get(f'{base_url}?country={country}')
        if r.status_code == 200:
            data = r.json()
            count = len(data.get('scholarships', []))
            print(f'{country}: {count} scholarships returned')
            # Print titles
            for s in data.get('scholarships', [])[:3]:
                print(f'  - {s.get("title", "N/A")}')
        else:
            print(f'{country}: HTTP {r.status_code}')
    except Exception as e:
        print(f'{country}: Error - {e}')

# Test total count
try:
    r = secure_get(base_url)
    if r.status_code == 200:
        data = r.json()
        print(f'\nTotal scholarships in API: {data.get("total", "N/A")}')
except Exception as e:
    print(f'Error: {e}')
