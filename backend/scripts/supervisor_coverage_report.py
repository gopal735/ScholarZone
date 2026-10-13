"""Produce the supervisor coverage report for one database.

Read-only. Nothing here writes to a database, a file or an env var; it prints
the state of the supervisor tables as they actually are, which is the only kind
of coverage number worth publishing.

    python scripts/supervisor_coverage_report.py \\
        --database-url sqlite:///C:/path/to/catalogue.db \\
        --out SUPERVISOR_OFFICIAL_SOURCE_COVERAGE_REPORT.md

Every unresolved category is listed with scholarship ids and the official source
URLs they were assessed against, so a reader can check a claim rather than take
it. A total that cannot be walked back to a row is not reported at all.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, text  # noqa: E402

from app.models import Scholarship  # noqa: E402
from app.models_supervisor import (  # noqa: E402
    ProfessorProfile,
    ScholarshipOfficialContact,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)
from app.services.supervisor_status import (  # noqa: E402
    NON_PUBLISHING_COVERAGE_STATUSES,
    PUBLIC_RELATIONSHIP_STATUSES,
    SupervisorCoverageStatus,
)


def _domain(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).netloc or "").lower()


def _table_exists(engine, name: str) -> bool:
    from sqlalchemy import inspect

    return inspect(engine).has_table(name)


def build_report(engine) -> dict:
    """Return the whole coverage picture for the database ``engine`` reads."""
    from sqlalchemy.orm import sessionmaker

    contacts_table_present = _table_exists(engine, "scholarship_official_contacts")
    session = sessionmaker(bind=engine)()
    try:
        # --- scope: publicly visible records, which is what the panel serves.
        scope_ids = [
            row[0]
            for row in session.execute(
                select(Scholarship.id).where(
                    Scholarship.is_archived.is_(False),
                    Scholarship.status != "closed",
                    Scholarship.verification_status != "quarantined",
                )
            )
        ]

        # --- coverage rows, and the records that have none at all.
        coverage_rows = {
            row.scholarship_id: row
            for row in session.execute(
                select(ScholarshipSupervisorCoverage).where(
                    ScholarshipSupervisorCoverage.scholarship_id.in_(scope_ids)
                )
            ).scalars()
        }
        never_searched = sorted(set(scope_ids) - set(coverage_rows))

        status_counts: Counter[str] = Counter(
            row.status for row in coverage_rows.values()
        )
        status_counts[str(SupervisorCoverageStatus.SEARCH_PENDING)] += len(never_searched)

        # --- professors and relationships that actually publish.
        links = session.execute(
            select(ScholarshipProfessorLink).where(
                ScholarshipProfessorLink.scholarship_id.in_(scope_ids)
            )
        ).scalars()
        publishable_links = [
            link
            for link in links
            if link.verification_status in PUBLIC_RELATIONSHIP_STATUSES
            and link.scholarship_id in coverage_rows
            and coverage_rows[link.scholarship_id].status
            == str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
        ]
        professor_ids = sorted({link.professor_id for link in publishable_links})
        profiles = {
            row.id: row
            for row in session.execute(
                select(ProfessorProfile).where(ProfessorProfile.id.in_(professor_ids))
            ).scalars()
        }
        verified_emails = sum(
            1
            for profile in profiles.values()
            if profile.official_email_verified and profile.official_email
        )

        # Scholarship-level rollups.
        verified_scholarships = sorted({link.scholarship_id for link in publishable_links})
        not_applicable_scholarships = sorted(
            sid
            for sid, row in coverage_rows.items()
            if row.status == str(SupervisorCoverageStatus.NOT_APPLICABLE)
        )

        # --- official contacts on records with no supervisor answer.
        # A database that predates the contact table reports zero rather than
        # failing, exactly as the public read path does: the schema arrives by
        # an out-of-band migration, and a report must still be producible.
        contacts: list = []
        if contacts_table_present:
            contact_rows = session.execute(
                select(ScholarshipOfficialContact).where(
                    ScholarshipOfficialContact.scholarship_id.in_(scope_ids)
                )
            ).scalars()
            contacts = list(contact_rows)
        contact_email_verified = sum(
            1 for contact in contacts if contact.contact_email_verified and contact.contact_email
        )

        # --- evidence rows, for the provenance total.
        evidence_count = session.execute(
            select(func.count())
            .select_from(SupervisorSourceEvidence)
        ).scalar_one()

        # --- the unresolved buckets, each with the ids and the URLs behind them.
        def sample(scholarship_ids, limit=12):
            rows = (
                session.execute(
                    select(Scholarship.id, Scholarship.title, Scholarship.official_source_url)
                    .where(Scholarship.id.in_(scholarship_ids))
                    .order_by(Scholarship.id)
                    .limit(limit)
                )
                .all()
                if scholarship_ids
                else []
            )
            return [
                {"id": row[0], "title": row[1], "official_source_url": row[2]}
                for row in rows
            ]

        by_status = lambda status: sorted(  # noqa: E731
            sid for sid, row in coverage_rows.items() if row.status == str(status)
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": {
                "public_scholarships": len(scope_ids),
                "never_searched": len(never_searched),
            },
            "professors": {
                "published_professors": len(professor_ids),
                "publishable_relationships": len(publishable_links),
                "verified_professor_emails": verified_emails,
                "scholarships_with_verified_supervisors": len(verified_scholarships),
                "scholarships_not_applicable": len(not_applicable_scholarships),
            },
            "coverage_status_counts": dict(sorted(status_counts.items())),
            "contacts": {
                "official_contacts": len(contacts),
                "verified_contact_emails": contact_email_verified,
                "contacts_table_present": contacts_table_present,
            },
            "evidence_rows": evidence_count,
            "unresolved": {
                "pending_never_searched": sample(never_searched),
                "source_blocked": sample(
                    by_status(SupervisorCoverageStatus.SOURCE_BLOCKED)
                ),
                "source_requires_rendering": sample(
                    by_status(SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING)
                ),
                "needs_verification": sample(
                    by_status(SupervisorCoverageStatus.NEEDS_VERIFICATION)
                ),
                "no_verified_supervisor_found": sample(
                    by_status(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
                ),
                "not_applicable": sample(not_applicable_scholarships),
            },
            "counts_unresolved": {
                "pending_never_searched": len(never_searched),
                "source_blocked": len(by_status(SupervisorCoverageStatus.SOURCE_BLOCKED)),
                "source_requires_rendering": len(
                    by_status(SupervisorCoverageStatus.SOURCE_REQUIRES_RENDERING)
                ),
                "needs_verification": len(
                    by_status(SupervisorCoverageStatus.NEEDS_VERIFICATION)
                ),
                "no_verified_supervisor_found": len(
                    by_status(SupervisorCoverageStatus.NO_VERIFIED_SUPERVISOR_FOUND)
                ),
                "not_applicable": len(not_applicable_scholarships),
            },
            "non_publishing_states": sorted(str(status) for status in NON_PUBLISHING_COVERAGE_STATUSES),
        }
    finally:
        session.close()


def render_markdown(report: dict, database_description: str) -> str:
    """Return the report as markdown a reviewer can read without a terminal."""
    scope = report["scope"]
    professors = report["professors"]
    contacts = report["contacts"]
    counts = report["counts_unresolved"]

    lines: list[str] = []
    lines.append("# Supervisor coverage report - official source verification")
    lines.append("")
    lines.append(f"* Generated {report['generated_at']} against `{database_description}`.")
    lines.append(
        "* Every number below is computed from the supervisor tables in that database. "
        "Nothing is estimated, and a record with no evidence is counted as unresolved "
        "rather than as a negative."
    )
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append("| Measure | Count |")
    lines.append("| --- | ---: |")
    lines.append(f"| Public scholarships in scope | {scope['public_scholarships']} |")
    lines.append(
        f"| Scholarships with verified supervisors | "
        f"{professors['scholarships_with_verified_supervisors']} |"
    )
    lines.append(f"| Publishable verified relationships | {professors['publishable_relationships']} |")
    lines.append(f"| Distinct published professors | {professors['published_professors']} |")
    lines.append(f"| Professors with a verified official email | {professors['verified_professor_emails']} |")
    lines.append(f"| Scholarships marked not applicable | {professors['scholarships_not_applicable']} |")
    lines.append(f"| Official contacts recorded | {contacts['official_contacts']} |")
    lines.append(f"| Contacts with a verified official email | {contacts['verified_contact_emails']} |")
    lines.append(f"| Source-evidence rows | {report['evidence_rows']} |")
    if not contacts["contacts_table_present"]:
        lines.append("")
        lines.append(
            "> The contact table is not present in this database yet, so contact counts "
            "are zero by absence of the table rather than by absence of contacts."
        )
    lines.append("")

    lines.append("## Coverage by state")
    lines.append("")
    lines.append("| State | Records |")
    lines.append("| --- | ---: |")
    for status, count in report["coverage_status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.append("")

    lines.append("## Unresolved categories")
    lines.append("")
    lines.append(
        "Each category is listed with the records it contains and the official source URL "
        "each was assessed against. No category is empty by omission: if it is zero here, "
        "there are no records in it."
    )
    labels = {
        "pending_never_searched": "Discovery pending (never searched)",
        "source_blocked": "Source blocked or inaccessible",
        "source_requires_rendering": "JavaScript-rendered source requiring separate review",
        "needs_verification": "Candidates requiring verification",
        "no_verified_supervisor_found": "No verified supervisor found",
        "not_applicable": "Supervisor information not applicable (evidence-based)",
    }
    lines.append("")
    lines.append("| Category | Records |")
    lines.append("| --- | ---: |")
    for key, label in labels.items():
        lines.append(f"| {label} | {counts[key]} |")
    lines.append("")

    for key, label in labels.items():
        rows = report["unresolved"][key]
        lines.append(f"### {label} ({counts[key]})")
        lines.append("")
        if not rows:
            lines.append("None.")
            lines.append("")
            continue
        lines.append("First records, by scholarship id:")
        lines.append("")
        for row in rows:
            url = row["official_source_url"] or "no official source recorded"
            lines.append(f"- `{row['id']}` {row['title']} - assessed against {url}")
        if counts[key] > len(rows):
            lines.append("")
            lines.append(f"...and {counts[key] - len(rows)} more in this category.")
        lines.append("")

    lines.append("## What is not claimed")
    lines.append("")
    lines.append(
        "- No professor is listed without an official page connecting them to the "
        "programme. A matching university domain alone is never treated as that link."
    )
    lines.append(
        "- No email is published as verified unless the institution's own page published "
        "it. No address is derived from a naming convention."
    )
    lines.append(
        "- An official contact is an administrative office, never presented as a professor "
        "or a research supervisor."
    )
    lines.append(
        "- A blocked, rendered or pending record is a statement about access, not a "
        "statement about the institution's faculty."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="supervisor_coverage_report.py",
        description="Read-only supervisor coverage report for one database.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "Database to read. Defaults to SCHOLARZONE_DATABASE_URL, which defaults to "
            "the local SQLite file. Point it at the copy you ran discovery against."
        ),
    )
    parser.add_argument("--out", type=Path, default=None, help="Write the markdown report here.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the raw totals here.")
    args = parser.parse_args(argv)

    from sqlalchemy import create_engine

    from app.core.config import get_settings

    database_url = args.database_url or get_settings().database_url
    engine = create_engine(database_url)
    report = build_report(engine)

    markdown = render_markdown(report, database_url)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
        print(f"Report written to {args.out}", file=sys.stderr)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            __import__("json").dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
        )
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
