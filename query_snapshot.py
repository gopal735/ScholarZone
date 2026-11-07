import sqlite3
import json

# Read snapshot with proper encoding
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\frontend\public\scholarships-snapshot.json', 'r', encoding='utf-8') as f:
    snapshot = json.load(f)

print(f"Snapshot meta source_record_count: {snapshot['meta']['source_record_count']}")
print(f"Snapshot meta public_record_count: {snapshot['meta']['public_record_count']}")
print(f"Snapshot stats total: {snapshot['stats']['total']}")
print(f"Actual scholarships in snapshot: {len(snapshot['scholarships'])}")

# Count sitemap URLs
import xml.etree.ElementTree as ET
tree = ET.parse(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\frontend\public\sitemap.xml')
root = tree.getroot()
ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
urls = root.findall('.//ns:url/ns:loc', ns)
scholarship_urls = [u for u in urls if '/scholarships/' in u.text and u.text.count('/scholarships/') == 1 and not u.text.endswith('/scholarships')]
print(f"\nSitemap total URLs: {len(urls)}")
print(f"Sitemap scholarship URLs: {len(scholarship_urls)}")

# Extract IDs from sitemap
sitemap_ids = set()
for u in scholarship_urls:
    try:
        id_str = u.text.split('/scholarships/')[-1]
        if id_str.isdigit():
            sitemap_ids.add(int(id_str))
    except:
        pass
print(f"Unique scholarship IDs in sitemap: {len(sitemap_ids)}")
print(f"Sitemap ID range: {min(sitemap_ids)} - {max(sitemap_ids)}")

# Check DB
conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()
cursor.execute("SELECT id FROM scholarships")
db_ids = set(r[0] for r in cursor.fetchall())

missing_from_sitemap = db_ids - sitemap_ids
extra_in_sitemap = sitemap_ids - db_ids
print(f"\nDB IDs missing from sitemap: {len(missing_from_sitemap)}")
if missing_from_sitemap:
    print(f"  Missing: {sorted(missing_from_sitemap)[:30]}...")
print(f"Extra IDs in sitemap: {len(extra_in_sitemap)}")
if extra_in_sitemap:
    print(f"  Extra: {sorted(extra_in_sitemap)}")

# Check snapshot IDs
snapshot_ids = set(s['id'] for s in snapshot['scholarships'])
print(f"\nSnapshot IDs count: {len(snapshot_ids)}")
missing_from_snapshot = db_ids - snapshot_ids
extra_in_snapshot = snapshot_ids - db_ids
print(f"DB IDs missing from snapshot: {len(missing_from_snapshot)}")
if missing_from_snapshot:
    print(f"  Missing: {sorted(missing_from_snapshot)[:30]}...")
print(f"Extra IDs in snapshot: {len(extra_in_snapshot)}")
if extra_in_snapshot:
    print(f"  Extra: {sorted(extra_in_snapshot)}")