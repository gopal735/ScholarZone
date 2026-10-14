import json, os, sqlite3

BASE = r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone'
DETAILS = os.path.join(BASE, 'backend', 'config', 'programme_details.json')
DB = os.path.join(BASE, 'backend', 'scholarzone.db')

# A percentage is not an amount: an award published as "20% of tuition" cannot
# be stored as a bare 20 with no currency, because that reads as twenty units of
# nothing. The value survives as a note; the amount column stays null.
PERCENT_IDS = {47, 194, 201, 394, 513, 709}
UNLABELLED = {693}  # Barbados "$" with no stated currency

raw = json.loads(open(DETAILS, encoding='utf-8').read())
changed = []
for rec in raw['records']:
    rid = rec.get('id')
    if rid not in PERCENT_IDS and rid not in UNLABELLED:
        continue
    o = rec.get('official') or {}
    amt = o.get('funding_amount')
    if amt is None:
        continue
    if rid in PERCENT_IDS:
        o.setdefault('funding_amount_note',
                     f'{amt}% of tuition fees; published as a percentage, not a cash amount.')
    else:
        o.setdefault('funding_amount_note',
                     f'{amt} per annum in an unlabelled "$" (the awarding body publishes allowances '
                     f'by destination without stating a currency); see benefits for the per-destination figures.')
    o['funding_amount'] = None
    o['funding_currency'] = None
    if rid in UNLABELLED:
        o['funding_period'] = None
    rec['official'] = o
    changed.append(rid)

with open(DETAILS, 'w', encoding='utf-8') as f:
    json.dump(raw, f, ensure_ascii=False, indent=1)
print('corpus records fixed:', changed)

conn = sqlite3.connect(DB)
for rid in changed:
    conn.execute("""UPDATE scholarships SET funding_amount=NULL, funding_currency=NULL
                    WHERE id=?""", (rid,))
    if rid in UNLABELLED:
        conn.execute('UPDATE scholarships SET funding_period=NULL WHERE id=?', (rid,))
conn.commit()

conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived=0 AND funding_amount IS NOT NULL AND funding_amount != '' AND (funding_currency IS NULL OR funding_currency='')")
print('remaining amount-without-currency rows:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM scholarships WHERE is_archived=0 AND funding_amount IS NOT NULL AND funding_amount != ''")
print('rows with funding_amount now:', cur.fetchone()[0], '/ 643')
conn.close()
