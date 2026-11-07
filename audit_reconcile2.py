import sqlite3
import json
import subprocess
import sys

# Load base commit snapshot IDs
result = subprocess.run(['git', 'show', '606e233:frontend/public/scholarships-snapshot.json'], capture_output=True)
base_data = json.loads(result.stdout.decode('utf-8', errors='replace'))
base_ids = set(s['id'] for s in base_data['scholarships'])
print(f'Base IDs count: {len(base_ids)}')
print(f'Base ID range: {min(base_ids)} - {max(base_ids)}')

# Current database IDs
conn = sqlite3.connect('backend/scholarzone.db')
cursor = conn.cursor()
cursor.execute('SELECT id FROM scholarships ORDER BY id')
current_ids = set(row[0] for row in cursor.fetchall())
print(f'Current IDs count: {len(current_ids)}')
print(f'Current ID range: {min(current_ids)} - {max(current_ids)}')

# Added IDs
added = current_ids - base_ids
print(f'\nAdded IDs ({len(added)}): {sorted(added)}')

# Removed IDs
removed = base_ids - current_ids
print(f'Removed IDs ({len(removed)}): {sorted(removed)}')

# For removed IDs, get details from base snapshot
print('\n--- REMOVED RECORDS DETAILS ---')
for rid in sorted(removed):
    for s in base_data['scholarships']:
        if s['id'] == rid:
            title = s.get("title", "N/A").encode('ascii', 'replace').decode()
            country = s.get("country", "N/A")
            url = s.get("official_source_url", "N/A")
            print(f'  ID {rid}: {title} | {country} | {url}')
            break

# For added IDs, get details from current database
print('\n--- ADDED RECORDS DETAILS (first 30) ---')
for aid in sorted(list(added))[:30]:
    cursor.execute('SELECT id, title, country, official_source, official_source_url, status, is_archived, verification_status FROM scholarships WHERE id = ?', (aid,))
    row = cursor.fetchone()
    if row:
        title = row[1].encode('ascii', 'replace').decode() if row[1] else ''
        country = row[2] or ''
        source = row[3] or ''
        url = row[4] or ''
        print(f'  ID {row[0]}: {title} | {country} | {source} | {url} | status={row[5]} archived={row[6]} verified={row[7]}')

print('\n--- ADDED RECORDS DETAILS (remaining) ---')
for aid in sorted(list(added))[30:]:
    cursor.execute('SELECT id, title, country, official_source, official_source_url, status, is_archived, verification_status FROM scholarships WHERE id = ?', (aid,))
    row = cursor.fetchone()
    if row:
        title = row[1].encode('ascii', 'replace').decode() if row[1] else ''
        country = row[2] or ''
        source = row[3] or ''
        url = row[4] or ''
        print(f'  ID {row[0]}: {title} | {country} | {source} | {url} | status={row[5]} archived={row[6]} verified={row[7]}')

# Check for updated records (common IDs with different data)
print('\n--- CHECKING FOR UPDATES ON COMMON IDs ---')
common = base_ids & current_ids
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
            diffs = []
            for k in current:
                if current[k] != base_comp[k]:
                    diffs.append(f'{k}: "{str(base_comp[k])[:50]}" -> "{str(current[k])[:50]}"')
            print(f'  ID {cid} UPDATED: {"; ".join(diffs[:3])}')

print(f'\nTotal updated records: {updated_count}')

# Geographic check - excluded regions
print('\n--- GEOGRAPHIC SCOPE CHECK (EXCLUDED REGIONS) ---')
excluded_countries = ['Saudi Arabia', 'United Arab Emirates', 'Israel', 'Egypt', 'Turkey', 'Iran', 'Iraq', 'Jordan', 'Lebanon', 'Qatar', 'Kuwait', 'Bahrain', 'Oman', 'Yemen', 'Syria', 'Palestine', 'Mexico', 'Brazil', 'Argentina', 'Chile', 'Colombia', 'Peru', 'Venezuela', 'Ecuador', 'Bolivia', 'Paraguay', 'Uruguay', 'Costa Rica', 'Panama', 'Guatemala', 'Honduras', 'El Salvador', 'Nicaragua', 'Cuba', 'Dominican Republic', 'Haiti', 'Jamaica', 'Trinidad and Tobago', 'Barbados', 'Bahamas', 'Guyana', 'Suriname']
cursor.execute('SELECT id, title, country FROM scholarships WHERE country IN ({})'.format(','.join('?'*len(excluded_countries))), excluded_countries)
excluded_found = cursor.fetchall()
print(f'Records from excluded regions: {len(excluded_found)}')
for r in excluded_found:
    print(f'  ID {r[0]}: {r[1].encode("ascii", "replace").decode()} | {r[2]}')

conn.close()