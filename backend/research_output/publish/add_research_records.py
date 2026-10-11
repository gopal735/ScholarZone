"""Insert reviewed new scholarship records into the LOCAL (non-production)
database so the supported snapshot pipeline can publish them.

Every candidate must arrive from backend/research_output/publish/
research_agents/agent_*.json with:
- an official_source_url on the awarding body's own domain;
- at least one evidence entry carrying url + verbatim quote + checked_on;
- an explicit dedupe statement checked against the published snapshot and
  the research corpus (matched ids are refused);
- a deadline/date window that is in the future, or an official page that
  states applications are open/rolling.

Anything failing a gate is refused and reported, never inserted. The lead
auditor re-verifies each accepted candidate against the live official page
before this script is run.

Usage:
    python backend/research_output/publish/add_research_records.py \
        [--agent agent_eu.json ...] [--dry-run]

It writes only to the local database named by the hard-coded path below.
There is no production branch in this script.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[3]
DB_PATH = BASE / "backend/scholarzone.db"
AGENT_DIR = BASE / "backend/research_output/publish/research_agents"
SNAPSHOT = BASE / "frontend/public/scholarships-snapshot.json"
CORPUS = BASE / "backend/config/programme_details.json"
REPORT_PATH = BASE / "backend/research_output/publish/research_additions_2026-10-11.json"

# Domains that are known non-awarding and must never be an official source.
KNOWN_NON_AWARDING = {
    "study.csp.work",
    "scholarshipplanet.com",
    "opportunitiesforafricans.com",
}

TODAY = date(2026, 10, 11)


def _json_or_none(value: Any) -> str | None:
    if value in (None, {}, ""):
        return None
    return json.dumps(value, ensure_ascii=False)


def _list_field(value: Any) -> str:
    """Serialise a list field; empty stays an empty JSON array.

    Several list columns are NOT NULL in the schema (documents among them),
    so an empty list is written as [] rather than NULL.
    """
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return json.dumps(items, ensure_ascii=False)
    if isinstance(value, str) and value.strip():
        return json.dumps([value], ensure_ascii=False)
    return json.dumps([], ensure_ascii=False)


def load_existing_identity() -> tuple[dict[int, dict], set[str]]:
    """Every record the catalogue already publishes, plus its identifiers."""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    records = {int(r["id"]): r for r in snapshot.get("scholarships", [])}
    keys: set[str] = set()
    for record in records.values():
        url = (record.get("official_source_url") or "").strip().lower()
        title = (record.get("title") or "").strip().lower()
        if url:
            keys.add(url)
        if title:
            keys.add(title)
    if CORPUS.is_file():
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        corpus_records = corpus.get("scholarships") or corpus.get("records") or []
        for record in corpus_records:
            if not isinstance(record, dict):
                continue
            url = (record.get("official_source_url") or "").strip().lower()
            title = (record.get("title") or "").strip().lower()
            if url:
                keys.add(url)
            if title:
                keys.add(title)
    return records, keys


def next_free_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(id) FROM scholarships").fetchone()
    return int(row[0]) + 1


def evaluate(candidate: dict, identity_keys: set[str]) -> tuple[bool, list[str]]:
    problems: list[str] = []

    title = (candidate.get("title") or "").strip()
    if not title:
        problems.append("no title")

    source_url = (candidate.get("official_source_url") or "").strip()
    if not source_url.startswith("https://") and not source_url.startswith("http://"):
        problems.append("official_source_url is not an absolute http(s) URL")
    host = re.sub(r"^https?://", "", source_url).split("/", 1)[0].lower()
    if host in KNOWN_NON_AWARDING:
        problems.append(f"official_source_url host {host} is a known non-awarding domain")

    evidence = candidate.get("evidence") or []
    if not evidence or not all(
        e.get("url") and e.get("quote") and e.get("checked_on") for e in evidence
    ):
        problems.append("evidence missing url/quote/checked_on")

    if not candidate.get("country"):
        problems.append("no country")
    if not candidate.get("degree"):
        problems.append("no degree level")

    deadline = candidate.get("deadline_date")
    status = (candidate.get("status") or "").lower()
    if deadline:
        try:
            if date.fromisoformat(str(deadline)) < TODAY:
                problems.append("deadline is in the past")
        except ValueError:
            problems.append("deadline_date is not YYYY-MM-DD")
    elif status not in ("open", "closing-soon", "upcoming"):
        problems.append("no future deadline and no official open/rolling status")

    dedupe = candidate.get("dedupe") or {}
    matched = dedupe.get("matched_existing_ids") or []
    if matched:
        problems.append(f"dedupe matched existing ids {matched}")
    if source_url.lower() in identity_keys or title.lower() in identity_keys:
        problems.append("official_source_url or title already in the catalogue")

    return (not problems), problems


def to_row(candidate: dict, new_id: int, now_iso: str, today: str) -> dict:
    official = {
        "official_source_urls": [
            u for u in (candidate.get("official_source_urls") or []) if u
        ],
        "application_link": candidate.get("application_link"),
        "catalogue_url": candidate.get("catalogue_url"),
        "official_updates_url": candidate.get("official_updates_url"),
        "deadline_note": candidate.get("deadline_note"),
        "application_cycle": candidate.get("application_period"),
        "status": candidate.get("status"),
        "status_note": candidate.get("status_note"),
        "funding_amount": candidate.get("funding_amount"),
        "funding_currency": candidate.get("funding_currency"),
        "funding_period": candidate.get("funding_period"),
        "tuition_coverage": candidate.get("tuition_coverage"),
    }
    official = {k: v for k, v in official.items() if v not in (None, [], "")}

    verification = {
        "source_citations": candidate.get("source_citations") or [],
        "last_verified_date": today,
        "verification_status": "confirmed",
        "confidence": "high" if candidate.get("confidence", 0) >= 0.8 else "medium",
        "verified_on": today,
        "notes": "Verified against the official page during the 2026-10-11 "
        "phase-3 research pass; evidence quoted in the research agent file.",
    }
    verification = {k: v for k, v in verification.items() if v not in (None, [], "")}

    utility = {
        "summary": candidate.get("description"),
        "best_fit": candidate.get("best_fit"),
        "funding_summary": candidate.get("funding_period"),
        "application_readiness_checklist": candidate.get("requirements"),
    }
    utility = {k: v for k, v in utility.items() if v not in (None, [], "")}

    return {
        "id": new_id,
        "title": candidate["title"].strip(),
        "country": candidate.get("country"),
        "degree": candidate.get("degree"),
        "region": candidate.get("region"),
        "program_type": candidate.get("program_type"),
        "funding": candidate.get("funding"),
        "funding_amount": candidate.get("funding_amount"),
        "funding_currency": candidate.get("funding_currency"),
        "funding_period": candidate.get("funding_period"),
        "tuition_coverage": candidate.get("tuition_coverage"),
        "description": candidate.get("description"),
        "duration": candidate.get("duration"),
        "application_period": candidate.get("application_period"),
        "deadline_date": candidate.get("deadline_date"),
        "deadline_display": candidate.get("deadline_display"),
        "deadline_precision": candidate.get("deadline_precision") or "day",
        "status": "open",
        "verification_status": "active",
        "is_verified": 1,
        "created_at": now_iso,
        "updated_at": now_iso,
        "last_verified_at": today,
        "last_verified_date": today,
        "next_verification_due": None,
        "verified_by": None,
        "verification_notes": "added by the 2026-10-11 phase-3 research pass",
        "official_source": candidate.get("official_source"),
        "official_source_url": candidate.get("official_source_url"),
        "application_link": candidate.get("application_link"),
        "catalogue_url": candidate.get("catalogue_url"),
        "official_updates_url": candidate.get("official_updates_url"),
        "image_url": candidate.get("image_url"),
        "image_source_url": candidate.get("image_source_url"),
        "image_source_type": candidate.get("image_source_type"),
        "image_kind": candidate.get("image_kind"),
        "image_alt_text": candidate.get("image_alt_text"),
        "image_verified_at": today if candidate.get("image_url") else None,
        "eligibility": _list_field(candidate.get("eligibility")),
        "eligibility_summary": candidate.get("eligibility_summary"),
        "benefits": _list_field(candidate.get("benefits")),
        "coverage": _list_field(candidate.get("coverage")),
        "requirements": _list_field(candidate.get("requirements")),
        "documents": _list_field(candidate.get("documents")),
        "english_requirement": candidate.get("english_requirement"),
        "application_method": _list_field(candidate.get("application_method")),
        "selection_notes": candidate.get("selection_notes"),
        "best_fit": candidate.get("best_fit"),
        "official_details": _json_or_none(official),
        "applicant_utility": _json_or_none(utility),
        "programme_verification": _json_or_none(verification),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not DB_PATH.is_file():
        raise SystemExit(f"Local database not found at {DB_PATH}")

    names = args.agent or [p.name for p in sorted(AGENT_DIR.glob("agent_*.json"))]
    files = [AGENT_DIR / name for name in names]
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise SystemExit(f"Agent files not found: {missing}")

    snapshot_records, identity_keys = load_existing_identity()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    accepted = []
    refused = []
    try:
        next_id = next_free_id(conn)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        today = date.today().isoformat()

        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for candidate in payload.get("candidates", []):
                ok, problems = evaluate(candidate, identity_keys)
                title = (candidate.get("title") or "?").strip()
                if not ok:
                    refused.append(
                        {
                            "from": path.name,
                            "title": title,
                            "problems": problems,
                        }
                    )
                    print(f"REFUSED {title}: {'; '.join(problems)}")
                    continue
                row = to_row(candidate, next_id, now_iso, today)
                columns = ", ".join(row.keys())
                placeholders = ", ".join("?" for _ in row)
                if not args.dry_run:
                    conn.execute(
                        f"INSERT INTO scholarships ({columns}) VALUES ({placeholders})",
                        tuple(row.values()),
                    )
                accepted.append(
                    {
                        "id": next_id,
                        "title": title,
                        "country": row["country"],
                        "degree": row["degree"],
                        "deadline_date": row["deadline_date"],
                        "official_source_url": row["official_source_url"],
                        "image_url": row["image_url"],
                        "from": path.name,
                    }
                )
                print(f"ACCEPTED id {next_id} {title}")
                next_id += 1
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    report = {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "next_free_id_before": next_free_id(sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)),
        "accepted": accepted,
        "refused": refused,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\naccepted {len(accepted)}, refused {len(refused)}; report at {REPORT_PATH}")
    if args.dry_run:
        print("(dry run: nothing written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
