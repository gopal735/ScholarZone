import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db')
cursor = conn.cursor()

# Archived count
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived = 1")
print(f"Archived (is_archived=1): {cursor.fetchone()[0]}")

# Check if there's a quarantined equivalent
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE is_verified = 0")
print(f"Not verified (is_verified=0): {cursor.fetchone()[0]}")

# Check all status values with counts
cursor.execute("SELECT status, COUNT(*) FROM scholarships GROUP BY status")
print("\nStatus counts:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

cursor.execute("SELECT verification_status, COUNT(*) FROM scholarships GROUP BY verification_status")
print("\nVerification status counts:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check for duplicates by official_source_url
cursor.execute("""
    SELECT official_source_url, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
    FROM scholarships
    WHERE official_source_url IS NOT NULL AND official_source_url != ''
    GROUP BY official_source_url
    HAVING COUNT(*) > 1
""")
dupes_url = cursor.fetchall()
print(f"\nDuplicate official_source_url: {len(dupes_url)}")
for d in dupes_url:
    print(f"  URL: {d[0][:80]}... count={d[1]}, IDs={d[2]}")

# Check for duplicates by title + country (canonical)
cursor.execute("""
    SELECT title, country, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
    FROM scholarships
    GROUP BY title, country
    HAVING COUNT(*) > 1
""")
dupes_title = cursor.fetchall()
print(f"\nDuplicate title+country: {len(dupes_title)}")
for d in dupes_title:
    print(f"  {d[0]} / {d[1]}: count={d[2]}, IDs={d[3]}")

# Count by country
cursor.execute("SELECT country, COUNT(*) FROM scholarships GROUP BY country ORDER BY COUNT(*) DESC")
countries = cursor.fetchall()
print(f"\nTotal countries: {len(countries)}")
print("Top 20 countries:")
for c in countries[:20]:
    print(f"  {c[0]}: {c[1]}")

# Check fully_funded distribution
cursor.execute("SELECT fully_funded, COUNT(*) FROM scholarships GROUP BY fully_funded")
print("\nFully funded distribution:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check funding_details
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE funding_details IS NOT NULL AND funding_details != ''")
print(f"\nRecords with funding_details: {cursor.fetchone()[0]}")

# Check academic_provenance
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE academic_provenance IS NOT NULL AND academic_provenance != ''")
print(f"Records with academic_provenance: {cursor.fetchone()[0]}")

# Check eligible_fields
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE eligible_fields IS NOT NULL AND eligible_fields != '[]'")
print(f"Records with eligible_fields: {cursor.fetchone()[0]}")

# Check eligible_programmes
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE eligible_programmes IS NOT NULL AND eligible_programmes != '[]'")
print(f"Records with eligible_programmes: {cursor.fetchone()[0]}")

# Check departments
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE departments IS NOT NULL AND departments != '[]'")
print(f"Records with departments: {cursor.fetchone()[0]}")

# Check last_verified_at
cursor.execute("SELECT last_verified_at, COUNT(*) FROM scholarships GROUP BY last_verified_at ORDER BY COUNT(*) DESC LIMIT 10")
print("\nLast verified at (top 10):")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check IDs 1-728 vs 729-1352 (base vs added)
cursor.execute("SELECT COUNT(*) FROM scholarships WHERE id <= 728")
print(f"\nIDs 1-728 (base range): {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM scholarships WHERE id > 728")
print(f"IDs 729+ (added): {cursor.fetchone()[0]}")

# Check the snapshot file count
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\frontend\public\scholarships-snapshot.json', 'r') as f:
    snapshot = json.load(f)
print(f"\nSnapshot meta source_record_count: {snapshot['meta']['source_record_count']}")
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

# Check which DB IDs are missing from sitemap
cursor.execute("SELECT id FROM scholarships")
db_ids = set(r[0] for r in cursor.fetchall())
missing_from_sitemap = db_ids - sitemap_ids
extra_in_sitemap = sitemap_ids - db_ids
print(f"DB IDs missing from sitemap: {len(missing_from_sitemap)}")
if missing_from_sitemap:
    print(f"  Missing: {sorted(missing_from_sitemap)[:20]}...")
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
    print(f"  Missing: {sorted(missing_from_snapshot)[:20]}...")
print(f"Extra IDs in snapshot: {len(extra_in_snapshot)}")
if extra_in_snapshot:
    print(f"  Extra: {sorted(extra_in_snapshot)}")