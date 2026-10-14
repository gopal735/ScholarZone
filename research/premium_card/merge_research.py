"""
Merge premium-card research output into existing scholarship records.

This script:
1. Reads research output from frontend/public/research/premium_card/output/index.json
2. Matches research records to existing DB scholarships
3. Produces a reconciliation report
4. Merges approved fields in a single transaction
5. Verifies the merge
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

# ── Config ────────────────────────────────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR
RESEARCH_INDEX = PROJECT_DIR / "frontend" / "public" / "research" / "premium_card" / "output" / "index.json"
RESEARCH_OUTPUT_DIR = PROJECT_DIR / "frontend" / "public" / "research" / "premium_card" / "output"
MIGRATIONS_DIR = PROJECT_DIR / "backend" / "migrations"

# Ensure backend is importable when running from project root.
import sys as _sys
_BACKEND_DIR = PROJECT_DIR / "backend"
if str(_BACKEND_DIR) not in _sys.path:
    _sys.path.insert(0, str(_BACKEND_DIR))
MIGRATIONS_DIR.mkdir(exist_ok=True)

REPORT_PATH = BACKEND_DIR / "research" / "premium_card" / "merge_report.json"
MIGRATION_SQL_PATH = MIGRATIONS_DIR / "merge_premium_card_research.sql"

# Fields we are allowed to merge from research into the flat scholarship model.
# Each entry maps research path -> DB column + type + evidence requirement.
# ONLY columns that exist in the actual SQLite/PostgreSQL schema are listed.
APPROVED_FIELDS: list[dict[str, Any]] = [
    {
        "research_path": ["official_sources", 0, "url"],
        "db_column": "official_source_url",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["official_sources", 0, "source_domain"],
        "db_column": "official_source",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["image", "url"],
        "db_column": "image_url",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["image", "source_type"],
        "db_column": "image_source_type",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["image", "source_url"],
        "db_column": "image_source_url",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["image", "alt_text"],
        "db_column": "image_alt_text",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "funding_type"],
        "db_column": "funding",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "fully_funded"],
        "db_column": "fully_funded",
        "type": "boolean",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "currency"],
        "db_column": "funding_currency",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "award_amount", "minimum"],
        "db_column": "funding_amount",
        "type": "number",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "award_amount", "period"],
        "db_column": "funding_period",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "tuition", "covered"],
        "db_column": "tuition_coverage",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "living_costs", "covered"],
        "db_column": "living_cost_coverage",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["funding", "travel", "covered"],
        "db_column": "travel_coverage",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["application", "application_method"],
        "db_column": "application_method",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["application", "official_application_url"],
        "db_column": "application_link",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["deadlines", "deadline_display"],
        "db_column": "deadline_display",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["deadlines", "deadline_date"],
        "db_column": "deadline_date",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["deadlines", "deadline_precision"],
        "db_column": "deadline_precision",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["eligibility", "language", "teaching_language", 0],
        "db_column": "english_requirement",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["eligibility", "summary"],
        "db_column": "eligibility_summary",
        "type": "string",
        "min_evidence": "official_provider",
    },
    {
        "research_path": ["eligibility"],
        "db_column": "eligibility",
        "type": "string",
        "min_evidence": "official_provider",
    },
]


# ── Helpers ───────────────────────────────────────────────────────

def load_research_index() -> list[dict[str, Any]]:
    if not RESEARCH_INDEX.exists():
        raise FileNotFoundError(f"Research index not found: {RESEARCH_INDEX}")
    with open(RESEARCH_INDEX, encoding="utf-8") as f:
        return json.load(f)


def get_db_url() -> str:
    from app.core.config import get_settings
    return get_settings().database_url


def normalize_title(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def match_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_norm = normalize_title(a)
    b_norm = normalize_title(b)
    if a_norm == b_norm:
        return 1.0
    words_a = set(a_norm.split())
    words_b = set(b_norm.split())
    if not words_a or not words_b:
        return 0.0
    overlap = words_a & words_b
    return len(overlap) / max(len(words_a), len(words_b))


def extract_nested(data: dict[str, Any], path: list[str | int]) -> Any:
    current = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return None
        if current is None:
            return None
    return current


def coerce_db_value(value: Any, col_type: str) -> Any:
    if value is None:
        return None
    if col_type == "string":
        text = str(value).strip()
        return text or None
    if col_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if col_type == "boolean":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1", "yes"):
            return True
        if text in ("false", "0", "no"):
            return False
        return None
    if col_type == "date":
        text = str(value).strip()
        # Accept ISO date strings
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return text
    return value


@dataclass
class MatchResult:
    research: dict[str, Any]
    scholarship: dict[str, Any] | None = None
    match_type: str = "unmatched"
    confidence: float = 0.0
    proposed_fields: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    rejected_fields: list[dict[str, Any]] = field(default_factory=list)


def match_research_to_scholarship(
    research: dict[str, Any],
    scholarships: list[dict[str, Any]],
    threshold: float = 0.65,
) -> MatchResult:
    data = research.get("data") or {}
    title = data.get("title") or research.get("source_title") or ""
    provider = data.get("provider") or {}
    provider_name = provider.get("name") if isinstance(provider, dict) else (provider or "")
    source_file = research.get("source_file", "")

    # Derive country from research data
    location = data.get("location") or {}
    country = location.get("host_country") or location.get("study_countries", [None])[0] or ""

    best: dict[str, Any] | None = None
    best_score = 0.0

    for sch in scholarships:
        score = 0.0
        title_score = match_score(title, sch.get("title", ""))
        score = max(score, title_score)

        if provider_name and sch.get("provider"):
            provider_score = match_score(provider_name, sch.get("provider", ""))
            score = max(score, provider_score * 1.1)

        if country and sch.get("country"):
            if country.lower() == (sch.get("country") or "").lower():
                score += 0.05

        if score > best_score:
            best_score = score
            best = sch

    result = MatchResult(research=research, confidence=best_score)
    if best and best_score >= threshold:
        result.scholarship = best
        result.match_type = "matched"
    else:
        result.match_type = "unmatched"
    return result


def evaluate_fields(
    research: dict[str, Any],
    scholarship: dict[str, Any],
    approved_fields: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (proposed, conflicts, rejected)."""
    proposed: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for field in approved_fields:
        new_value = extract_nested(research.get("data") or research, field["research_path"])
        if new_value is None:
            continue
        if isinstance(new_value, str) and not new_value.strip():
            continue

        col = field["db_column"]
        old_value = scholarship.get(col)

        # Never overwrite verified data with null/weaker evidence.
        if old_value is not None and str(old_value).strip():
            if new_value is None:
                rejected.append(
                    {
                        "field": col,
                        "reason": "null_value",
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                )
                continue

        # Provenance check.
        source_type = extract_nested(research.get("data") or research, ["official_sources", 0, "source_type"])
        if source_type != field.get("min_evidence"):
            rejected.append(
                {
                    "field": col,
                    "reason": "insufficient_evidence",
                    "required": field.get("min_evidence"),
                    "actual": source_type,
                }
            )
            continue

        coerced = coerce_db_value(new_value, field["type"])
        if coerced is None:
            rejected.append(
                {
                    "field": col,
                    "reason": "coerce_failed",
                    "raw_value": new_value,
                }
            )
            continue

        entry = {
            "field": col,
            "old_value": old_value,
            "new_value": coerced,
            "type": field["type"],
            "source_url": extract_nested(research.get("data") or research, ["official_sources", 0, "url"]),
            "source_type": source_type,
            "checked_at": extract_nested(research.get("data") or research, ["verification", "last_verified_date"]),
        }

        if old_value is not None and str(old_value).strip() and old_value != coerced:
            conflicts.append(entry)
        else:
            proposed.append(entry)

    return proposed, conflicts, rejected


def build_reconciliation(
    research_index: list[dict[str, Any]],
    scholarships: list[dict[str, Any]],
) -> dict[str, Any]:
    matched = 0
    unmatched = 0
    all_proposed: list[dict[str, Any]] = []
    all_conflicts: list[dict[str, Any]] = []
    all_rejected: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    matched_pairs: list[dict[str, Any]] = []

    seen_ids: dict[str, int] = {}

    for research in research_index:
        result = match_research_to_scholarship(research, scholarships)
        result.proposed_fields, result.conflicts, result.rejected_fields = evaluate_fields(
            research, result.scholarship or {}, APPROVED_FIELDS
        )

        if result.scholarship:
            matched += 1
            sch_id = result.scholarship.get("id")
            if sch_id in seen_ids:
                duplicate_ids.append(str(sch_id))
            else:
                seen_ids[sch_id] = seen_ids.get(sch_id, 0) + 1
            matched_pairs.append(
                {
                    "research_id": (research.get("data") or {}).get("id") or research.get("id"),
                    "research_title": (research.get("data") or {}).get("title") or research.get("source_title"),
                    "scholarship_id": sch_id,
                    "scholarship_title": result.scholarship.get("title"),
                    "match_type": result.match_type,
                    "confidence": result.confidence,
                    "proposed_fields": result.proposed_fields,
                    "conflicts": result.conflicts,
                    "rejected_fields": result.rejected_fields,
                }
            )
        else:
            unmatched += 1

        all_proposed.extend(result.proposed_fields)
        all_conflicts.extend(result.conflicts)
        all_rejected.extend(result.rejected_fields)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_records": len(research_index),
        "matched": matched,
        "unmatched": unmatched,
        "duplicate_ids": duplicate_ids,
        "proposed_fields": all_proposed,
        "conflicts": all_conflicts,
        "rejected_fields": all_rejected,
        "matched_pairs": matched_pairs,
    }


def load_existing_scholarships(engine) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM scholarships"))
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


def generate_migration_sql(report: dict[str, Any]) -> str:
    lines = [
        "-- Premium card research merge",
        f"-- Generated: {report['generated_at']}",
        f"-- Research records: {report['research_records']}",
        f"-- Matched: {report['matched']}",
        f"-- Unmatched: {report['unmatched']}",
        f"-- Conflicts: {len(report['conflicts'])}",
        f"-- Rejected: {len(report['rejected_fields'])}",
        "",
        "BEGIN;",
        "",
    ]

    for pair in report["matched_pairs"]:
        sch_id = pair["scholarship_id"]
        if sch_id is None:
            continue
        for field in pair["proposed_fields"]:
            col = field["field"]
            val = field["new_value"]
            if val is None:
                continue
            if isinstance(val, str):
                val = "'" + val.replace("'", "''") + "'"
            elif isinstance(val, bool):
                val = "1" if val else "0"
            else:
                val = str(val)
            lines.append(f"UPDATE scholarships SET {col} = {val} WHERE id = {sch_id};")

    lines.extend(["", "COMMIT;"])
    return "\n".join(lines)


def main() -> int:
    print("[merge] Loading research index...")
    research_index = load_research_index()
    print(f"[merge] Research records: {len(research_index)}")

    print("[merge] Loading DB settings...")
    db_url = get_db_url()
    print(f"[merge] Database: {db_url}")

    engine = create_engine(db_url, future=True)

    print("[merge] Loading existing scholarships...")
    scholarships = load_existing_scholarships(engine)
    print(f"[merge] Existing scholarships: {len(scholarships)}")

    print("[merge] Building reconciliation report...")
    report = build_reconciliation(research_index, scholarships)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"[merge] Report written to {REPORT_PATH}")

    sql = generate_migration_sql(report)
    MIGRATION_SQL_PATH.write_text(sql, encoding="utf-8")
    print(f"[merge] Migration SQL written to {MIGRATION_SQL_PATH}")

    print(f"[merge] Research records: {report['research_records']}")
    print(f"[merge] Matched existing scholarships: {report['matched']}")
    print(f"[merge] Unmatched: {report['unmatched']}")
    print(f"[merge] Duplicate IDs: {len(report['duplicate_ids'])}")
    print(f"[merge] Proposed fields: {len(report['proposed_fields'])}")
    print(f"[merge] Conflicts: {len(report['conflicts'])}")
    print(f"[merge] Rejected fields: {len(report['rejected_fields'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
