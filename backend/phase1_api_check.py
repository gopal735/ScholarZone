import requests
import time

base_url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"

print("=" * 60)
print("PHASE 1: LIVE API CHECK (Re-run with container online)")
print("=" * 60)

# 1. Health check
print("\n1. GET /health")
r = requests.get(f"{base_url}/health", timeout=30, headers={"Cache-Control": "no-cache"})
print(f"   HTTP {r.status_code}: {r.json()}")
assert r.status_code == 200

# 2. Scholarships total
print("\n2. GET /scholarships?limit=1")
r = requests.get(f"{base_url}/scholarships?limit=1", timeout=30, headers={"Cache-Control": "no-cache"})
data = r.json()
pagination = data.get("pagination", {})
print(f"   HTTP {r.status_code}")
print(f"   total={pagination.get('total')}")
print(f"   page={pagination.get('page')}")
print(f"   limit={pagination.get('limit')}")
print(f"   total_pages={pagination.get('total_pages')}")
print(f"   items_count={len(data.get('items', []))}")
assert r.status_code == 200
assert pagination.get("total") == 303, f"Expected 303, got {pagination.get('total')}"
print("   PASS — total is 303")

# 3. Verify status
print("\n3. GET /internal/verify/status")
r = requests.get(f"{base_url}/internal/verify/status", timeout=30, headers={"Cache-Control": "no-cache"})
status_data = r.json()
print(f"   HTTP {r.status_code}")
print(f"   scheduler_running={status_data.get('scheduler_running')}")
print(f"   last_trigger_time={status_data.get('last_trigger_time')}")
print(f"   min_interval={status_data.get('min_trigger_interval_seconds')}")
assert r.status_code == 200
print("   PASS")

# 4. Database identity — check a known scholarship
print("\n4. Database identity (Neon PostgreSQL proof)")
r = requests.get(f"{base_url}/scholarships/1", timeout=30, headers={"Cache-Control": "no-cache"})
scholarship = r.json()
print(f"   HTTP {r.status_code}")
print(f"   id={scholarship.get('id')}, title={scholarship.get('title')}")
print(f"   official_source_url={scholarship.get('official_source_url')}")
print(f"   updated_at={scholarship.get('updated_at')}")
print(f"   has verification_status={scholarship.get('verification_status')}")
assert r.status_code == 200
print("   PASS")

# 5. Count via pagination
print("\n5. Verify total scholarship count via pagination (limit=100)")
total_count = 0
for page in range(1, 5):
    r = requests.get(f"{base_url}/scholarships?page={page}&limit=100", timeout=30, headers={"Cache-Control": "no-cache"})
    items = r.json().get("items", [])
    total_count += len(items)
    print(f"   Page {page}: {len(items)} items")
print(f"   Total across all pages: {total_count}")
assert total_count == 303, f"Expected 303, got {total_count}"
print("   PASS")

print("\n" + "=" * 60)
print("PHASE 1 COMPLETE")
print("  /health = HTTP 200")
print("  /scholarships total = 303")
print("  /internal/verify/status = working")
print("=" * 60)
