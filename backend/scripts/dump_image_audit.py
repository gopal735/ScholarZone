"""Read-only dump of image mutation audit evidence for the target records.

Reports every audit event for the target scholarships in chronological order,
plus the distribution of writer contexts across the whole audit. Used to
attribute mutations rather than infer them from timing.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402

AUDIT = "scholarship_image_audit"
TARGET_IDS = (14, 130, 554)


def short(value, limit=58):
    if value is None:
        return "None"
    text_value = str(value)
    return text_value if len(text_value) <= limit else text_value[:limit] + "..."


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1

    with engine.connect() as c:
        total = c.execute(text(f"SELECT count(*) FROM {AUDIT}")).scalar()
        print(f"=== audit totals ===")
        print(f"  rows in audit: {total}")
        span = c.execute(text(
            f"SELECT min(changed_at_utc), max(changed_at_utc) FROM {AUDIT}"
        )).one()
        print(f"  first event: {span[0]}")
        print(f"  last  event: {span[1]}")

        print("=== writer context distribution (whole audit) ===")
        for wc, n, first, last in c.execute(text(
            f"SELECT writer_context, count(*), min(changed_at_utc), max(changed_at_utc) "
            f"FROM {AUDIT} GROUP BY writer_context ORDER BY count(*) DESC"
        )):
            print(f"  {str(wc):34} n={n:<4} {first} .. {last}")

        print("=== unattributed events (writer_context = unknown) ===")
        unk = c.execute(text(
            f"SELECT count(*) FROM {AUDIT} WHERE writer_context = 'unknown'"
        )).scalar()
        print(f"  count: {unk}")

        for sid in TARGET_IDS:
            print(f"=== id {sid}: audit history (oldest first) ===")
            rows = c.execute(text(
                f"SELECT id, changed_at_utc, changed_fields, before_values, "
                f"after_values, writer_context, application_name, transaction_id "
                f"FROM {AUDIT} WHERE scholarship_id = :i ORDER BY changed_at_utc ASC, id ASC"
            ), {"i": sid}).mappings().all()
            if not rows:
                print("  (no audit events)")
                continue
            for r in rows:
                print(f"  [{r['id']}] {r['changed_at_utc']}  ctx={r['writer_context']!r}"
                      f"  app={r['application_name']!r}  txid={r['transaction_id']!r}")
                print(f"       fields: {r['changed_fields']}")
                print(f"       before: {short(r['before_values'], 150)}")
                print(f"       after : {short(r['after_values'], 150)}")

        print("=== most recent 15 audit events, any record ===")
        for r in c.execute(text(
            f"SELECT id, scholarship_id, changed_at_utc, changed_fields, writer_context "
            f"FROM {AUDIT} ORDER BY changed_at_utc DESC, id DESC LIMIT 15"
        )):
            print(f"  [{r[0]}] id={r[1]:<5} {r[2]}  ctx={str(r[4]):26} {r[3][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())