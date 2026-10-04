"""Phase 0-2 forensic pre-flight: audit boundary, pipeline health, baseline.

Read-only. Every statement is a SELECT or a privilege lookup; no scholarship row
and no audit row is created, altered or removed.

Reports, in order:
  Phase 0  audit objects and the application's privileges on them
  Phase 1  the most recent scheduled maintenance run and its stage outcomes
  Phase 2  the baseline image state of the target records
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402

TARGET_IDS = (14, 130, 554)
AUDIT = "scholarship_image_audit"

TRACKED = (
    "image_url",
    "image_source_url",
    "image_source_type",
    "image_kind",
    "image_alt_text",
    "image_verified_at",
    "image_evaluation_status",
    "image_evaluated_at",
)


def phase0(c) -> bool:
    print("=== PHASE 0: audit boundary ===")
    role = c.execute(text("SELECT current_user")).scalar()
    print(f"  connected role: {role}")

    for label, sql in (
        ("audit table", "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:t"),
        ("audit trigger", "SELECT count(*) FROM pg_trigger WHERE "
                          "tgrelid='scholarships'::regclass AND "
                          "tgname='trg_scholarships_image_audit' AND NOT tgisinternal"),
        ("immutable guard", "SELECT count(*) FROM pg_trigger WHERE "
                            "tgrelid='scholarship_image_audit'::regclass AND "
                            "tgname='trg_scholarship_image_audit_immutable' AND "
                            "NOT tgisinternal"),
        ("record function", "SELECT count(*) FROM pg_proc WHERE "
                            "proname='scholarzone_record_image_mutation'"),
    ):
        params = {"t": AUDIT} if "information_schema" in sql else {}
        print(f"  {label:16}: {'YES' if c.execute(text(sql), params).scalar() else 'NO'}")

    print("  privileges of the connected role on scholarship_image_audit:")
    privs = {}
    for name in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES"):
        privs[name] = bool(c.execute(
            text("SELECT has_table_privilege(current_user, :t, :p)"),
            {"t": AUDIT, "p": name},
        ).scalar())
        print(f"    {name:11}: {'yes' if privs[name] else 'DENIED'}")

    # The boundary the mission requires.
    print("  boundary assessment:")
    ok = True
    if privs["UPDATE"] or privs["DELETE"] or privs["TRUNCATE"]:
        print("    UNSAFE: the application role can rewrite or remove audit rows")
        ok = False
    else:
        print("    safe: UPDATE, DELETE and TRUNCATE are all denied")
    print(f"    INSERT: {'permitted (expected: the trigger writes as SECURITY DEFINER)' if privs['INSERT'] else 'denied'}")
    if not privs["INSERT"]:
        print("    note: INSERT denied; the SECURITY DEFINER trigger must still work")
    return ok


def phase1(c) -> bool:
    print("=== PHASE 1: maintenance health gate ===")
    cols = {r[0] for r in c.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name='maintenance_runs'")
    )}
    if not cols:
        print("  no maintenance_runs table found")
        return False
    print(f"  maintenance_runs columns: {', '.join(sorted(cols))}")

    order = "started_at" if "started_at" in cols else (
        "created_at" if "created_at" in cols else "id")
    row = c.execute(text(
        f"SELECT * FROM maintenance_runs ORDER BY {order} DESC LIMIT 1"
    )).mappings().first()
    if row is None:
        print("  no runs recorded")
        return False
    print(f"  latest run id: {row.get('run_id') or row.get('id')}")
    for key in ("started_at", "finished_at", "status", "stages_run", "stages_failed",
                "stages_skipped", "error"):
        if key in row:
            print(f"    {key}: {row[key]}")

    detail = row.get("detail") or row.get("detail_json") or row.get("result")
    text_detail = detail if isinstance(detail, str) else (str(detail) if detail else "")
    bad = [n for n in ("LOGO_IDENTITY_KINDS", "ACCEPTED_IMAGE_KINDS") if n in text_detail]
    if bad:
        print(f"  FAIL: latest run mentions unbound constants: {', '.join(bad)}")
        return False
    print("  no unbound image-constant NameError in the latest run")

    recent = c.execute(text(
        f"SELECT * FROM maintenance_runs ORDER BY {order} DESC LIMIT 3"
    )).mappings().all()
    for r in recent:
        d = r.get("detail") or r.get("detail_json") or ""
        d = d if isinstance(d, str) else str(d)
        flag = "NAMEERROR" if ("LOGO_IDENTITY_KINDS" in d or "ACCEPTED_IMAGE_KINDS" in d) else "clean"
        print(f"    run {r.get('run_id') or r.get('id')}: {r.get('status')} [{flag}]")
    return True


def phase2(c) -> None:
    print("=== PHASE 2: baseline image state ===")
    audit_rows = c.execute(
        text(f"SELECT count(*) FROM {AUDIT}")).scalar()
    print(f"  existing audit rows: {audit_rows}")

    for sid in TARGET_IDS:
        r = c.execute(text(
            "SELECT " + ", ".join(TRACKED) + ", verification_status, is_archived, "
            "updated_at FROM scholarships WHERE id = :i"), {"i": sid},
        ).mappings().one_or_none()
        if r is None:
            print(f"  id {sid}: MISSING")
            continue
        print(f"  id {sid}:")
        for f in TRACKED:
            print(f"    {f:26}= {r[f]!r}")
        print(f"    {'verification_status':26}= {r['verification_status']!r}")
        print(f"    {'is_archived':26}= {r['is_archived']!r}")
        print(f"    {'updated_at':26}= {r['updated_at']!r}")

    total = c.execute(text("SELECT count(*) FROM scholarships")).scalar()
    print(f"  storage total: {total}")


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1
    with engine.connect() as c:
        boundary_ok = phase0(c)
        pipeline_ok = phase1(c)
        phase2(c)
    print("=== PRE-FLIGHT RESULT ===")
    print(f"  audit boundary safe: {'YES' if boundary_ok else 'NO'}")
    print(f"  maintenance gate:    {'PASS' if pipeline_ok else 'FAIL'}")
    return 0 if (boundary_ok and pipeline_ok) else 2


if __name__ == "__main__":
    raise SystemExit(main())