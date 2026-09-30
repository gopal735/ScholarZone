"""Audit how official_source_url domains are classified by the evidence layer."""
from __future__ import annotations

import sys
from collections import Counter
from urllib.parse import urlparse

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.models import Base, Scholarship
from app.services.scholarship_evidence import SourceType, classify_source

DB = sys.argv[1] if len(sys.argv) > 1 else "scholarzone.db"
engine = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

rows = session.execute(
    select(Scholarship.id, Scholarship.title, Scholarship.official_source_url)
).all()

by_type: Counter[str] = Counter()
not_auth: list[tuple[int, str, str]] = []
for sid, title, url in rows:
    if not url:
        continue
    st = classify_source(url)
    by_type[st.value] += 1
    if st == SourceType.THIRD_PARTY:
        not_auth.append((sid, urlparse(url).netloc, title))

print("=== CLASSIFICATION BREAKDOWN ===")
for k, v in by_type.most_common():
    print(f"  {k:32s} {v}")

print(f"\n=== THIRD-PARTY CLASSIFIED DOMAINS ({len(not_auth)} records) ===")
domains = Counter(d for _, d, _ in not_auth)
for domain, count in domains.most_common(40):
    print(f"  {count:4d}  {domain}")

print("\n=== SAMPLE TITLES (first 20) ===")
for sid, domain, title in not_auth[:20]:
    print(f"  id={sid:<5d} {domain:<40s} {title[:52]}")

session.close()
