import json
import pathlib
import re
import sys

BACKEND = pathlib.Path(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend")
sys.path.insert(0, str(BACKEND))

from sqlalchemy import inspect as sa_inspect

import app.models as M

print("=" * 78)
print("ALL TABLES AND THEIR COLUMNS (from ORM metadata)")
print("=" * 78)
md = M.Base.metadata
for tname, table in sorted(md.tables.items()):
    print(f"\n-- {tname}")
    for c in table.columns:
        fk = ""
        if c.foreign_keys:
            fk = "  ->FK-> " + ", ".join(sorted(str(f.target_fullname) for f in c.foreign_keys))
        print(f"     {c.name:34} {str(c.type)[:22]:24}{fk}")

print()
print("=" * 78)
print("TABLES WITH A FOREIGN KEY TO scholarships")
print("=" * 78)
ref = []
for tname, table in md.tables.items():
    if tname == "scholarships":
        continue
    for c in table.columns:
        for f in c.foreign_keys:
            if f.target_fullname.startswith("scholarships."):
                ref.append((tname, c.name, str(f.target_fullname),
                            str(f.ondelete) if f.ondelete else "NO ACTION (default)"))
for r in ref:
    print(f"   {r[0]:34} {r[1]:24} -> {r[2]:26} ondelete={r[3]}")
if not ref:
    print("   (no FK constraints declared to scholarships)")

print()
print("=" * 78)
print("SCHOLARSHIP LIFECYCLE / VISIBILITY FIELDS")
print("=" * 78)
sch = md.tables["scholarships"]
for c in sch.columns:
    print(f"   {c.name:32} {str(c.type)[:24]:26} nullable={c.nullable} default={c.default.arg if c.default is not None and hasattr(c.default,'arg') else None}")