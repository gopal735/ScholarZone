"""Rebuild the logo-hunt shards from the original 57-host run, then append the
hosts that only appeared after the wave-2 inserts.

The in-flight agents read `shards/w3-NN.json` by number, so the numbering has to
stay the one they were given: a regeneration that renumbered the files would send
each agent to another awarding body's page.
"""
import json
import os

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
W3 = os.path.join(ROOT, "research", "wave3")
OUT = os.path.join(W3, "shards")
os.makedirs(OUT, exist_ok=True)

# The host -> record ids assignment the first 57 shards were built from.
ORIGINAL = [
    ("massey.ac.nz", [615, 658, 659]), ("ean.org", [625, 627]),
    ("study.gov.pl", [413, 423]), ("wider.unu.edu", [491, 492]),
    ("admissions.kaust.edu.sa", [557]), ("admissions.tc.umn.edu", [59]),
    ("admissions.yale.edu", [126]), ("afdb.org", [520]),
    ("aims.ac.za", [522]), ("albertainnovates.ca", [499]),
    ("anrfonline.in", [361]), ("apply.ruffordsmallgrants.org", [536]),
    ("arabfund.org", [667]), ("aut.ac.nz", [616]), ("bond.edu.au", [664]),
    ("campuschina.org", [33]), ("canterbury.ac.nz", [511]), ("cdu.edu.au", [512]),
    ("conservationleadershipprogramme.org", [535]), ("cucsh.udg.mx", [596]),
    ("education.gov.au", [45]), ("ersnet.org", [626]), ("escardio.org", [580]),
    ("finaid.yale.edu", [481]), ("fnr.lu", [507]), ("globalhealth.unc.edu", [534]),
    ("gob.mx", [635]), ("gov.br", [603]), ("grants.at", [526]),
    ("gulbenkian.pt", [628]), ("in.emb-japan.go.jp", [360]),
    ("international.colostate.edu", [636]), ("ip-paris.fr", [95]),
    ("jobs.inria.fr", [549]), ("lut.fi", [267]),
    ("mandelawashingtonfellowship.org", [521]), ("master-bioceb.eu", [350]),
    ("master-europeanforestry.eu", [348]), ("mastercardfdn.org", [541]),
    ("mbzuai.ac.ae", [558]), ("medicine.yale.edu", [533]), ("movetia.ch", [567]),
    ("tec.mx", [631]), ("tugraz.at", [217]), ("ulisboa.pt", [304]),
    ("unhcr-dafi-tertiary.scholarshipsplatform.com", [523]), ("unibocconi.it", [139]),
    ("unige.ch", [152]), ("unitn.it", [137]), ("vanier.gc.ca", [38]),
    ("visegradfund.mvcr.cz", [419]), ("vlaanderen.be", [508]), ("web.ub.edu", [100]),
    ("wellcome.org", [562]), ("westernsydney.edu.au", [666]),
    ("westminster.ac.uk", [524]), ("whitleyaward.org", [537]),
]

# Hosts that appeared only after the wave-2 inserts landed.
ADDED = [("aucegypt.edu", [724]), ("cshl.edu", [697]), ("edu.gov.az", [715]),
         ("portal.gov.gy", [716])]

import sqlite3
conn = sqlite3.connect(os.path.join(ROOT, "backend", "scholarzone.db"))
conn.row_factory = sqlite3.Row
titles = {}
for row in conn.execute("SELECT id, title, official_source, official_source_url FROM scholarships"):
    titles[row["id"]] = row
conn.close()

manifest = []
for i, (host, ids) in enumerate(ORIGINAL + ADDED, start=1):
    shard = f"w3-{i:02d}"
    records = []
    for rid in ids:
        row = titles.get(rid)
        records.append({
            "target_id": rid,
            "title": row["title"] if row else None,
            "official_source": row["official_source"] if row else None,
            "official_source_url": row["official_source_url"] if row else None,
        })
    payload = {"shard": shard, "agent_id": f"w3_{i:02d}", "today": "2026-10-04",
               "host": host, "records": records, "added_later": host in dict(ADDED)}
    json.dump(payload, open(os.path.join(OUT, f"{shard}.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    manifest.append({"shard": shard, "host": host, "records": ids,
                     "added_later": payload["added_later"]})

json.dump({"shards": len(manifest), "items": manifest},
          open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8"), indent=2)
print("logo hunt shards:", len(manifest), "| newly added hosts:",
      sum(1 for m in manifest if m["added_later"]))
for m in manifest[-6:]:
    print("  ", m["shard"], m["host"], m["records"], m["added_later"])