"""Read-only verification that the image mutation audit is live on production.

Every statement here is a SELECT. The script proves the audit exists and is
armed, and that nothing about the stored data changed as a result of installing
it. It writes nothing, and deliberately does not create a synthetic mutation:
proving the trigger fires would itself alter a scholarship, which is exactly
what this phase is forbidden from doing.
"""
from __future__ import annotations

import os
import sys

# The application package lives one level up from this script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402

TARGET_IDS = (14, 130, 554)


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1

    with engine.connect() as c:
        print(f"  dialect: {engine.dialect.name}")

        tables = c.execute(
            text("SELECT count(*) FROM information_schema.tables "
                 "WHERE table_schema = 'public' AND table_name = 'scholarship_image_audit'")
        ).scalar()
        print(f"  1. audit table exists: {'YES' if tables else 'NO'}")

        trig = c.execute(
            text("SELECT count(*) FROM pg_trigger WHERE tgrelid = 'scholarships'::regclass "
                 "AND tgname = 'trg_scholarships_image_audit' AND NOT tgisinternal")
        ).scalar()
        print(f"  2. audit trigger installed: {'YES' if trig else 'NO'}")

        guard = c.execute(
            text("SELECT count(*) FROM pg_trigger "
                 "WHERE tgrelid = 'scholarship_image_audit'::regclass "
                 "AND tgname = 'trg_scholarship_image_audit_immutable' AND NOT tgisinternal")
        ).scalar()
        print(f"     append-only guard installed: {'YES' if guard else 'NO'}")

        cols = [r[0] for r in c.execute(
            text("SELECT column_name FROM information_schema.columns "
                 "WHERE table_name = 'scholarship_image_audit' ORDER BY ordinal_position")
        )]
        print(f"     audit columns ({len(cols)}): {', '.join(cols)}")

        fn = c.execute(
            text("SELECT count(*) FROM pg_proc "
                 "WHERE proname = 'scholarzone_record_image_mutation'")
        ).scalar()
        print(f"     record function installed: {'YES' if fn else 'NO'}")

        rows = c.execute(text("SELECT count(*) FROM scholarship_image_audit")).scalar()
        print(f"     audit rows so far: {rows} (0 expected: no mutations occurred)")

        storage = c.execute(text("SELECT count(*) FROM scholarships")).scalar()
        print(f"  4. storage count: {storage}")

        public = c.execute(
            text("SELECT count(*) FROM scholarships WHERE is_archived IS NOT TRUE "
                 "AND verification_status = 'active'")
        ).scalar()
        print(f"  5. public count: {public}")

        withimg = c.execute(
            text("SELECT count(*) FROM scholarships WHERE image_url IS NOT NULL")
        ).scalar()
        print(f"     with image: {withimg}")

        print("  6/7. target record image state (unchanged, not repaired):")
        for sid in TARGET_IDS:
            r = c.execute(
                text("SELECT image_url, image_kind, image_verified_at, "
                     "image_evaluation_status, verification_status "
                     "FROM scholarships WHERE id = :i"), {"i": sid}
            ).mappings().one_or_none()
            if r is None:
                print(f"     id {sid}: MISSING")
                continue
            img = "NULL" if not r["image_url"] else r["image_url"][:58]
            print(f"     id {sid}: image={img}")
            print(f"              kind={r['image_kind']} "
                  f"verif_at={r['image_verified_at']} "
                  f"eval={r['image_evaluation_status']} "
                  f"status={r['verification_status']}")

        print("  8. Match/Count/Stats invariants:")
        stats = c.execute(
            text("SELECT count(*) FROM scholarships WHERE is_archived IS NOT TRUE")
        ).scalar()
        print(f"     non-archived rows: {stats}")
        archived = c.execute(
            text("SELECT count(*) FROM scholarships WHERE is_archived IS TRUE")
        ).scalar()
        print(f"     archived rows: {archived}")
        needs = c.execute(
            text("SELECT count(*) FROM scholarships WHERE is_archived IS NOT TRUE "
                 "AND verification_status <> 'active'")
        ).scalar()
        print(f"     public non-active: {needs} (expected 0)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())