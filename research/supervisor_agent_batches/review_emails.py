import os
import sqlite3
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "..", "backend", "scholarzone.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
rows = cur.execute(
    "SELECT id, canonical_name, official_email, official_profile_url FROM professor_profiles WHERE official_email IS NOT NULL"
).fetchall()

benign = 0
suspicious = []
for r in rows:
    host = (urlparse(r["official_profile_url"]).netloc or "").lower().replace("www.", "")
    em = r["official_email"].split("@")[1].lower()
    if em == host or em.endswith("." + host) or host.endswith("." + em):
        benign += 1
        continue
    suspicious.append((r["id"], r["canonical_name"], r["official_email"], host, em))

print(f"total with email: {len(rows)}, same-domain or subdomain: {benign}, to review: {len(suspicious)}")
for sid, name, email, phost, ehost in suspicious:
    print(f"  [{sid}] {name} | email={email} | profile_host={phost} | email_host={ehost}")
con.close()
