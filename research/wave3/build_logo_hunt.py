import json
import os
import sqlite3
from urllib.parse import urlsplit

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
conn = sqlite3.connect(os.path.join(ROOT, "backend", "scholarzone.db"))
conn.row_factory = sqlite3.Row
LOGO_KINDS = ("official_logo", "official_government", "official_university")
rows = conn.execute(
    "SELECT id,title,country,official_source,official_source_url,image_url,image_kind "
    "FROM scholarships WHERE verification_status!='quarantined' ORDER BY id"
).fetchall()


def host(url):
    try:
        h = (urlsplit(url or "").hostname or "").lower()
        return h[4:] if h.startswith("www.") else h
    except ValueError:
        return ""


need = [r for r in rows if (r["image_kind"] or "") not in LOGO_KINDS]
print("records without an official logo:", len(need))
by_host = {}
for r in need:
    by_host.setdefault(host(r["official_source_url"]), []).append(r)

items = sorted(by_host.items(), key=lambda kv: (-len(kv[1]), kv[0]))
for h, group in items:
    print(f"\n{h or '<no host>'}  ({len(group)})")
    for r in group:
        print(f"   id={r['id']:<4} {(r['title'] or '')[:64]:<66} img={'yes' if r['image_url'] else 'no'} kind={r['image_kind']}")

out = {
    "generated_for": "official logo hunt",
    "total_records": len(need),
    "hosts": [
        {
            "host": h,
            "records": [
                {"target_id": r["id"], "title": r["title"], "country": r["country"],
                 "official_source": r["official_source"],
                 "official_source_url": r["official_source_url"],
                 "has_any_image": bool(r["image_url"]), "current_image_kind": r["image_kind"]}
                for r in group
            ],
        }
        for h, group in items
    ],
}
path = os.path.join(ROOT, "research", "wave3", "logo_hunt.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(out, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("\nwritten:", os.path.relpath(path, ROOT))
print("distinct hosts:", len(items))