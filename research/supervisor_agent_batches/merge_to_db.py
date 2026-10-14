"""Merge live-research agent findings into the supervisor tables.

Reads every research/supervisor_agent_batches/output/batch_*.json produced by the
100 live research agents, validates it against the supervisor vocabulary in
app/services/supervisor_status.py, and writes:

  * professor_profiles        (deduplicated on official_profile_url)
  * scholarship_professor_links
  * supervisor_source_evidence
  * scholarship_supervisor_coverage

Run from the repo root with the backend venv interpreter. Use --dry-run to print
what would be written without touching the database.
"""

from __future__ import annotations

import argparse
import json
import glob
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "..", "backend", "scholarzone.db")

COVERAGE_STATUSES = {
    "verified_supervisors",
    "no_verified_supervisor_found",
    "not_applicable",
    "needs_verification",
    "source_blocked",
    "source_requires_rendering",
    "search_pending",
}
RELATIONSHIP_TYPES = {
    "potential_supervisor",
    "program_faculty",
    "research_group",
    "program_relevant_faculty",
}
SOURCE_TYPES = {
    "official_university_profile",
    "official_department_page",
    "official_research_group",
    "official_programme_page",
    "official_institution_domain",
    "secondary_aggregator",
}
AVAIL_SCOPES = {"masters_supervision", "phd_supervision", "postdoc_supervision", "funding"}
AVAIL_STATES = {"verified_yes", "verified_no", "unknown", "not_published", "stale"}

FRESHNESS_DAYS = 180


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")


def norm_email(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value or None


def profile_host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def load_outputs() -> list[dict]:
    items: list[dict] = []
    for path in sorted(glob.glob(os.path.join(HERE, "output", "batch_*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            print(f"[SKIP] {path}: unreadable JSON ({exc})")
            continue
        if isinstance(data, dict):
            data = [data]
        for obj in data:
            obj["_batch_file"] = os.path.basename(path)
            items.append(obj)
    return items


def validate(items: list[dict]) -> list[str]:
    problems: list[str] = []
    seen_by_path: dict[str, set[int]] = {}
    for obj in items:
        sid = obj.get("scholarship_id")
        outcome = obj.get("outcome")
        professors = obj.get("professors") or []
        origin = f"{obj.get('_batch_file')} scholarship={sid}"
        if not isinstance(sid, int):
            problems.append(f"{origin}: missing scholarship_id")
            continue
        seen_by_path.setdefault(obj.get("_batch_file"), set()).add(sid)
        if outcome not in COVERAGE_STATUSES:
            problems.append(f"{origin}: bad outcome '{outcome}'")
            continue
        if outcome == "verified_supervisors" and not professors:
            problems.append(f"{origin}: verified_supervisors with no professors")
        if outcome != "verified_supervisors" and professors:
            problems.append(f"{origin}: outcome {outcome} carries professors")
        if len(professors) > 3:
            problems.append(f"{origin}: more than 3 professors")
            professors = professors[:3]
        for prof in professors:
            name = prof.get("canonical_name")
            profile_url = prof.get("official_profile_url")
            if not name:
                problems.append(f"{origin}: professor without canonical_name")
            if not profile_url or not profile_url.startswith("http"):
                problems.append(f"{origin}: professor '{name}' without official_profile_url")
                continue
            rel = prof.get("relationship_type")
            if rel not in RELATIONSHIP_TYPES:
                problems.append(f"{origin}: professor '{name}' bad relationship_type '{rel}'")
            est = prof.get("evidence_source_type")
            if est not in SOURCE_TYPES:
                problems.append(f"{origin}: professor '{name}' bad evidence_source_type '{est}'")
            esu = prof.get("evidence_source_url")
            if not esu or not esu.startswith("http"):
                problems.append(f"{origin}: professor '{name}' without evidence_source_url")
            email = norm_email(prof.get("official_email"))
            if email and "@" not in email:
                problems.append(f"{origin}: professor '{name}' malformed email '{email}'")
            if prof.get("official_email_verified") is True and not email:
                problems.append(f"{origin}: professor '{name}' email_verified without email")
            conf = prof.get("confidence")
            if conf is not None and not (isinstance(conf, int) and 0 <= conf <= 100):
                problems.append(f"{origin}: professor '{name}' bad confidence '{conf}'")
            avail = prof.get("availability")
            if avail:
                if avail.get("scope") not in AVAIL_SCOPES:
                    problems.append(f"{origin}: professor '{name}' bad availability scope")
                if avail.get("state") not in AVAIL_STATES:
                    problems.append(f"{origin}: professor '{name}' bad availability state")
                if not avail.get("source_url"):
                    problems.append(f"{origin}: professor '{name}' availability without source_url")
    return problems


def merge(items: list[dict], dry_run: bool) -> dict:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    valid_sids = {
        row[0] for row in cur.execute("SELECT id FROM scholarships").fetchall()
    }

    # professor_profiles keyed by official_profile_url (the documented dedup key)
    professors: dict[str, dict] = {}
    links: list[dict] = []
    evidence: list[dict] = []
    coverage: dict[int, dict] = {}
    skipped_unknown: list[int] = []
    dropped_duplicates: list[tuple] = []

    now = now_iso()
    next_check = (datetime.now(timezone.utc) + timedelta(days=FRESHNESS_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S%z"
    )

    for obj in items:
        sid = obj.get("scholarship_id")
        if not isinstance(sid, int):
            continue
        if sid not in valid_sids:
            skipped_unknown.append(sid)
            continue
        outcome = obj.get("outcome")
        profs = obj.get("professors") or []
        publishable = 0
        for prof in profs[:3]:
            profile_url = prof["official_profile_url"].strip()
            email = norm_email(prof.get("official_email"))
            record = professors.get(profile_url)
            if record is None:
                record = {
                    "canonical_name": prof["canonical_name"].strip(),
                    "title": prof.get("title"),
                    "institution_name": (prof.get("institution_name") or "").strip(),
                    "department_name": prof.get("department_name"),
                    "official_profile_url": profile_url,
                    "official_email": email,
                    "official_email_verified": bool(prof.get("official_email_verified")) and bool(email),
                    "lab_url": prof.get("lab_url"),
                    "personal_academic_url": prof.get("personal_academic_url"),
                    "research_areas": prof.get("research_areas") or [],
                    "research_keywords": prof.get("research_keywords") or [],
                    "profile_status": "active",
                    "last_verified_at": now,
                    "next_verification_at": next_check,
                    "created_at": now,
                    "updated_at": now,
                }
                professors[profile_url] = record
            else:
                if record["canonical_name"] != prof["canonical_name"].strip():
                    # Two people sharing one profile URL: the schema makes that URL the
                    # person's identity, so the row cannot represent both. Keep the
                    # first, drop the later one and its links rather than misattribute
                    # the second person's relationship to the first person's record.
                    dropped_duplicates.append((sid, prof["canonical_name"].strip(), profile_url))
                    continue
                if email and not record["official_email"]:
                    record["official_email"] = email
                if prof.get("official_email_verified"):
                    record["official_email_verified"] = bool(email)

            evidence_url = prof["evidence_source_url"].strip()
            is_authoritative = prof.get("evidence_source_type") in SOURCE_TYPES - {"secondary_aggregator"}
            verified = bool(is_authoritative and profile_url)
            links.append({
                "scholarship_id": sid,
                "profile_url": profile_url,
                "relationship_type": prof["relationship_type"],
                "evidence_source_url": evidence_url,
                "evidence_source_type": prof["evidence_source_type"],
                "evidence_quote_or_summary": prof.get("evidence_quote_or_summary"),
                "retrieved_at": now,
                "verified_at": now if verified else None,
                "verification_status": "verified" if verified else "unverified",
                "confidence": prof.get("confidence"),
                "created_at": now,
                "updated_at": now,
            })
            evidence.append({
                "profile_url": profile_url,
                "scholarship_id": sid,
                "source_url": evidence_url,
                "source_host": profile_host(evidence_url),
                "source_type": prof["evidence_source_type"],
                "retrieved_at": now,
                "verified_at": now if verified else None,
                "verification_status": "verified" if verified else "unverified",
                "evidence_summary": prof.get("evidence_quote_or_summary"),
                "http_status": None,
                "content_hash": None,
            })
            if prof.get("availability"):
                evidence.append({
                    "profile_url": profile_url,
                    "scholarship_id": sid,
                    "source_url": prof["availability"]["source_url"],
                    "source_host": profile_host(prof["availability"]["source_url"]),
                    "source_type": "official_university_profile",
                    "retrieved_at": now,
                    "verified_at": now if verified else None,
                    "verification_status": "verified" if verified else "unverified",
                    "evidence_summary": f"availability {prof['availability']['scope']}={prof['availability']['state']}",
                    "http_status": None,
                    "content_hash": None,
                })
            if verified:
                publishable += 1
        coverage[sid] = {
            "scholarship_id": sid,
            "status": outcome,
            "verified_supervisor_count": publishable,
            # Provenance is only complete when the official source was actually read;
            # blocked/JS-only sources must not be recorded as completed negatives.
            "evidence_state": (
                "partial"
                if outcome in {"source_blocked", "source_requires_rendering", "needs_verification"}
                else "complete"
            ),
            "last_checked_at": now,
            "next_check_at": next_check,
            "last_error_summary": None,
            "created_at": now,
            "updated_at": now,
        }

    stats = {
        "results": len(items),
        "professors": len(professors),
        "links": len(links),
        "evidence_rows": len(evidence),
        "emails": sum(1 for p in professors.values() if p["official_email"]),
        "coverage_rows": len(coverage),
        "skipped_unknown_scholarships": len(skipped_unknown),
        "dropped_duplicate_professors": len(dropped_duplicates),
        "dry_run": dry_run,
    }
    print(json.dumps(stats, indent=1))
    for sid, name, url in dropped_duplicates:
        print(f"[DROPPED DUPLICATE] scholarship={sid} name={name} shared_url={url}")

    if dry_run:
        con.close()
        return stats

    with con:
        # ---- professor_profiles
        existing_profiles: dict[str, int] = {
            row[0]: row[1]
            for row in cur.execute(
                "SELECT official_profile_url, id FROM professor_profiles"
            ).fetchall()
        }
        for profile_url, rec in professors.items():
            if profile_url in existing_profiles:
                pid = existing_profiles[profile_url]
                cur.execute(
                    "UPDATE professor_profiles SET canonical_name=?, title=?, institution_name=?, "
                    "department_name=?, official_email=COALESCE(?, official_email), "
                    "official_email_verified=?, lab_url=COALESCE(?, lab_url), "
                    "research_areas=?, research_keywords=?, profile_status='active', "
                    "last_verified_at=?, next_verification_at=?, updated_at=? WHERE id=?",
                    (
                        rec["canonical_name"], rec["title"], rec["institution_name"],
                        rec["department_name"], rec["official_email"],
                        1 if rec["official_email_verified"] else 0,
                        rec["lab_url"], json.dumps(rec["research_areas"]),
                        json.dumps(rec["research_keywords"]), rec["last_verified_at"],
                        rec["next_verification_at"], rec["updated_at"], pid,
                    ),
                )
            else:
                cur.execute(
                    "INSERT INTO professor_profiles (canonical_name, title, institution_name, "
                    "department_name, official_profile_url, official_email, official_email_verified, "
                    "lab_url, personal_academic_url, research_areas, research_keywords, "
                    "profile_status, last_verified_at, next_verification_at, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rec["canonical_name"], rec["title"], rec["institution_name"],
                        rec["department_name"], rec["official_profile_url"],
                        rec["official_email"], 1 if rec["official_email_verified"] else 0,
                        rec["lab_url"], rec["personal_academic_url"],
                        json.dumps(rec["research_areas"]), json.dumps(rec["research_keywords"]),
                        rec["profile_status"], rec["last_verified_at"], rec["next_verification_at"],
                        rec["created_at"], rec["updated_at"],
                    ),
                )
                existing_profiles[profile_url] = cur.lastrowid

        # ---- scholarship_professor_links (idempotent on unique constraint)
        existing_links = {
            (row[0], row[1], row[2])
            for row in cur.execute(
                "SELECT scholarship_id, professor_id, relationship_type FROM scholarship_professor_links"
            ).fetchall()
        }
        link_ids: dict[tuple, int] = {}
        for link in links:
            pid = existing_profiles[link["profile_url"]]
            key = (link["scholarship_id"], pid, link["relationship_type"])
            if key in existing_links:
                row = cur.execute(
                    "SELECT id FROM scholarship_professor_links WHERE scholarship_id=? AND professor_id=? AND relationship_type=?",
                    key,
                ).fetchone()
                link_ids[key] = row[0]
                cur.execute(
                    "UPDATE scholarship_professor_links SET evidence_source_url=?, evidence_source_type=?, "
                    "evidence_quote_or_summary=?, retrieved_at=?, verified_at=?, verification_status=?, "
                    "confidence=?, updated_at=? WHERE id=?",
                    (
                        link["evidence_source_url"], link["evidence_source_type"],
                        link["evidence_quote_or_summary"], link["retrieved_at"],
                        link["verified_at"], link["verification_status"],
                        link["confidence"], link["updated_at"], row[0],
                    ),
                )
            else:
                cur.execute(
                    "INSERT INTO scholarship_professor_links (scholarship_id, professor_id, "
                    "relationship_type, evidence_source_url, evidence_source_type, "
                    "evidence_quote_or_summary, retrieved_at, verified_at, verification_status, "
                    "confidence, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        link["scholarship_id"], pid, link["relationship_type"],
                        link["evidence_source_url"], link["evidence_source_type"],
                        link["evidence_quote_or_summary"], link["retrieved_at"],
                        link["verified_at"], link["verification_status"], link["confidence"],
                        link["created_at"], link["updated_at"],
                    ),
                )
                link_ids[key] = cur.lastrowid
            existing_links.add(key)

        # ---- supervisor_source_evidence
        existing_evidence = {
            (row[0], row[1], row[2])
            for row in cur.execute(
                "SELECT professor_id, source_url, source_type FROM supervisor_source_evidence"
            ).fetchall()
        }
        for ev in evidence:
            pid = existing_profiles[ev["profile_url"]]
            key = (pid, ev["source_url"], ev["source_type"])
            if key in existing_evidence:
                continue
            link_id = None
            for link in links:
                if (
                    link["profile_url"] == ev["profile_url"]
                    and link["scholarship_id"] == ev["scholarship_id"]
                    and link["evidence_source_url"] == ev["source_url"]
                ):
                    link_id = link_ids[(link["scholarship_id"], pid, link["relationship_type"])]
                    break
            cur.execute(
                "INSERT INTO supervisor_source_evidence (professor_id, scholarship_id, link_id, "
                "source_url, source_host, source_type, retrieved_at, verified_at, "
                "verification_status, evidence_summary, http_status, content_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    pid, ev["scholarship_id"], link_id, ev["source_url"], ev["source_host"],
                    ev["source_type"], ev["retrieved_at"], ev["verified_at"],
                    ev["verification_status"], ev["evidence_summary"], ev["http_status"],
                    ev["content_hash"],
                ),
            )
            existing_evidence.add(key)

        # ---- coverage upsert (unique on scholarship_id)
        for cov in coverage.values():
            cur.execute(
                "INSERT INTO scholarship_supervisor_coverage (scholarship_id, status, "
                "verified_supervisor_count, evidence_state, last_checked_at, next_check_at, "
                "last_error_summary, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(scholarship_id) DO UPDATE SET status=excluded.status, "
                "verified_supervisor_count=excluded.verified_supervisor_count, "
                "evidence_state=excluded.evidence_state, last_checked_at=excluded.last_checked_at, "
                "next_check_at=excluded.next_check_at, last_error_summary=NULL, updated_at=excluded.updated_at",
                (
                    cov["scholarship_id"], cov["status"], cov["verified_supervisor_count"],
                    cov["evidence_state"], cov["last_checked_at"], cov["next_check_at"],
                    cov["last_error_summary"], cov["created_at"], cov["updated_at"],
                ),
            )
    con.close()
    return stats


def sanitize_items(items: list[dict]) -> list[dict]:
    """Drop only unmergeable professors, never a whole scholarship silently.

    A scholarship whose outcome is valid is always written, even when one of its
    professor entries is malformed; the malformed professors are reported instead.
    """
    clean: list[dict] = []
    for obj in items:
        outcome = obj.get("outcome")
        if outcome not in COVERAGE_STATUSES:
            print(f"[DROPPED] {obj.get('_batch_file')} scholarship={obj.get('scholarship_id')}: "
                  f"bad outcome '{outcome}'")
            continue
        professors = obj.get("professors") or []
        kept = []
        for prof in professors:
            if not (prof.get("official_profile_url") and prof.get("canonical_name")):
                reason = "missing canonical_name" if not prof.get("canonical_name") else "missing official_profile_url"
            elif prof.get("relationship_type") not in RELATIONSHIP_TYPES:
                reason = f"bad relationship_type '{prof.get('relationship_type')}'"
            elif prof.get("evidence_source_type") not in SOURCE_TYPES:
                reason = f"bad evidence_source_type '{prof.get('evidence_source_type')}'"
            else:
                reason = None
            if reason:
                print(f"[DROPPED PROFESSOR] {obj.get('_batch_file')} "
                      f"scholarship={obj.get('scholarship_id')} "
                      f"name={prof.get('canonical_name')!r}: {reason}")
                continue
            # A malformed email must not reach the public payload, but the supervisor
            # itself is still valid evidence, so blank the address rather than the person.
            email = norm_email(prof.get("official_email"))
            if email and "@" not in email:
                print(f"[NULLED EMAIL] {obj.get('_batch_file')} "
                      f"scholarship={obj.get('scholarship_id')} "
                      f"name={prof.get('canonical_name')!r}: malformed email {email!r}")
                prof = {**prof, "official_email": None, "official_email_verified": False}
            kept.append(prof)
        if outcome == "verified_supervisors" and not kept:
            print(f"[DROPPED] {obj.get('_batch_file')} "
                  f"scholarship={obj.get('scholarship_id')}: "
                  f"verified_supervisors with no mergeable professors")
            continue
        clean.append({**obj, "professors": kept})
    return clean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    items = load_outputs()
    print(f"loaded {len(items)} result objects from output batches")
    problems = validate(items)
    for p in problems[:80]:
        print("[INVALID]", p)
    if len(problems) > 80:
        print(f"... and {len(problems) - 80} more validation problems")
    # invalid rows are reported above and dropped from the merge, not written
    items = [
        obj for obj in items
        if isinstance(obj.get("scholarship_id"), int)
    ]
    items = sanitize_items(items)
    print(f"valid result objects: {len(items)}")
    merge(items, args.dry_run)


if __name__ == "__main__":
    main()
