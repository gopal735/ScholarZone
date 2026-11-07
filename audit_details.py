import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('backend/scholarzone.db')
cursor = conn.cursor()

# Check fully_funded=True records for evidence
print("=" * 80)
print("FULLY_FUNDED=TRUE RECORDS - EVIDENCE CHECK")
print("=" * 80)

cursor.execute('''
    SELECT id, title, country, fully_funded, tuition_coverage, living_cost_coverage, 
           travel_coverage, funding_amount, funding_currency, funding_period, funding_details
    FROM scholarships
    WHERE fully_funded = 1
''')
ff_records = cursor.fetchall()

no_evidence = []
with_evidence = []
for r in ff_records:
    (id_, title, country, ff, tuition, living, travel, amt, curr, period, fdet) = r
    has_evidence = False
    evidence_type = []
    if tuition == 1 and living == 1:
        has_evidence = True
        evidence_type.append("tuition+living coverage flags")
    if fdet:
        try:
            det = json.loads(fdet) if isinstance(fdet, str) else fdet
            if isinstance(det, list) and len(det) > 0:
                has_evidence = True
                evidence_type.append("funding_details JSON")
        except:
            pass
    if has_evidence:
        with_evidence.append((id_, title, country, "; ".join(evidence_type)))
    else:
        no_evidence.append((id_, title, country))

print(f"Total fully_funded=True: {len(ff_records)}")
print(f"With evidence: {len(with_evidence)}")
print(f"WITHOUT EVIDENCE (VIOLATION): {len(no_evidence)}")
print()
if no_evidence:
    print("RECORDS WITH fully_funded=True BUT NO EVIDENCE:")
    for r in no_evidence[:50]:
        print(f"  ID {r[0]:>4}: {r[1][:50]:<50} | {r[2]}")
    if len(no_evidence) > 50:
        print(f"  ... and {len(no_evidence) - 50} more")

print()
print("RECORDS WITH EVIDENCE:")
for r in with_evidence[:20]:
    print(f"  ID {r[0]:>4}: {r[1][:50]:<50} | {r[2]} | Evidence: {r[3]}")
if len(with_evidence) > 20:
    print(f"  ... and {len(with_evidence) - 20} more")

# Check snapshot vs database field agreement
print("\n" + "=" * 80)
print("SNAPSHOT vs DATABASE CONSISTENCY CHECK")
print("=" * 80)

# Load snapshot
with open('frontend/public/scholarships-snapshot.json', 'r', encoding='utf-8') as f:
    snapshot = json.load(f)

snap_by_id = {s['id']: s for s in snapshot['scholarships']}

cursor.execute('SELECT id, title, country, fully_funded, funding, deadline_display, official_source, official_source_url FROM scholarships')
db_records = cursor.fetchall()

mismatches = 0
for r in db_records:
    id_, title, country, ff, funding, deadline, osrc, osurl = r
    if id_ in snap_by_id:
        s = snap_by_id[id_]
        # Check key fields
        if s.get('fully_funded') != (ff == 1):
            mismatches += 1
            print(f"  ID {id_}: fully_funded mismatch - DB={ff}, Snapshot={s.get('fully_funded')}")
        if s.get('funding') != funding:
            mismatches += 1
            print(f"  ID {id_}: funding mismatch - DB={funding[:40]}, Snapshot={s.get('funding')[:40]}")
        if s.get('deadline_display') != deadline:
            mismatches += 1
            print(f"  ID {id_}: deadline mismatch - DB={deadline[:40]}, Snapshot={s.get('deadline_display')[:40]}")
        if s.get('official_source') != osrc:
            mismatches += 1
            print(f"  ID {id_}: official_source mismatch - DB={osrc}, Snapshot={s.get('official_source')}")
        if s.get('official_source_url') != osurl:
            mismatches += 1
            print(f"  ID {id_}: official_source_url mismatch - DB={osurl}, Snapshot={s.get('official_source_url')}")

print(f"\nTotal field mismatches: {mismatches}")

# Check region classification using taxonomy.py COUNTRY_REGION
print("\n" + "=" * 80)
print("REGION CLASSIFICATION (using taxonomy.py COUNTRY_REGION)")
print("=" * 80)

# Load taxonomy
from backend.app.services.taxonomy import COUNTRY_REGION

cursor.execute('SELECT id, title, country, region FROM scholarships')
reg_records = cursor.fetchall()

region_counts = {}
mismatch_region = 0
missing_region = 0
for r in reg_records:
    id_, title, country, region = r
    canonical_country = country
    # Simple canonicalization - just use as-is for now
    expected_region = COUNTRY_REGION.get(canonical_country)
    if expected_region:
        region_counts[expected_region] = region_counts.get(expected_region, 0) + 1
        if region and region != expected_region:
            mismatch_region += 1
            print(f"  ID {id_}: region mismatch - stored='{region}', expected='{expected_region}' (country={country})")
        elif not region:
            missing_region += 1
    else:
        region_counts['UNKNOWN'] = region_counts.get('UNKNOWN', 0) + 1
        if not region:
            missing_region += 1

print(f"Region distribution (by COUNTRY_REGION):")
for reg, cnt in sorted(region_counts.items(), key=lambda x: -x[1]):
    print(f"  {reg}: {cnt}")
print(f"\nRecords with region mismatch: {mismatch_region}")
print(f"Records missing region field: {missing_region}")

# Check excluded regions in current catalogue
print("\n" + "=" * 80)
print("EXCLUDED REGION RECORDS IN CURRENT CATALOGUE")
print("=" * 80)

excluded_regions = ["Middle East", "Latin America"]
excluded_count = 0
for reg, cnt in region_counts.items():
    if reg in excluded_regions:
        excluded_count += cnt
        print(f"  {reg}: {cnt} records (EXCLUDED per scope)")

print(f"\nTotal records in EXCLUDED regions: {excluded_count}")

conn.close()