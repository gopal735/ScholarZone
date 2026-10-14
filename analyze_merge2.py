import json

# Load merge report
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\research\premium_card\merge_report.json') as f:
    report = json.load(f)

# Get unmatched research records
# The unmatched are those research records that didn't match any scholarship
# Let's look at the research index to see all 70 records
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\frontend\public\research\premium_card\output\index.json') as f:
    research_index = json.load(f)

print(f"Total research records: {len(research_index)}")

# Get matched research IDs
matched_research_ids = set()
for pair in report.get('matched_pairs', []):
    rid = pair.get('research_id')
    if rid:
        matched_research_ids.add(rid)

print(f"Matched research IDs: {matched_research_ids}")

# Find unmatched
unmatched_records = []
for r in research_index:
    data = r.get('data') or {}
    rid = data.get('id') or r.get('id')
    if rid not in matched_research_ids:
        unmatched_records.append(r)

print(f"Unmatched records: {len(unmatched_records)}")

for r in unmatched_records:
    data = r.get('data') or {}
    title = data.get('title') or r.get('source_title') or 'Unknown'
    provider = data.get('provider', {})
    provider_name = provider.get('name') if isinstance(provider, dict) else str(provider)
    location = data.get('location', {})
    country = location.get('host_country') or (location.get('study_countries', [None])[0] if location.get('study_countries') else 'Unknown')
    source_file = r.get('source_file', 'Unknown')
    print(f"\n  Title: {title}")
    print(f"  Provider: {provider_name}")
    print(f"  Country: {country}")
    print(f"  Source file: {source_file}")
    print(f"  Research ID: {data.get('id') or r.get('id')}")

# Now let's check which of the 14 unique matched IDs got updated in the SQL
print("\n=== SQL MIGRATION UPDATES ===")
sql_updates = {}
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\migrations\merge_premium_card_research.sql') as f:
    for line in f:
        if line.startswith('UPDATE scholarships'):
            # Parse: UPDATE scholarships SET col = 'val' WHERE id = 123;
            parts = line.strip().split()
            sch_id = int(parts[-1].rstrip(';'))
            col = parts[3]
            if sch_id not in sql_updates:
                sql_updates[sch_id] = []
            sql_updates[sch_id].append(col)

for sch_id, cols in sql_updates.items():
    print(f"  ID {sch_id}: {len(cols)} updates - {cols}")

# Check all 14 unique matched IDs
unique_matched_ids = set()
for pair in report.get('matched_pairs', []):
    sch_id = pair.get('scholarship_id')
    if sch_id:
        unique_matched_ids.add(sch_id)

print(f"\nUnique matched IDs: {sorted(unique_matched_ids)}")
print(f"IDs updated in SQL: {sorted(sql_updates.keys())}")
print(f"IDs NOT updated in SQL: {sorted(unique_matched_ids - set(sql_updates.keys()))}")

# Count total field updates in SQL
total_sql_updates = sum(len(v) for v in sql_updates.values())
print(f"Total SQL field updates: {total_sql_updates}")

# Now let's verify what the verification report says
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\research\premium_card\merge_verification_report.json') as f:
    verify = json.load(f)
print(f"\n=== VERIFICATION REPORT ===")
for k, v in verify.items():
    print(f"  {k}: {v}")