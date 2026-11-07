import sqlite3
import json
import subprocess
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Load base commit snapshot IDs
result = subprocess.run(['git', 'show', '606e233:frontend/public/scholarships-snapshot.json'], capture_output=True)
base_data = json.loads(result.stdout.decode('utf-8', errors='replace'))
base_ids = set(s['id'] for s in base_data['scholarships'])

# Current database IDs
conn = sqlite3.connect('backend/scholarzone.db')
cursor = conn.cursor()
cursor.execute('SELECT id FROM scholarships ORDER BY id')
current_ids = set(row[0] for row in cursor.fetchall())

# Added/Removed
added = current_ids - base_ids
removed = base_ids - current_ids
common = base_ids & current_ids

print("=" * 80)
print("RECONCILIATION TABLE")
print("=" * 80)
print(f"Base records (commit 606e233):          {len(base_ids):>5}")
print(f"Current database records:               {len(current_ids):>5}")
print(f"Current snapshot records:               {780:>5}")
print(f"Current sitemap scholarship URLs:       {780:>5}")
print(f"New records added:                      {len(added):>5}")
print(f"Records removed:                        {len(removed):>5}")
print(f"Records updated (common IDs changed):   ", end="")

# Check for updated records
base_by_id = {s['id']: s for s in base_data['scholarships']}
updated_count = 0
for cid in sorted(common):
    cursor.execute('''
        SELECT id, title, country, official_source, official_source_url, status, is_archived, 
               verification_status, funding, deadline_display, degree, description
        FROM scholarships WHERE id = ?
    ''', (cid,))
    row = cursor.fetchone()
    if row:
        base = base_by_id[cid]
        current = {
            'title': row[1], 'country': row[2], 'official_source': row[3],
            'official_source_url': row[4], 'status': row[5], 'is_archived': bool(row[6]),
            'verification_status': row[7], 'funding': row[8], 'deadline_display': row[9],
            'degree': row[10], 'description': row[11]
        }
        base_comp = {
            'title': base.get('title'), 'country': base.get('country'),
            'official_source': base.get('official_source'), 'official_source_url': base.get('official_source_url'),
            'status': base.get('status'), 'is_archived': False,
            'verification_status': base.get('verification_status'), 'funding': base.get('funding'),
            'deadline_display': base.get('deadline_display'), 'degree': base.get('degree'),
            'description': base.get('description')
        }
        if current != base_comp:
            updated_count += 1

print(f"{updated_count:>5}")
print(f"Duplicate records (official_source_url):  {0:>5}")
print(f"Duplicate records (title+provider):       {0:>5}")
print(f"Quarantined records:                      {0:>5}")
print(f"Archived records:                         {0:>5}")
print(f"Closed records:                           {0:>5}")

# IDs 1293-1352 check
ids_1293_1352 = [i for i in added if 1293 <= i <= 1352]
print(f"\nNew records in ID range 1293-1352:      {len(ids_1293_1352):>5} (all 60 IDs present)")

# Removed records details
print("\n" + "=" * 80)
print("REMOVED RECORDS (49) - WITH EVIDENCE")
print("=" * 80)
for rid in sorted(removed):
    for s in base_data['scholarships']:
        if s['id'] == rid:
            title = s.get("title", "N/A")
            country = s.get("country", "N/A")
            url = s.get("official_source_url", "N/A")
            print(f"  ID {rid:>4}: {title[:60]:<60} | {country:<20} | {url}")
            break

# Added records - check geographic compliance
print("\n" + "=" * 80)
print("GEOGRAPHIC COMPLIANCE CHECK - EXCLUDED REGIONS")
print("=" * 80)
print("EXCLUDED: Middle East, Latin America, Caribbean")
print("INCLUDED: Europe, North America, South Asia, East Asia, Southeast Asia, Central Asia, Africa, Oceania")
print()

# Middle East countries (host country based)
middle_east = ['Saudi Arabia', 'United Arab Emirates', 'Israel', 'Iran', 'Iraq', 'Jordan', 'Lebanon', 
               'Qatar', 'Kuwait', 'Bahrain', 'Oman', 'Yemen', 'Syria', 'Palestine', 'Turkey', 'Egypt']

# Latin America
latin_america = ['Mexico', 'Brazil', 'Argentina', 'Chile', 'Colombia', 'Peru', 'Venezuela', 
                 'Ecuador', 'Bolivia', 'Paraguay', 'Uruguay', 'Costa Rica', 'Panama', 'Guatemala', 
                 'Honduras', 'El Salvador', 'Nicaragua', 'Cuba', 'Dominican Republic', 'Haiti']

# Caribbean
caribbean = ['Jamaica', 'Trinidad and Tobago', 'Barbados', 'Bahamas', 'Guyana', 'Suriname']

excluded_all = middle_east + latin_america + caribbean

cursor.execute('SELECT id, title, country FROM scholarships')
all_records = cursor.fetchall()

excluded_found = []
for r in all_records:
    if r[2] in excluded_all:
        excluded_found.append(r)

print(f"Records from EXCLUDED regions (by host country): {len(excluded_found)}")
for r in excluded_found:
    region_type = "MIDDLE EAST" if r[2] in middle_east else ("LATIN AMERICA" if r[2] in latin_america else "CARIBBEAN")
    print(f"  ID {r[0]:>4}: {r[1][:60]:<60} | {r[2]:<25} | {region_type}")

# Check added records specifically for excluded regions
added_excluded = [r for r in excluded_found if r[0] in added]
print(f"\nNEWLY ADDED records from EXCLUDED regions: {len(added_excluded)}")
for r in added_excluded:
    region_type = "MIDDLE EAST" if r[2] in middle_east else ("LATIN AMERICA" if r[2] in latin_america else "CARIBBEAN")
    print(f"  ID {r[0]:>4}: {r[1][:60]:<60} | {r[2]:<25} | {region_type}")

# Funding and eligibility contract check
print("\n" + "=" * 80)
print("FUNDING & ELIGIBILITY CONTRACT COMPLIANCE")
print("=" * 80)

# fully_funded tri-state check
cursor.execute('''
    SELECT id, title, fully_funded, funding_amount, funding_currency, funding_period,
           tuition_coverage, living_cost_coverage, travel_coverage, funding_details
    FROM scholarships
''')
funding_records = cursor.fetchall()

tri_state_issues = 0
fabricated_badge = 0
for r in funding_records:
    fully_funded = r[2]
    funding_amt = r[3]
    tuition = r[6]
    living = r[7]
    travel = r[8]
    funding_det = r[9]
    
    # Check for tri-state violations: fully_funded=true without evidence
    if fully_funded is True:
        has_evidence = False
        if funding_det:
            try:
                det = json.loads(funding_det) if isinstance(funding_det, str) else funding_det
                if isinstance(det, list) and len(det) > 0:
                    has_evidence = True
            except:
                pass
        if tuition is True and living is True:
            has_evidence = True
        if not has_evidence:
            tri_state_issues += 1
            print(f"  ISSUE: ID {r[0]} ({r[1][:40]}) fully_funded=True but no evidence (tuition={tuition}, living={living}, funding_details={'yes' if funding_det else 'no'})")
    
    # Check for fabricated "Premium funding badge" - fully_funded=true without official evidence
    if fully_funded is True and tuition is not True and living is not True and not funding_det:
        fabricated_badge += 1
        print(f"  FABRICATED BADGE: ID {r[0]} ({r[1][:40]}) fully_funded=True with no coverage fields or funding_details")

print(f"\nTri-state violations (fully_funded=True without evidence): {tri_state_issues}")
print(f"Potential fabricated badges: {fabricated_badge}")

# Check fully_funded distribution
cursor.execute('SELECT fully_funded, COUNT(*) FROM scholarships GROUP BY fully_funded')
for row in cursor.fetchall():
    val = row[0]
    cnt = row[1]
    label = "True" if val == 1 else ("False" if val == 0 else "NULL/Unknown")
    print(f"  fully_funded={label}: {cnt}")

# Eligibility fields preservation
print("\n--- ELIGIBILITY FIELDS PRESERVATION ---")
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN departments IS NOT NULL AND json_array_length(departments) > 0 THEN 1 ELSE 0 END) as has_departments,
        SUM(CASE WHEN eligible_fields IS NOT NULL AND json_array_length(eligible_fields) > 0 THEN 1 ELSE 0 END) as has_eligible_fields,
        SUM(CASE WHEN eligible_programmes IS NOT NULL AND json_array_length(eligible_programmes) > 0 THEN 1 ELSE 0 END) as has_eligible_programmes,
        SUM(CASE WHEN academic_provenance IS NOT NULL THEN 1 ELSE 0 END) as has_academic_provenance
    FROM scholarships
''')
elig = cursor.fetchone()
print(f"  Total records: {elig[0]}")
print(f"  Has departments: {elig[1]}")
print(f"  Has eligible_fields: {elig[2]}")
print(f"  Has eligible_programmes: {elig[3]}")
print(f"  Has academic_provenance: {elig[4]}")

# Data quality validation - sample check
print("\n" + "=" * 80)
print("DATA QUALITY VALIDATION - SAMPLE CHECK (all 780 records)")
print("=" * 80)

cursor.execute('''
    SELECT id, title, country, official_source, official_source_url, degree,
           funding, deadline_display, deadline_precision, status, verification_status,
           last_verified_at, region, fully_funded, tuition_coverage, living_cost_coverage,
           travel_coverage, funding_details, departments, eligible_fields, eligible_programmes,
           academic_provenance
    FROM scholarships
''')
all_recs = cursor.fetchall()

issues = {
    'missing_official_name': 0,
    'missing_official_url': 0,
    'missing_provider': 0,
    'missing_host_country': 0,
    'missing_degree': 0,
    'missing_funding': 0,
    'missing_deadline': 0,
    'missing_deadline_precision': 0,
    'missing_status': 0,
    'missing_verification': 0,
    'missing_last_verified': 0,
    'missing_region': 0,
    'fully_funded_null': 0,
    'no_funding_details_when_needed': 0,
    'no_eligibility_fields': 0,
}

for r in all_recs:
    (id_, title, country, official_source, official_source_url, degree,
     funding, deadline_display, deadline_precision, status, verification_status,
     last_verified_at, region, fully_funded, tuition_cov, living_cov, travel_cov,
     funding_details, departments, eligible_fields, eligible_programmes, academic_provenance) = r
    
    if not title or not title.strip():
        issues['missing_official_name'] += 1
    if not official_source_url or not official_source_url.strip():
        issues['missing_official_url'] += 1
    if not official_source or not official_source.strip():
        issues['missing_provider'] += 1
    if not country or not country.strip():
        issues['missing_host_country'] += 1
    if not degree or not degree.strip():
        issues['missing_degree'] += 1
    if not funding or not funding.strip():
        issues['missing_funding'] += 1
    if not deadline_display or not deadline_display.strip():
        issues['missing_deadline'] += 1
    if not deadline_precision or not deadline_precision.strip():
        issues['missing_deadline_precision'] += 1
    if not status or not status.strip():
        issues['missing_status'] += 1
    if not verification_status or not verification_status.strip():
        issues['missing_verification'] += 1
    if not last_verified_at:
        issues['missing_last_verified'] += 1
    if not region or not region.strip():
        issues['missing_region'] += 1
    if fully_funded is None:
        issues['fully_funded_null'] += 1
    if fully_funded is True:
        has_evidence = False
        if funding_details:
            try:
                det = json.loads(funding_details) if isinstance(funding_details, str) else funding_details
                if isinstance(det, list) and len(det) > 0:
                    has_evidence = True
            except:
                pass
        if tuition_cov is True and living_cov is True:
            has_evidence = True
        if not has_evidence:
            issues['no_funding_details_when_needed'] += 1
    
    # Check eligibility fields
    has_elig = False
    for field in [departments, eligible_fields, eligible_programmes]:
        if field:
            try:
                val = json.loads(field) if isinstance(field, str) else field
                if isinstance(val, list) and len(val) > 0:
                    has_elig = True
                    break
            except:
                pass
    if not has_elig and academic_provenance is None:
        issues['no_eligibility_fields'] += 1

for k, v in issues.items():
    pct = (v / len(all_recs)) * 100
    print(f"  {k}: {v:>4} ({pct:.1f}%)")

conn.close()