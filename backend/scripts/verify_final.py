import urllib.request
import json

countries = ["Belgium", "Hungary", "Poland", "Czech Republic", "Portugal"]

all_ids = []
total = 0
for country in countries:
    encoded = country.replace(" ", "%20")
    url = f"http://localhost:8000/scholarships?country={encoded}"
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, dict):
            data = data.get("items", data.get("results", []))
        ids = [s["id"] for s in data]
        names = [s["name"] for s in data]
        unique_ids = len(set(ids)) == len(ids)
        unique_names = len(set(names)) == len(names)
        all_ids.extend(ids)
        total += len(data)
        print(f"{country}: {len(data)} records, unique IDs: {unique_ids}, unique names: {unique_names}")
        for s in data:
            print(f"  - [{s['id']}] {s['name'][:65]}")
    except Exception as e:
        print(f"{country}: ERROR - {e}")

print(f"\n=== API SUMMARY ===")
print(f"Total records across all 5 countries: {total}")
print(f"Unique IDs: {len(set(all_ids))}")
print(f"Duplicate IDs: {len(all_ids) - len(set(all_ids))}")

print(f"\n=== DATABASE URL UNIQUENESS CHECK ===")
try:
    url_all = "http://localhost:8000/scholarships"
    with urllib.request.urlopen(url_all) as resp:
        all_data = json.loads(resp.read().decode())
    if isinstance(all_data, dict):
        all_data = all_data.get("items", all_data.get("results", []))
    print(f"Total scholarships in DB: {len(all_data)}")
    # Check for duplicate IDs across full DB
    all_db_ids = [s["id"] for s in all_data]
    print(f"Unique IDs in DB: {len(set(all_db_ids))}")
    print(f"Duplicate IDs in DB: {len(all_db_ids) - len(set(all_db_ids))}")
except Exception as e:
    print(f"Could not fetch full DB via API: {e}")
    print("Note: API response does not include official_source_url field.")
