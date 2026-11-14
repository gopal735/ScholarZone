"""Verify API returns for each country."""

from __future__ import annotations

import sys
import json

from scripts.local_smoke_http import open_local_smoke_url

countries = ["Belgium", "Hungary", "Poland", "Czech Republic", "Portugal"]
base_url = "http://127.0.0.1:8000/api/scholarships"

print("=== API VERIFICATION ===")
for country in countries:
    try:
        with open_local_smoke_url(
            f"{base_url}?country={country}",
            allowed_ports={8000},
        ) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                count = len(data.get("scholarships", []))
                print(f"{country}: {count} scholarships returned")
                # Print titles
                for s in data.get("scholarships", [])[:3]:
                    print(f"  - {s.get('title', 'N/A')}")
            else:
                print(f"{country}: HTTP {resp.status}")
    except Exception as e:
        print(f"{country}: Error - {e}")

# Test total count
try:
    with open_local_smoke_url(base_url, allowed_ports={8000}) as resp:
        if resp.status == 200:
            data = json.loads(resp.read().decode())
            print(f"\nTotal scholarships in API: {data.get('total', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
