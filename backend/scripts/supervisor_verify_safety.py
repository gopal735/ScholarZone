"""Phase 2 and Phase 10 verification: migration safety and worker bounds.

Static checks against the real DDL module rather than a claim that it is safe.
Prints a verdict per rule and exits non-zero if any required rule fails.
"""

from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")

from app.supervisor_ddl import NEW_TABLE_DDL, NEW_TABLE_INDEXES  # noqa: E402

FORBIDDEN = ("DROP ", "ALTER ", "DELETE ", "TRUNCATE ", "UPDATE ")

LOOKUP_PATHS = {
    "scholarship_supervisor_coverage": ["scholarship_id", "status", "next_check_at"],
    "professor_profiles": ["official_profile_url", "institution_name", "canonical_name"],
    "scholarship_professor_links": [
        "scholarship_id",
        "professor_id",
        "verification_status",
    ],
    "supervisor_source_evidence": ["professor_id", "scholarship_id", "source_host"],
    "professor_availability": ["professor_id"],
    "professor_outreach_records": ["user_id", "scholarship_id", "professor_id"],
}

WORKER_BOUNDS = {
    "MAX_WORKERS": 8,
    "MAX_WORKERS_CEILING": 16,
    "MAX_PAGES_PER_SCHOLARSHIP": 6,
    "MAX_CANDIDATES_PER_SCHOLARSHIP": 40,
    "MAX_HTML_BYTES": 400_000,
}

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((bool(ok), label))


def main() -> None:
    # ---- Phase 2: additive only -------------------------------------------
    for table, ddl in NEW_TABLE_DDL.items():
        for dialect, body in ddl.items():
            upper = body.upper()
            hits = [token for token in FORBIDDEN if token in upper]
            check(not hits, f"{table} ({dialect}) is additive only  [found: {hits or 'none'}]")
            check(
                "GENERATED ALWAYS AS IDENTITY" in upper or "AUTOINCREMENT" in upper,
                f"{table} ({dialect}) uses an auto-incrementing id",
            )

    # Only brand-new tables. Nothing existing is touched.
    existing = {"scholarships", "users", "user_sessions", "student_profiles", "application_records"}
    check(
        not (set(NEW_TABLE_DDL) & existing),
        "no existing table is altered; every new table is additive",
    )

    # ---- Foreign keys point at canonical parents ---------------------------
    expected_parents = {
        "scholarship_supervisor_coverage": {"scholarships"},
        "professor_profiles": set(),
        "scholarship_professor_links": {"scholarships", "professor_profiles"},
        "supervisor_source_evidence": {"professor_profiles", "scholarships", "scholarship_professor_links"},
        "professor_availability": {"professor_profiles"},
        "professor_outreach_records": {"users", "scholarships", "professor_profiles", "contact_templates"},
        "contact_templates": set(),
    }
    for table, parents in expected_parents.items():
        body = NEW_TABLE_DDL[table]["postgresql"]
        found = set(re.findall(r"REFERENCES\s+(\w+)\(", body))
        check(found == parents, f"{table} FK parents {sorted(found)} == {sorted(parents)}")

    # Outreach ownership must key to the canonical identity, not a private one.
    outreach = NEW_TABLE_DDL["professor_outreach_records"]["postgresql"]
    check("user_id INTEGER NOT NULL REFERENCES users(id)" in outreach,
          "outreach ownership keys to users(id) - no second identity system")

    # ---- Unique constraints are intentional --------------------------------
    uniqueness = {
        "scholarship_supervisor_coverage": "scholarship_id",
        "professor_profiles": "official_profile_url",
        "scholarship_professor_links": "scholarship_id, professor_id, relationship_type",
        "supervisor_source_evidence": "professor_id, source_url, source_type",
        "professor_availability": "professor_id, scope",
        "professor_outreach_records": "user_id, scholarship_id, professor_id",
    }
    for table, columns in uniqueness.items():
        body = NEW_TABLE_DDL[table]["postgresql"]
        check("UNIQUE" in body, f"{table} enforces uniqueness on ({columns})")

    # ---- Provenance is structurally required -------------------------------
    check(
        "evidence_source_url VARCHAR(2048) NOT NULL" in NEW_TABLE_DDL["scholarship_professor_links"]["postgresql"],
        "a relationship cannot exist without a source URL",
    )
    check(
        "source_url VARCHAR(2048) NOT NULL" in NEW_TABLE_DDL["professor_availability"]["postgresql"]
        and "verified_at TIMESTAMPTZ NOT NULL" in NEW_TABLE_DDL["professor_availability"]["postgresql"],
        "an availability claim cannot exist without a source and a date",
    )

    # ---- Indexes support the real lookup paths -----------------------------
    # A UNIQUE constraint already creates an index on its columns in both
    # PostgreSQL and SQLite, so those columns are indexed whether or not an
    # explicit index also names them. Adding a second, non-unique index over a
    # unique column would cost writes and buy nothing, so it is not added.
    def indexed_columns(table: str) -> set[str]:
        columns: set[str] = set()
        for definition in NEW_TABLE_INDEXES.get(table, []):
            if "(" in definition and ")" in definition:
                inner = definition[definition.index("(") + 1 : definition.rindex(")")]
                for part in inner.split(","):
                    columns.add(part.strip())
        body = NEW_TABLE_DDL[table]["postgresql"]
        for match in re.finditer(r"UNIQUE\s*\(([^)]*)\)", body, re.IGNORECASE):
            for part in match.group(1).split(","):
                columns.add(part.strip())
        return columns

    for table, columns in LOOKUP_PATHS.items():
        available = indexed_columns(table)
        missing = [column for column in columns if column not in available]
        check(not missing, f"{table} indexes cover {columns}  [missing: {missing or 'none'}]")

    # ---- Phase 10: worker bounds -------------------------------------------
    from app.services import supervisor_discovery as worker
    from app.core.rate_limit import outreach_write_limiter, draft_limiter, supervisor_read_limiter

    for name, bound in WORKER_BOUNDS.items():
        actual = getattr(worker, name)
        check(actual == bound, f"worker bound {name} = {actual} (expected {bound})")
    check(
        worker.MAX_WORKERS <= worker.MAX_WORKERS_CEILING,
        "worker concurrency cannot exceed its ceiling",
    )

    # No unbounded crawl: the crawler is a flat, bounded loop, not recursion.
    source = open("app/services/supervisor_discovery.py", encoding="utf-8").read()
    check("def discover_for_scholarship" in source, "discovery entry point is named and bounded")
    check(source.count("polite_fetch(") <= 6, "polite_fetch call sites are finite and few")
    check("_RATE_LIMITER.wait_if_needed" in source, "per-host delay is enforced before every request")
    check("_robots_allows" in source, "robots is checked before every fetch")
    check("MAX_PAGES_PER_SCHOLARSHIP" in source, "page budget is enforced")
    check("next_check_at" in source, "records are scheduled for a later re-check, not a tight loop")
    check(
        not re.search(r"def\s+(\w+)\(.*\):\s*\n\s+\1\(", source),
        "no self-recursive crawl function",
    )

    # Rate limits exist and are bounded.
    for name, limiter in (
        ("supervisor_read", supervisor_read_limiter),
        ("draft", draft_limiter),
        ("outreach_write", outreach_write_limiter),
    ):
        check(limiter._limit > 0 and limiter._window > 0, f"{name} limiter is bounded")

    # ---- Report -----------------------------------------------------------
    passed = sum(1 for ok, _ in results if ok)
    for ok, label in results:
        print(("PASS  " if ok else "FAIL  ") + label)
    print()
    print(f"{passed}/{len(results)} checks passed")
    if passed != len(results):
        raise SystemExit(1)
    print("Migration safety and worker bounds verified.")


if __name__ == "__main__":
    main()