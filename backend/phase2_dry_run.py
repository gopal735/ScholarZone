"""Phase 2 dry-run: verify 10 scholarships from different countries without DB writes.

This script runs the full verification pipeline on a sample of scholarships
and reports what would change, WITHOUT modifying the database.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import get_engine
from app.models import Scholarship
from app.services.lifecycle_manager import evaluate_lifecycle
from app.services.next_cycle_discovery import discover_next_cycle
from app.services.official_source_fetcher import fetch_official_source
from app.services.scholarship_diff import diff_scholarship
from app.services.scholarship_extractor import extract_scholarship_information
from app.services.discovery_identity import find_exact_url_match, normalize_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    scholarship_id: int
    title: str
    country: str
    current_status: str
    proposed_status: str | None
    lifecycle_reason: str | None
    fetch_success: bool | None
    fetch_error: str | None
    changes_detected: list[dict] = field(default_factory=list)
    next_cycle_found: bool = False
    next_cycle_year: int | None = None
    duplicate_found: bool = False
    duplicate_id: int | None = None
    image_action: str | None = None
    proposed_db_changes: list[str] = field(default_factory=list)


def run_phase2_dry_run(scholarship_ids: list[int]) -> list[DryRunResult]:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    results = []
    try:
        for sid in scholarship_ids:
            scholarship = session.get(Scholarship, sid)
            if scholarship is None:
                logger.warning("Scholarship %d not found, skipping", sid)
                continue

            logger.info("Processing scholarship %d: %s", sid, scholarship.title)

            result = DryRunResult(
                scholarship_id=scholarship.id,
                title=scholarship.title,
                country=scholarship.country,
                current_status=scholarship.status or "open",
                proposed_status=None,
                lifecycle_reason=None,
                fetch_success=None,
                fetch_error=None,
            )

            normalized_url = normalize_url(scholarship.official_source_url) if scholarship.official_source_url else ""
            if normalized_url:
                fetch_result = fetch_official_source(normalized_url)
                result.fetch_success = fetch_result.success
                result.fetch_error = fetch_result.error_reason if not fetch_result.success else None

                if fetch_result.success:
                    extraction = extract_scholarship_information(
                        fetch_result.content or "", normalized_url
                    )
                    changeset = diff_scholarship(scholarship, extraction)

                    for change in changeset.changes:
                        if change.change_type.value == "modified" and change.is_update_candidate:
                            result.changes_detected.append({
                                "field": change.field,
                                "old": change.old_value,
                                "new": change.new_value,
                                "confidence": change.confidence,
                            })

                    if scholarship.status == "closed":
                        next_cycle = discover_next_cycle(session, scholarship)
                        result.next_cycle_found = next_cycle.discovered
                        result.next_cycle_year = next_cycle.next_cycle_year
                        if next_cycle.discovered and next_cycle.proposed_status == "upcoming":
                            result.proposed_status = "upcoming"
                            result.proposed_db_changes.append(
                                f"status: {scholarship.status} -> upcoming (next cycle {next_cycle.next_cycle_year})"
                            )

            evaluation = evaluate_lifecycle(
                scholarship,
                verification_result={"fetch_status": "success" if result.fetch_success else "failed"},
            )
            if evaluation.should_transition and not result.proposed_status:
                result.proposed_status = evaluation.proposed_state
                result.lifecycle_reason = evaluation.reason
                result.proposed_db_changes.append(
                    f"status: {scholarship.status} -> {evaluation.proposed_state} ({evaluation.reason})"
                )

            duplicate = find_exact_url_match(session, normalized_url) if normalized_url else None
            if duplicate and duplicate.id != scholarship.id:
                result.duplicate_found = True
                result.duplicate_id = duplicate.id

            if scholarship.image_url:
                result.image_action = "revalidate_stored_image"
            else:
                result.image_action = "eligible_for_image_discovery"

            results.append(result)
            logger.info(
                "Dry-run result for %d: status=%s -> %s, changes=%d, next_cycle=%s",
                sid,
                result.current_status,
                result.proposed_status or "no_change",
                len(result.changes_detected),
                result.next_cycle_found,
            )
    finally:
        session.close()

    return results


def main():
    scholarship_ids = [1, 3, 4, 5, 6, 7, 14, 27, 28, 30]
    results = run_phase2_dry_run(scholarship_ids)

    report = {
        "dry_run_timestamp": datetime.now(timezone.utc).isoformat(),
        "scholarships_checked": len(results),
        "results": [asdict(r) for r in results],
        "summary": {
            "fetch_failures": sum(1 for r in results if not r.fetch_success and r.fetch_success is not None),
            "status_changes_proposed": sum(1 for r in results if r.proposed_status and r.proposed_status != r.current_status),
            "next_cycles_discovered": sum(1 for r in results if r.next_cycle_found),
            "duplicates_found": sum(1 for r in results if r.duplicate_found),
            "changes_detected": sum(len(r.changes_detected) for r in results),
        },
    }

    output_path = "phase2_dry_run_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(json.dumps(report, indent=2, default=str))
    print(f"\nReport saved to {output_path}")


if __name__ == "__main__":
    main()
