#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY forensic dump of the image-mutation audit boundary and evidence.

EVERY statement in this file is a SELECT against pg_catalog,
information_schema, or a read-only application query. There is no INSERT,
UPDATE, DELETE, TRUNCATE, DDL, DML or commit anywhere in it. It exists to
answer, from live production, questions that cannot be answered from the
repository alone: which trigger objects are actually installed, whether the
append-only guards are present, who owns the table, and what the audit can
therefore prove.

It deliberately does not use app.image_audit.create_image_audit_schema or any
other installer, because those execute DDL. Reading the boundary must not
change the boundary.

Usage
-----
    SCHOLARZONE_DATABASE_URL=... python scripts/pg_forensic_dump.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402

AUDIT = "scholarship_image_audit"
GUARD = "scholarship_image_audit_context"

#: TRIGGER_TYPE bits from the PostgreSQL catalog.
TYPE_BITS = ((1, "ROW"), (2, "BEFORE"), (4, "INSERT"), (8, "DELETE"),
             (16, "UPDATE"), (32, "TRUNCATE"), (64, "INSTEAD"))

TARGETS = (14, 130, 554)
I6_IDS = (557, 564, 569)

IMAGE_COLS = ("image_url", "image_source_url", "image_source_type", "image_kind",
              "image_alt_text", "image_verified_at", "image_evaluation_status",
              "image_evaluated_at")


def decode(tgtype: int) -> str:
    bits = [name for bit, name in TYPE_BITS if tgtype & bit]
    return "+".join(bits) if bits else f"raw({tgtype})"


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def safe(c, label, sql, params=None, show=40):
    try:
        rows = c.execute(text(sql), params or {}).mappings().all()
        print(f"  [{label}] {len(rows)} row(s)")
        for r in rows[:show]:
            print("    " + " | ".join(f"{k}={v!r}" for k, v in r.items()))
        return rows
    except Exception as exc:
        print(f"  [{label}] ERROR {type(exc).__name__}: {str(exc).splitlines()[0]}")
        return []


def phase_a_trigger_inventory(c) -> None:
    section("A. TRIGGER INVENTORY (live)")
    sql = """
        SELECT t.tgname,
               t.tgenabled,
               t.tgtype,
               c.relname                AS on_table,
               p.proname                AS function,
               p.prosecdef              AS security_definer,
               p.proconfig              AS function_settings,
               p.provolatile            AS volatility,
               p.prorettype::regtype    AS returns
        FROM pg_trigger t
        JOIN pg_class c     ON c.oid = t.tgrelid
        JOIN pg_proc  p     ON p.oid = t.tgfoid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND NOT t.tgisinternal
          AND c.relname IN ('scholarships', :audit)
        ORDER BY c.relname, t.tgname
    """
    for r in c.execute(text(sql), {"audit": AUDIT}).mappings().all():
        print(f"  trigger   : {r['tgname']}")
        print(f"    on table        : {r['on_table']}")
        print(f"    enabled (O/D/R/A): {r['tgenabled']}   (O=origin, D=disabled, "
              f"R=replica, A=always)")
        print(f"    tgtype decode   : {decode(r['tgtype'])}")
        print(f"    function        : {r['function']}()  returns {r['returns']}")
        print(f"    SECURITY DEFINER: {r['security_definer']}")
        print(f"    function settings (search_path): {r['function_settings']}")
        print(f"    volatility      : {r['volatility']}")


def phase_b_functions(c) -> None:
    section("B. FUNCTION BODIES (guard + record)")
    safe(c, "guard function", f"""
        SELECT p.proname, p.prosecdef, p.proconfig, p.prosrc
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname='public'
          AND p.proname IN ('scholarzone_image_mutation_guard',
                            'scholarzone_record_image_mutation')
        ORDER BY p.proname""", show=2)


def phase_c_ownership_grants(c) -> None:
    section("C. OWNERSHIP, GRANTS, ROLE MEMBERSHIP")
    safe(c, "connected identity", """
        SELECT current_user AS connected_role,
               r.rolsuper    AS is_superuser,
               r.rolbypassrls AS bypass_rls,
               r.rolcreaterole AS create_role,
               r.rolcreatedb   AS create_db
        FROM pg_roles r WHERE r.rolname = current_user""")
    safe(c, "audit table owner", f"""
        SELECT c.relname, pg_get_userbyid(c.relowner) AS owner, c.relrowsecurity,
               c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname IN (:audit, :guard, 'scholarships')""",
         {"audit": AUDIT, "guard": GUARD})
    safe(c, "explicit table grants on audit table", f"""
        SELECT grantee, table_privilege, privilege_type
        FROM information_schema.role_table_grants
        WHERE table_schema='public' AND table_name=:audit
        ORDER BY grantee, privilege_type""", {"audit": AUDIT}, show=60)
    safe(c, "PUBLIC grant check (REVOKE ... FROM PUBLIC leaves no PUBLIC row)", f"""
        SELECT count(*) AS public_grants
        FROM information_schema.role_table_grants
        WHERE table_schema='public' AND table_name=:audit AND grantee='PUBLIC'""",
         {"audit": AUDIT})
    safe(c, "has_table_privilege for current_user", f"""
        SELECT p AS privilege,
               has_table_privilege(current_user, :audit, p) AS granted
        FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE']) AS p""",
         {"audit": AUDIT})
    safe(c, "role memberships of connected role", """
        SELECT r.rolname AS member, g.rolname AS role_granted,
               m.admin_option
        FROM pg_auth_members m
        JOIN pg_roles r ON r.oid = m.member
        JOIN pg_roles g ON g.oid = m.roleid
        WHERE r.rolname = current_user""")
    safe(c, "all non-internal roles that could own/alter", """
        SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
        FROM pg_roles WHERE rolcanlogin ORDER BY rolname""")


def phase_d_evidence_model(c) -> None:
    section("D. EVIDENCE MODEL: what the scholarships trigger actually covers")
    safe(c, "triggers on scholarships by event", """
        SELECT t.tgname, t.tgenabled,
               CASE WHEN (t.tgtype & 4)  THEN 'INSERT' ELSE '' END ||
               CASE WHEN (t.tgtype & 8)  THEN 'DELETE' ELSE '' END ||
               CASE WHEN (t.tgtype & 16) THEN 'UPDATE' ELSE '' END ||
               CASE WHEN (t.tgtype & 32) THEN 'TRUNCATE' ELSE '' END AS events,
               CASE WHEN (t.tgtype & 2) THEN 'BEFORE' ELSE 'AFTER' END AS timing,
               CASE WHEN (t.tgtype & 1) THEN 'ROW' ELSE 'STATEMENT' END AS granularity
        FROM pg_trigger t
        WHERE t.tgrelid='scholarships'::regclass AND NOT t.tgisinternal
        ORDER BY t.tgname""")
    safe(c, "audit table columns", """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=:audit
        ORDER BY ordinal_position""", {"audit": AUDIT}, show=20)
    safe(c, "audit writer_context distribution", f"""
        SELECT writer_context, count(*) AS mutations,
               min(changed_at_utc) AS first_seen, max(changed_at_utc) AS last_seen
        FROM {AUDIT} GROUP BY writer_context ORDER BY mutations DESC""")
    safe(c, "audit: can a row exist for a non-existent scholarship? (orphan rows)", f"""
        SELECT count(*) AS orphan_audit_rows
        FROM {AUDIT} a LEFT JOIN scholarships s ON s.id = a.scholarship_id
        WHERE s.id IS NULL""")


def phase_e_records(c, ids, label) -> None:
    section(f"E. {label}: current state + full mutation history")
    for sid in ids:
        r = c.execute(text(
            "SELECT " + ", ".join(IMAGE_COLS) + ", verification_status, "
            "is_verified, is_archived, official_source_url, updated_at "
            "FROM scholarships WHERE id=:i"), {"i": sid}).mappings().one_or_none()
        if r is None:
            print(f"  id {sid}: NOT IN STORAGE")
            continue
        print(f"  id {sid}:")
        for f in IMAGE_COLS:
            print(f"    {f:26}= {str(r[f])[:88]!r}")
        print(f"    {'verification_status':26}= {r['verification_status']!r}"
              f"  is_verified={r['is_verified']}  is_archived={r['is_archived']}")
        print(f"    {'updated_at':26}= {r['updated_at']!r}")
        rows = c.execute(text(
            f"SELECT id, changed_at_utc, changed_fields, writer_context, "
            f"before_values, after_values, transaction_id "
            f"FROM {AUDIT} WHERE scholarship_id=:i ORDER BY id"), {"i": sid}).mappings().all()
        print(f"    audit rows: {len(rows)}")
        for a in rows:
            print(f"      #{a['id']} {a['changed_at_utc']} txn={a['transaction_id']} "
                  f"writer={a['writer_context']!r}")
            print(f"         fields: {a['changed_fields']}")
            print(f"         before: {str(a['before_values'])[:150]}")
            print(f"         after : {str(a['after_values'])[:150]}")
        try:
            h = c.execute(text(
                "SELECT created_at, field_name, old_value, new_value, change_type "
                "FROM scholarship_verification_history "
                "WHERE scholarship_id=:i AND field_name LIKE 'image%' "
                "ORDER BY id"), {"i": sid}).mappings().all()
            print(f"    verification_history image rows: {len(h)}")
            for x in h[:10]:
                print(f"      {x['created_at']} {x['field_name']}: "
                      f"{str(x['old_value'])[:34]} -> {str(x['new_value'])[:34]}")
        except Exception as exc:
            print(f"    verification_history: {type(exc).__name__}")


def phase_f_purged_images(c) -> None:
    section("F. IMAGE CLEARING EVENTS (candidates for the '18 purged images')")
    safe(c, "audit rows where image_url went non-null -> null", f"""
        SELECT a.scholarship_id, a.id AS audit_id, a.changed_at_utc,
               a.writer_context, a.transaction_id,
               a.before_values->>'image_url' AS old_url
        FROM {AUDIT} a
        WHERE a.before_values ? 'image_url'
          AND a.before_values->>'image_url' IS NOT NULL
          AND a.after_values->>'image_url' IS NULL
        ORDER BY a.changed_at_utc""", show=60)
    safe(c, "count of those events", f"""
        SELECT count(*) AS clear_events,
               count(DISTINCT scholarship_id) AS distinct_records
        FROM {AUDIT} a
        WHERE a.before_values ? 'image_url'
          AND a.before_values->>'image_url' IS NOT NULL
          AND a.after_values->>'image_url' IS NULL""")
    safe(c, "current image state of records whose image was ever cleared", f"""
        WITH cleared AS (
            SELECT DISTINCT scholarship_id FROM {AUDIT} a
            WHERE a.before_values ? 'image_url'
              AND a.before_values->>'image_url' IS NOT NULL
              AND a.after_values->>'image_url' IS NULL)
        SELECT s.id, s.image_url IS NOT NULL AS has_image_now,
               s.image_kind, s.image_evaluation_status,
               s.image_verified_at, s.updated_at
        FROM scholarships s JOIN cleared c ON c.scholarship_id = s.id
        ORDER BY s.id""", show=60)


def phase_g_public_universe(c) -> None:
    section("G. PUBLIC UNIVERSE now, and recent visibility-field changes")
    try:
        from sqlalchemy import select
        from app.models import Scholarship
        from app.repositories.scholarships import public_visibility_conditions

        A = set(c.execute(select(Scholarship.id)
                          .where(*public_visibility_conditions())).scalars().all())
        allids = set(c.execute(select(Scholarship.id)).scalars().all())
        print(f"  PUBLIC A={len(A)}  STORAGE B={len(allids)}  "
              f"A-B={len(A - allids)}  B-A={len(allids - A)}  A&B={len(A & allids)}")
        print(f"  I6_image_without_kind (image_url set, image_kind empty) among public: "
              f"{sorted(i for i in A if _i6(c, i))}")
    except Exception as exc:
        print(f"  public universe ERROR {type(exc).__name__}: {exc}")
    safe(c, "verification_history changes to visibility-relevant fields since 08:30Z", """
        SELECT scholarship_id, created_at, field_name, old_value, new_value, change_type
        FROM scholarship_verification_history
        WHERE created_at >= '2026-10-04 08:30:00+00'
          AND field_name IN ('verification_status','is_verified','is_archived',
                             'official_source_url','status','is_archived_at')
        ORDER BY created_at""", show=80)


def _i6(c, sid) -> bool:
    r = c.execute(text("SELECT image_url, image_kind FROM scholarships WHERE id=:i"),
                  {"i": sid}).mappings().one_or_none()
    return bool(r and r["image_url"] and not r["image_kind"])


def phase_h_maintenance_runs(c) -> None:
    section("H. RECENT MAINTENANCE RUNS (for correlation)")
    safe(c, "maintenance_runs latest 12", """
        SELECT run_id, started_at, finished_at, status, worker,
               stages_run, stages_failed, stages_skipped
        FROM maintenance_runs ORDER BY started_at DESC LIMIT 12""", show=14)
    safe(c, "I6 bucket: image_url set, image_kind empty (whole catalogue)", """
        SELECT id, image_url, image_kind, image_evaluation_status,
               image_verified_at, verification_status, is_archived, updated_at
        FROM scholarships
        WHERE image_url IS NOT NULL AND image_kind IS NULL
        ORDER BY id""", show=40)


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1
    with engine.connect() as c:
        phase_a_trigger_inventory(c)
        phase_b_functions(c)
        phase_c_ownership_grants(c)
        phase_d_evidence_model(c)
        phase_e_records(c, TARGETS, "TARGETS 14/130/554")
        phase_e_records(c, I6_IDS, "I6 records 557/564/569")
        phase_f_purged_images(c)
        phase_g_public_universe(c)
        phase_h_maintenance_runs(c)
    print()
    print("=== READ-ONLY DUMP COMPLETE (no writes were issued) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())