"""Duplicate and identity checks over the published snapshot and the corpus.

Read-only. Compares official-source URLs and programme titles to find any
collision that would make an insertion a duplicate rather than a new record.
"""
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
SNAPSHOT = BASE / "frontend/public/scholarships-snapshot.json"
DATABASE = BASE / "backend/scholarzone.db"
CORPUS = BASE / "backend/config/programme_details.json"

snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
records = snapshot["scholarships"]

conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row
corpus = {r["id"]: r for r in json.loads(CORPUS.read_text(encoding="utf-8"))["records"]}


def norm_url(url):
    return (url or "").strip().lower().rstrip("/")


def norm_title(title):
    text = re.sub(r"[^a-z0-9]+", " ", (title or "").lower())
    return " ".join(text.split())


url_groups = defaultdict(list)
title_groups = defaultdict(list)
for record in records:
    for url in [record.get("official_source_url"), *(record.get("official_source_urls") or [])]:
        if url:
            url_groups[norm_url(url)].append(record["id"])
    title_groups[norm_title(record.get("title"))].append(record["id"])

url_dupes = {u: ids for u, ids in url_groups.items() if len(ids) > 1}
title_dupes = {t: ids for t, ids in title_groups.items() if len(ids) > 1}
print("official URL collisions:", len(url_dupes))
for u, ids in list(url_dupes.items())[:10]:
    print("  ", u[:80], ids)
print("normalised title collisions:", len(title_dupes))
for t, ids in list(title_dupes.items())[:10]:
    print("  ", t[:70], ids)

# Corpus ids that also exist in the DB (the apply path), to make sure any new
# record would get a fresh id rather than overwriting one.
corpus_ids = set(corpus)
db_ids = {int(r["id"]) for r in conn.execute("SELECT id FROM scholarships")}
snapshot_ids = {int(r["id"]) for r in records}
print()
print("corpus records:", len(corpus_ids), "| db rows:", len(db_ids), "| snapshot records:", len(snapshot_ids))
print("snapshot ids missing from db:", sorted(snapshot_ids - db_ids, key=int)[:10])
print("db archived rows among snapshot ids:", len([i for i in snapshot_ids if conn.execute('SELECT is_archived FROM scholarships WHERE id=?', (i,)).fetchone()[0]]))
print("next free db id:", max(db_ids) + 1)

# The two confirmed discontinued candidates, checked for any surviving
# duplicate of the same official identity.
for rid in (279, 729):
    row = conn.execute("SELECT id, title, official_source_url FROM scholarships WHERE id=?", (rid,)).fetchone()
    print()
    print("record", rid, "->", row["title"])
    same_url = [i for i, s in enumerate(records, 1) if norm_url(s.get("official_source_url")) == norm_url(row["official_source_url"]) and s["id"] != rid]
    print("  other published records on the same official_source_url:", same_url)
    partial = [
        r["id"] for r in records
        if r["id"] != rid and any(
            norm_url(u) == norm_url(row["official_source_url"]) for u in (r.get("official_source_urls") or [])
        )
    ]
    print("  other published records citing it in official_source_urls:", partial)
conn.close()
