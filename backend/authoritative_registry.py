"""Authoritative registry builder and dry-run selector for image population.

Merges:
- Database state (image_verified_at, reviews, history)
- All previous JSON/CSV batch reports

Defines a scholarship as "processed" if it has a terminal result in any source:
  APPROVED, HUMAN_REVIEW, REJECTED, NO_IMAGE, FAILED_PERMANENT

Then selects the next 10 truly unprocessed IDs for dry-run verification.
NO database writes are performed.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add backend to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import func, select

from app.database import get_session_factory
from app.models import Scholarship, ScholarshipReview, ScholarshipVerificationHistory

REPORT_DIR = backend_dir / "reports"

TERMINAL_DECISIONS = {
    "approved", "human_review", "rejected", "no_image", "failed_permanent",
    "APPROVED", "HUMAN_REVIEW", "REJECTED", "NO_IMAGE", "FAILED_PERMANENT",
}


@dataclass
class RegistrySource:
    source_type: str
    source_file: str
    scholarship_id: int
    decision: str | None
    timestamp: str | None = None


def _normalize_decision(decision: str | None) -> str | None:
    if not decision:
        return None
    d = decision.strip().lower()
    mapping = {
        "approved": "APPROVED",
        "human_review": "HUMAN_REVIEW",
        "rejected": "REJECTED",
        "no_candidates": "NO_IMAGE",
        "no_valid_candidates": "NO_IMAGE",
        "no_candidate_found": "NO_IMAGE",
        "failed": "FAILED_PERMANENT",
        "failed_permanent": "FAILED_PERMANENT",
        "error": "FAILED_PERMANENT",
    }
    return mapping.get(d, d.upper() if d in TERMINAL_DECISIONS else None)


def _extract_from_json_report(filepath: Path) -> list[RegistrySource]:
    sources = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return sources

    records = data if isinstance(data, list) else [data]

    for item in records:
        if not isinstance(item, dict):
            continue
        sid = item.get("scholarship_id")
        if sid is None:
            continue
        decision = _normalize_decision(
            item.get("decision")
            or item.get("validation_result")
            or item.get("result")
        )
        if decision:
            sources.append(RegistrySource(
                source_type="report",
                source_file=filepath.name,
                scholarship_id=int(sid),
                decision=decision,
                timestamp=item.get("processed_at") or item.get("timestamp"),
            ))
    return sources


def _extract_from_csv_report(filepath: Path) -> list[RegistrySource]:
    sources = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid_raw = row.get("scholarship_id") or row.get("ID") or row.get("id")
                if not sid_raw:
                    continue
                try:
                    sid = int(sid_raw)
                except ValueError:
                    continue
                decision = _normalize_decision(
                    row.get("decision")
                    or row.get("validation_result")
                    or row.get("result")
                    or row.get("Decision")
                    or row.get("Status")
                )
                if decision:
                    sources.append(RegistrySource(
                        source_type="report",
                        source_file=filepath.name,
                        scholarship_id=sid,
                        decision=decision,
                        timestamp=row.get("timestamp") or row.get("Timestamp"),
                    ))
    except Exception:
        pass
    return sources


def _extract_from_database() -> list[RegistrySource]:
    sources = []
    session_factory = get_session_factory()
    session = session_factory()

    try:
        # APPROVED: image_verified_at IS NOT NULL
        approved = session.execute(
            select(Scholarship.id, Scholarship.image_verified_at)
            .where(Scholarship.image_verified_at.is_not(None))
        ).all()
        for sid, ts in approved:
            ts_str = ts.isoformat() if ts else None
            sources.append(RegistrySource(
                source_type="database",
                source_file="scholarships.image_verified_at",
                scholarship_id=sid,
                decision="APPROVED",
                timestamp=ts_str,
            ))

        # HUMAN_REVIEW / REJECTED: existing image_url reviews (even pending = already routed)
        reviews = session.execute(
            select(ScholarshipReview.scholarship_id, ScholarshipReview.decision, ScholarshipReview.created_at)
            .where(ScholarshipReview.field_name == "image_url")
        ).all()
        for sid, decision, ts in reviews:
            if decision and decision.strip().lower() != "pending":
                norm = _normalize_decision(decision)
            else:
                norm = "HUMAN_REVIEW"
            sources.append(RegistrySource(
                source_type="database",
                source_file="scholarship_reviews",
                scholarship_id=sid,
                decision=norm,
                timestamp=ts.isoformat() if ts else None,
            ))

        # APPROVED via history
        history = session.execute(
            select(ScholarshipVerificationHistory.scholarship_id, ScholarshipVerificationHistory.created_at)
            .where(ScholarshipVerificationHistory.field_name == "image_url")
        ).all()
        for sid, ts in history:
            ts_str = ts.isoformat() if ts else None
            sources.append(RegistrySource(
                source_type="database",
                source_file="scholarship_verification_history",
                scholarship_id=sid,
                decision="APPROVED",
                timestamp=ts_str,
            ))
    finally:
        session.close()

    return sources


def build_authoritative_registry() -> dict[int, dict[str, Any]]:
    """Build a dict mapping scholarship_id -> {decision, sources, timestamp}.

    A scholarship is processed if ANY source reports a terminal decision.
    If multiple sources agree, the most recent terminal decision wins.
    """
    all_sources: list[RegistrySource] = []

    # Scan report files — exclude dry-run / discovery-only reports because they
    # represent read-only evaluations, not completed processing batches.
    dry_run_exclusions = {"dry_run", "pilot", "discovery_results", "discovery_targeted", "discovery_progress"}
    for pattern in ["**/*.json", "**/*.csv"]:
        for filepath in REPORT_DIR.rglob(pattern):
            if filepath.is_file():
                name_lower = filepath.name.lower()
                if any(excl in name_lower for excl in dry_run_exclusions):
                    continue
                if filepath.suffix.lower() == ".json":
                    all_sources.extend(_extract_from_json_report(filepath))
                elif filepath.suffix.lower() == ".csv":
                    all_sources.extend(_extract_from_csv_report(filepath))

    # Scan root-level report files too (exclude dry runs)
    for pattern in ["*.json", "*.csv"]:
        for filepath in backend_dir.glob(pattern):
            if filepath.is_file() and "report" in filepath.name.lower():
                name_lower = filepath.name.lower()
                if any(excl in name_lower for excl in dry_run_exclusions):
                    continue
                if filepath.suffix.lower() == ".json":
                    all_sources.extend(_extract_from_json_report(filepath))
                elif filepath.suffix.lower() == ".csv":
                    all_sources.extend(_extract_from_csv_report(filepath))

    # Scan database
    all_sources.extend(_extract_from_database())

    # Include original PROCESSED_IDS from batch_image_population.py as manual override
    # for IDs that were processed before database tracking was fully implemented.
    legacy_processed_ids = (
        set(range(1, 26)) | {27, 58, 62, 80, 98, 116, 161, 245}
    )
    for sid in legacy_processed_ids:
        all_sources.append(RegistrySource(
            source_type="legacy_registry",
            source_file="batch_image_population.py PROCESSED_IDS",
            scholarship_id=sid,
            decision="PROCESSED",
        ))

    # Build registry
    registry: dict[int, dict[str, Any]] = {}
    for src in all_sources:
        sid = src.scholarship_id
        if sid not in registry:
            registry[sid] = {
                "decision": src.decision,
                "sources": [src.source_file],
                "timestamp": src.timestamp,
            }
        else:
            registry[sid]["sources"].append(src.source_file)
            # Prefer more recent timestamp if available
            if src.timestamp and (registry[sid]["timestamp"] is None or src.timestamp > registry[sid]["timestamp"]):
                registry[sid]["timestamp"] = src.timestamp
                registry[sid]["decision"] = src.decision

    return registry


def get_unprocessed_scholarships(limit: int = 10) -> list[dict[str, Any]]:
    """Return the next `limit` unprocessed scholarships for dry-run selection.

    A scholarship is unprocessed if:
    - It is NOT in the authoritative registry
    - AND it has no image_url set (or image_url is NULL)
    """
    registry = build_authoritative_registry()
    processed_ids = set(registry.keys())

    session_factory = get_session_factory()
    session = session_factory()

    try:
        query = (
            select(Scholarship)
            .where(~Scholarship.id.in_(processed_ids))
            .where(Scholarship.image_url.is_(None))
            .order_by(Scholarship.id)
            .limit(limit)
        )
        scholarships = session.execute(query).scalars().all()
    finally:
        session.close()

    results = []
    for s in scholarships:
        results.append({
            "id": s.id,
            "title": s.title,
            "official_source_url": s.official_source_url,
            "image_url": s.image_url,
            "in_registry": s.id in processed_ids,
            "registry_decision": registry.get(s.id, {}).get("decision"),
            "registry_sources": registry.get(s.id, {}).get("sources", []),
        })

    return results


def main():
    print("=" * 80)
    print("AUTHORITATIVE REGISTRY — DRY-RUN SELECTION")
    print("=" * 80)

    # Build registry
    print("\nBuilding authoritative registry from database + all reports...")
    registry = build_authoritative_registry()
    processed_ids = set(registry.keys())
    print(f"Total processed scholarships in registry: {len(processed_ids)}")

    # Show breakdown
    decisions: dict[str, int] = {}
    for info in registry.values():
        d = info.get("decision", "UNKNOWN")
        decisions[d] = decisions.get(d, 0) + 1
    print("Decision breakdown:")
    for d, count in sorted(decisions.items()):
        print(f"  {d}: {count}")

    # Select next batch
    print("\nSelecting next 10 truly unprocessed scholarships...")
    selected = get_unprocessed_scholarships(limit=10)
    selected_ids = [s["id"] for s in selected]

    print(f"Selected IDs: {selected_ids}")
    print(f"Count: {len(selected_ids)}")

    # Verify exactly 10
    if len(selected_ids) != 10:
        print(f"ERROR: Expected 10 IDs, got {len(selected_ids)}")
        return []

    # Verify all image_url = NULL
    all_null = True
    for s in selected:
        if s["image_url"] is not None:
            print(f"ERROR: ID {s['id']} has image_url = {s['image_url']}")
            all_null = False
    if not all_null:
        return []

    # Verify none in registry
    conflicts = [sid for sid in selected_ids if sid in processed_ids]
    if conflicts:
        print(f"ERROR: Previously processed IDs detected: {conflicts}")
        for sid in conflicts:
            info = registry[sid]
            print(f"  ID {sid}: decision={info.get('decision')}, sources={info.get('sources', [])[:3]}")
        return []

    print("Verification passed: exactly 10 IDs, all image_url = NULL, none in registry")
    print("=" * 80)

    # Print selected IDs detail
    print("\nSELECTED IDs FOR NEXT BATCH (DRY RUN — NO DB WRITES)")
    print("-" * 80)
    for s in selected:
        print(f"ID {s['id']}: {s['title'][:70]}")
        print(f"  Official Source: {s['official_source_url']}")
        print(f"  Image URL:       {s['image_url']}")
        print(f"  In Registry:     {s['in_registry']}")
        print()

    # Summary
    session_factory2 = get_session_factory()
    session2 = session_factory2()
    try:
        total = session2.scalar(select(func.count(Scholarship.id)))
        with_image = session2.scalar(
            select(func.count(Scholarship.id)).where(Scholarship.image_url.is_not(None))
        )
        remaining = session2.scalar(
            select(func.count(Scholarship.id)).where(Scholarship.image_url.is_(None))
        )
    finally:
        session2.close()

    print("-" * 80)
    print("DATABASE SUMMARY")
    print("-" * 80)
    print(f"Total scholarships:           {total}")
    print(f"With image_url set:           {with_image}")
    print(f"Without image_url (remaining): {remaining}")
    print(f"Processed in registry:        {len(processed_ids)}")
    print(f"Selected for next batch:      {len(selected_ids)}")
    print("=" * 80)
    print("\nDatabase writes: 0")
    print("Batch 6 NOT started.")

    return selected


if __name__ == "__main__":
    main()
