"""Measure authoritative-source coverage of official_source_url across the catalogue."""
from __future__ import annotations

import sys
from collections import Counter
from urllib.parse import urlparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.models import Base, Scholarship
from app.services.scholarship_evidence import SourceType, classify_source

DB = sys.argv[1] if len(sys.argv) > 1 else "scholarzone.db"
engine = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(engine)
session = sessionmaker(bind=engine)()

rows = session.execute(select(Scholarship.id, Scholarship.title, Scholarship.official_source_url)).all()

counts: Counter[str] = Counter()
residual: list[tuple[int, str, str]] = []
for sid, title, url in rows:
    if not url:
        continue
    st = classify_source(url)
    counts[st.value] += 1
    if st == SourceType.THIRD_PARTY:
        residual.append((sid, urlparse(url).netloc.lower(), title))

total = sum(counts.values())
auth = total - counts["third_party"]
print("=== AUTHORITATIVE COVERAGE ===")
for k, v in counts.most_common():
    print(f"  {k:32s} {v:4d}  ({100*v/total:5.1f}%)")
print(f"\n  AUTHORITATIVE: {auth}/{total} ({100*auth/total:.1f}%)")
print(f"  THIRD PARTY   : {counts['third_party']}/{total} ({100*counts['third_party']/total:.1f}%)")

if residual:
    print(f"\n=== RESIDUAL THIRD-PARTY DOMAINS ({len(set(d for _,d,_ in residual))} distinct) ===")
    doms = Counter(d for _, d, _ in residual)
    for d, c in doms.most_common(60):
        print(f"  {c:3d}  {d}")
    print("\n  sample titles:")
    for sid, d, t in residual[:15]:
        print(f"    id={sid:<5d} {d:<38s} {t[:46]}")
session.close()
