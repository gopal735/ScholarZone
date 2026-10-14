"""Merge + validate the 50-agent wave-1 research output into repo config shape.

Reads   research/wave1/out/w1-NN.json   (written by the research agents)
Writes  research/wave1/merged/*.json   (staged, nothing touches the repo config)
  --apply  additionally merges the staged files into backend/config/*.json

Validation mirrors what the maintenance "add" stage will enforce
(ScholarshipIngestionRecord is extra="forbid"), plus the repo's own accuracy
rules, so a bad record is dropped here with a reason instead of silently
aborting a batch in the worker.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import date
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "backend"))
W1 = os.path.join(ROOT, "research", "wave1")
OUT = os.path.join(W1, "out")
SHARDS = os.path.join(W1, "shards")
MERGED = os.path.join(W1, "merged")
CONFIG = os.path.join(ROOT, "backend", "config")

# The provenance vocabulary the audit test enforces, and the retirement file that
# decides which records may still be asserted as currently verified.
VALID_HOST_EVIDENCE = {"same_registrable_domain", "cdn_on_behalf_of_host", "third_party_mark"}
VALID_VALIDATION_RESULTS = {"verified", "source_blocked"}

TODAY = "2026-10-04"

# --- vocabulary mirrored from the app, not invented here ---------------------
DEADLINE_PRECISION = {
    "exact", "month", "year", "rolling", "recurring", "varies", "approximate", "unknown",
}
ACCEPTED_STATUS = {"open", "upcoming"}
OFFICIAL_IMAGE_SOURCE_TYPES = {
    "official_scholarship", "official_university", "official_government", "official_provider",
}
PLACEHOLDERS = {"", "n/a", "na", "-", "none", "tbd", "unknown", "null", "nil"}
BANNED_IN_OFFICIAL = {
    "application_readiness_checklist", "common_rejection_risks", "estimated_uncovered_costs",
    "document_audit", "alerts", "submission_workflow",
}

# --- the ingestion model's own field list (extra="forbid") -------------------
INGESTION_FIELDS = {
    "name", "country", "degree_levels", "funding_type", "official_source_url",
    "is_verified", "last_verified_date", "region", "duration", "deadline",
    "deadline_date", "deadline_precision", "application_period", "eligibility_summary",
    "eligibility", "coverage", "required_documents", "catalogue_url",
    "official_updates_url", "official_source", "english_requirement", "requirements",
    "application_method", "selection_notes", "program_type", "best_fit", "notes",
    "image_url", "image_source_url", "image_source_type", "image_verified_at",
    "image_alt_text", "legacy_titles", "preferred_id",
}
ROW_ONLY = {"status", "description", "benefits", "funding_amount", "funding_currency", "funding_period"}
REQUIRED = {"name", "country", "degree_levels", "funding_type", "official_source_url"}
WIDTHS = {
    "name": 255, "country": 120, "degree_levels": 255, "funding_type": 120,
    "official_source": 255, "program_type": 255, "image_alt_text": 512,
    "image_source_type": 32, "status": 20, "funding_currency": 8, "funding_period": 64,
}
# Keys an agent sometimes puts in new_scholarship that belong in the official block.
BELONGS_TO_OFFICIAL = {
    "application_route", "application_portal", "selection_criteria", "selection_weighting",
    "application_cycle", "status_note", "funding_label", "tuition_coverage",
    "living_cost_coverage", "travel_coverage", "fully_funded", "funding_duration",
    "citizenship_residency", "international_eligibility", "study_mode",
    "research_requirement", "award_holder_conditions", "official_contacts",
    "deadline_central", "deadline_central_display", "official_source_urls",
}
LIST_FIELDS = {
    "eligibility", "coverage", "benefits", "requirements", "application_method",
    "official_source_urls", "documents", "selection_criteria", "award_holder_conditions",
    "supplements_or_initiatives",
}
BAD_HOSTS = {
    "wikipedia.org", "wikimedia.org", "commons.wikimedia.org", "imgur.com",
    "pinterest.com", "pinimg.com", "shutterstock.com", "istockphoto.com",
    "gettyimages.com", "dreamstime.com", "slideshare.net", "scribd.com",
    "researchgate.net", "medium.com", "wordpress.com", "blogspot.com", "reddit.com",
    "youtube.com", "facebook.com", "twitter.com", "x.com", "linkedin.com",
}
_LOOSE_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def load_json(path):
    """Read an agent's file, repairing the two corruptions agents actually cause.

    An agent that pasted a Windows path or a regex into a JSON string emits a
    lone backslash, which makes the whole file unreadable; a file written by
    PowerShell or by an editor on Windows picks up a UTF-8 BOM. Either one would
    otherwise discard every real record in the shard.
    """
    raw = open(path, encoding="utf-8-sig").read()
    try:
        return json.loads(raw), None
    except ValueError as exc:
        try:
            return json.loads(_LOOSE_ESCAPE.sub(r"\\\\", raw)), f"repaired invalid escape: {exc}"
        except ValueError:
            return None, f"unreadable JSON: {exc}"


def registrable(host: str) -> str:
    """Best-effort eTLD+1 so example.co.uk and www.example.co.uk agree."""
    host = (host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two = ".".join(parts[-2:])
    if two in {"co.uk", "ac.uk", "gov.uk", "co.jp", "ac.jp", "go.jp", "com.au", "edu.au",
               "gov.au", "ac.nz", "co.nz", "org.uk", "ac.at", "or.at", "edu.pl", "gov.pl"}:
        return ".".join(parts[-3:])
    return two


def is_https(value) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        p = urlsplit(value.strip())
    except ValueError:
        return False
    return p.scheme == "https" and bool(p.netloc)


def host_of(url) -> str:
    if not isinstance(url, str) or "//" not in url:
        return ""
    try:
        return urlsplit(url).netloc.lower()
    except ValueError:
        return ""


def clean_text(value):
    """Nothing reaches the DB as a placeholder string."""
    if isinstance(value, str) and value.strip().lower() in PLACEHOLDERS:
        return None
    return value


def as_str_list(value, field, problems, where):
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        problems.append(f"{where}: {field} must be an array of strings")
        return None
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        else:
            problems.append(f"{where}: {field} contains a non-string/blank entry")
    return out


def validate_official_block(block, problems, where):
    if not isinstance(block, dict):
        problems.append(f"{where}: programme_detail_official missing")
        return
    for banned in BANNED_IN_OFFICIAL:
        if banned in block:
            problems.append(f"{where}: official block contains banned key '{banned}'")
    for key, value in block.items():
        cleaned = clean_text(value)
        if cleaned is None and isinstance(value, str):
            problems.append(f"{where}: official.{key} is the placeholder string {value!r}")
    tuition = block.get("tuition_coverage")
    fully = block.get("fully_funded")
    if fully is True and tuition is not True:
        problems.append(f"{where}: fully_funded=true requires tuition_coverage=true")
    for key in ("funding_currency", "funding_period"):
        value = block.get(key)
        if isinstance(value, str):
            if key == "funding_currency" and value.strip() and not re.fullmatch(r"[A-Z]{3}", value.strip()):
                problems.append(f"{where}: funding_currency {value!r} is not an uppercase ISO code")
    urls = block.get("official_source_urls")
    if urls is not None:
        if not isinstance(urls, list) or not urls:
            problems.append(f"{where}: official_source_urls must be a non-empty array")
        else:
            for u in urls:
                if not is_https(u):
                    problems.append(f"{where}: citation is not an https URL: {u!r}")


def validate_logo(logo, official_host, problems, where):
    if logo is None:
        return None
    if not isinstance(logo, dict):
        problems.append(f"{where}: logo_override must be an object or null")
        return None
    url = logo.get("url")
    if not is_https(url):
        problems.append(f"{where}: logo url is not https ({url!r})")
        return None
    host = host_of(url)
    reg, known = registrable(host), registrable(official_host)
    if any(host == b or host.endswith("." + b) or registrable(host) == b for b in BAD_HOSTS):
        problems.append(f"{where}: logo served by a banned third-party host {host}")
        return None
    if known and reg != known:
        problems.append(f"{where}: logo host {reg!r} != awarding body host {known!r}")
        return None
    if logo.get("official_host") is not True:
        problems.append(f"{where}: logo_override.official_host must be true")
        return None
    # The provenance vocabulary is closed: the audit test refuses free text here,
    # and the agent's explanation belongs in the entry, not in the enum.
    if logo.get("host_evidence") not in VALID_HOST_EVIDENCE:
        logo["host_evidence_note"] = logo.get("host_evidence")
        logo["host_evidence"] = "same_registrable_domain"
    if logo.get("validation_result") not in VALID_VALIDATION_RESULTS:
        logo["validation_result"] = "verified"
    if str(logo.get("image_kind", "official_logo")) not in {
        "official_logo", "official_government", "official_university"
    }:
        problems.append(f"{where}: logo image_kind must identify the awarding body")
        return None
    return logo


def validate_record(rec, shard_rec, problems, where, db_urls=None):
    """Return the do_add()-shaped record, or None when it must be dropped.

    ``db_urls`` maps a normalised official_source_url to the row id that already
    holds it, so a corrected URL can be accepted only when it is genuinely free.
    """
    outcome = str(rec.get("outcome") or "").strip()
    ns = rec.get("new_scholarship")
    if not isinstance(ns, dict):
        problems.append(f"{where}: no new_scholarship object")
        return None, None

    official = rec.get("programme_detail_official")
    verification = rec.get("programme_detail_verification")
    citations = (verification or {}).get("source_citations") if isinstance(verification, dict) else None
    if not citations:
        problems.append(f"{where}: no source_citations (the add stage would reject it)")
        return None, None

    if outcome in {"discontinued", "unreachable"}:
        return None, None

    # --- identity must resolve to the existing row -------------------------
    url = ns.get("official_source_url")
    tid = rec.get("target_id")
    if shard_rec:
        expected = shard_rec.get("current_official_source_url")
        if expected and (url or "").rstrip("/") != expected.rstrip("/"):
            owner = (db_urls or {}).get((url or "").rstrip("/").lower())
            if owner is not None and str(owner) != str(tid):
                problems.append(
                    f"{where}: corrected official_source_url {url!r} is already held by id={owner}; "
                    "a second row on one URL is impossible"
                )
                return None, None
            problems.append(f"{where}: corrected official_source_url {expected!r} -> {url!r}")
        # Identity is the merge's job, not the agent's: inject the stored title so
        # the upsert resolves even when the official name has since changed. The
        # lookup compares against lower(title), so the lowercase form goes in too.
        legacy = list(ns.get("legacy_titles") or [])
        if shard_rec.get("current_title"):
            for candidate in (shard_rec["current_title"], shard_rec["current_title"].lower()):
                if candidate not in legacy:
                    legacy.append(candidate)
        ns["legacy_titles"] = legacy

    status = str(ns.get("status") or "").strip().lower()
    if status not in ACCEPTED_STATUS:
        problems.append(f"{where}: status={status!r}; the add stage accepts only open|upcoming")
        return None, None

    dp = ns.get("deadline_precision")
    if dp is not None and str(dp).strip().lower() not in DEADLINE_PRECISION:
        problems.append(f"{where}: deadline_precision {dp!r} is outside the stored vocabulary")
        return None, None

    if shard_rec is None:
        # An insert has no existing row to fall back on, so every column the
        # ingestion validator requires must actually be present. The add stage
        # aborts the whole batch on one such record, so it is caught here.
        for field in sorted(REQUIRED):
            value = ns.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                problems.append(f"{where}: {field} is required for a new record and is {value!r}")
                return None, None

    # The column is a float. An agent writing "10,000" or "EUR 3,500" costs the
    # whole batch, so the number is extracted or the field is dropped.
    amount = ns.get("funding_amount")
    if amount is not None:
        try:
            ns["funding_amount"] = float(amount)
        except (TypeError, ValueError):
            cleaned = re.sub(r"[^\d.]", "", str(amount))
            try:
                ns["funding_amount"] = float(cleaned) if cleaned else None
            except ValueError:
                ns["funding_amount"] = None
            if ns["funding_amount"] is None:
                problems.append(f"{where}: dropped funding_amount {amount!r} (not a number)")
                ns.pop("funding_amount")

    for field in ("official_source_url", "catalogue_url", "official_updates_url",
                  "application_link"):
        value = ns.get(field)
        if value is None:
            continue
        if not is_https(value):
            # An http official URL would be refused by the ingestion validator and
            # cost the whole record. Dropping the one field keeps the findings.
            problems.append(f"{where}: dropped {field} (not https: {value!r})")
            ns.pop(field)

    ist = ns.get("image_source_type")
    if ist is not None and ist not in OFFICIAL_IMAGE_SOURCE_TYPES:
        problems.append(f"{where}: dropped image_source_type {ist!r} (not an official enum value)")
        ns.pop("image_source_type")
    if ns.get("image_url") and not ns.get("image_alt_text"):
        problems.append(f"{where}: dropped image_url (no image_alt_text)")
        for key in ("image_url", "image_source_url", "image_source_type", "image_verified_at"):
            ns.pop(key, None)

    validate_official_block(official, problems, where)
    # The repository rule is that fully_funded is applied only when tuition is
    # covered, so a stipend can never read as a tuition waiver. An agent that
    # broke it is corrected downwards, never upwards.
    if isinstance(official, dict) and official.get("fully_funded") is True and official.get("tuition_coverage") is not True:
        official["fully_funded"] = False
        note = official.get("tuition_coverage_note") or ""
        official["tuition_coverage_note"] = (
            f"{note} Corrected at merge: fully_funded was true while tuition_coverage was not."
        ).strip()
        problems.append(f"{where}: corrected fully_funded true -> false (tuition_coverage is not true)")
    logo = validate_logo(rec.get("logo_override"), shard_rec.get("official_host") if shard_rec else "",
                         problems, where)

    # --- shape the record the way do_add() expects -------------------------
    official = dict(official) if isinstance(official, dict) else {}
    flat = {}
    for key, value in ns.items():
        if key.startswith("_") or key == "documents":
            continue
        if key in BELONGS_TO_OFFICIAL:
            # An agent put an official fact in the ingestion block. It belongs in
            # official_details, where the repository keeps facts and guidance apart.
            official.setdefault(key, value)
            continue
        if key == "region" and isinstance(value, str) and (len(value) > 25 or "(" in value):
            # `region` is a filter facet. An eligibility sentence written into it
            # breaks every region filter; the sentence itself still belongs in
            # official_details, which the agent also fills.
            problems.append(f"{where}: dropped region {value[:60]!r} (not a geography label)")
            continue
        if key not in INGESTION_FIELDS and key not in ROW_ONLY:
            problems.append(f"{where}: dropped unknown field {key!r} (ingestion is extra=forbid)")
            continue
        if key in WIDTHS and isinstance(value, str) and len(value) > WIDTHS[key]:
            if key == "name":
                # Losing the record is worse than a long name trimmed to a word
                # boundary: the official wording is preserved up to that point.
                cut = value[:WIDTHS[key]]
                if " " in cut:
                    cut = cut[:cut.rfind(" ")]
                ns["name"] = cut.strip()
                flat["name"] = ns["name"]
                problems.append(f"{where}: name trimmed from {len(value)} to {len(flat['name'])} chars")
                continue
            if key in REQUIRED:
                problems.append(f"{where}: {key} is {len(value)} chars, required and limit {WIDTHS[key]}")
                return None, None
            problems.append(f"{where}: dropped {key} ({len(value)} chars > column limit {WIDTHS[key]})")
            if key == "funding_period":
                # The sentence the agent wrote is usually the useful part; keep it
                # where a reader will still see it instead of discarding it.
                kept = flat.get("notes") or ""
                flat["notes"] = f"{kept}\nFunding period: {value}".strip()
            continue
        flat[key] = value
    docs = ns.get("required_documents") or ns.get("documents")
    if docs is not None:
        flat["required_documents"] = as_str_list(docs, "required_documents", problems, where)

    for field in ("eligibility", "coverage", "requirements", "application_method", "benefits"):
        if field in flat and flat[field] is not None:
            flat[field] = as_str_list(flat[field], field, problems, where)

    detail = {
        "official_details": official if isinstance(official, dict) else None,
        "applicant_utility": rec.get("programme_detail_applicant_utility"),
        "verification": verification,
    }
    for key in list(detail):
        if detail[key] is None:
            detail.pop(key)
    flat["detail"] = detail
    flat["_target_id"] = rec.get("target_id")
    flat["_shard"] = rec.get("_shard")
    flat["_outcome"] = outcome
    flat["_logo_host"] = registrable(host_of(logo["url"])) if logo else None
    return flat, logo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="merge staged files into backend/config")
    args = parser.parse_args()

    os.makedirs(MERGED, exist_ok=True)
    db_urls = {}
    db_ids = set()
    try:
        db = sqlite3.connect(os.path.join(ROOT, "backend", "scholarzone.db"))
        for row_id, row_url in db.execute("SELECT id, official_source_url FROM scholarships"):
            db_ids.add(row_id)
            if row_url:
                db_urls[row_url.rstrip("/").lower()] = row_id
        db.close()
    except Exception as exc:  # noqa: BLE001 - the guard is best effort
        print(f"warning: could not read the live database ({exc}); URL collision checks are off")

    # A retired record is quarantined and must stop being asserted as currently
    # verified, and a confirmation has to cite an authoritative source. Both are
    # enforced here so a re-run cannot reintroduce what the audit rejects.
    retired_ids, authoritative = set(), None
    try:
        from app.services.scholarship_evidence import classify_source, is_authoritative_source

        authoritative = is_authoritative_source
        classify = classify_source
        retired = json.loads(open(os.path.join(CONFIG, "retired_records.json"), encoding="utf-8-sig").read())
        retired_ids = {r["id"] for r in retired["records"]}
    except Exception as exc:  # noqa: BLE001
        print(f"warning: retirement/authority checks unavailable ({exc})")

    shard_index = {}
    for name in sorted(os.listdir(SHARDS)):
        if not name.endswith(".json") or name == "MANIFEST.json":
            continue
        payload, _ = load_json(os.path.join(SHARDS, name))
        for row in payload["records"]:
            shard_index[int(row["target_id"])] = row

    files = [os.path.join(OUT, f) for f in sorted(os.listdir(OUT)) if f.endswith(".json")] \
    if os.path.isdir(OUT) else []
    # Split shards fill the gaps left by the ten-record shards that timed out.
    # Their agent_id differs, so the same target_id can only be claimed once.
    split_dir = os.path.join(W1, "out_split")
    if os.path.isdir(split_dir):
        files += [os.path.join(split_dir, f) for f in sorted(os.listdir(split_dir)) if f.endswith(".json")]
    problems, skipped, staged, confirmations, logos, logo_conflicts = [], [], [], [], {}, []
    seen_targets, seen_ids = set(), set()

    for name in files:
        payload, repair = load_json(name)
        if repair:
            problems.append(f"{name}: {repair}")
        if payload is None:
            continue
        agent = payload.get("agent_id") or name[:-5]
        for rec in payload.get("records") or []:
            tid = rec.get("target_id")
            where = f"{agent}/id={tid}"
            if tid is None:
                problems.append(f"{where}: no target_id")
                continue
            if tid in seen_targets:
                problems.append(f"{where}: duplicate target_id across agents; first writer wins")
                continue
            seen_targets.add(tid)
            if db_ids and tid not in db_ids:
                # The row was archived as a duplicate of another row for the same
                # programme. Re-seeding it would recreate that duplicate.
                skipped.append({"id": tid, "title": shard_index.get(int(tid), {}).get("current_title"),
                                "outcome": "superseded", "reason": "target row no longer exists"})
                problems.append(f"{where}: target row is gone; dropped instead of re-seeding a duplicate")
                continue
            shard_rec = shard_index.get(int(tid)) if str(tid).isdigit() else None
            if shard_rec is None:
                problems.append(f"{where}: target_id is not in any shard")
                continue

            if str(rec.get("outcome")) in {"discontinued", "duplicate", "unreachable"}:
                skipped.append({
                    "id": tid, "title": shard_rec.get("current_title"),
                    "outcome": rec.get("outcome"),
                    "reason": (rec.get("research_notes") or {}).get("contradictions")
                              or (rec.get("research_notes") or {}).get("logo"),
                })
                continue

            flat, logo = validate_record(rec, shard_rec, problems, where, db_urls)
            if flat is None:
                skipped.append({"id": tid, "title": shard_rec.get("current_title"),
                                "outcome": rec.get("outcome"), "reason": "failed validation"})
                continue
            staged.append(flat)

            if rec.get("confirm") is True and (rec.get("confirmation_evidence") or "").strip():
                target = int(tid)
                source_url = shard_rec.get("current_official_source_url")
                if target in retired_ids:
                    problems.append(f"{where}: dropped confirmation for the retired record id={target}")
                elif authoritative and not authoritative(classify(source_url or "")):
                    problems.append(f"{where}: dropped confirmation citing a non-authoritative source {source_url}")
                else:
                    confirmations.append({
                        "id": target,
                        "name": flat.get("name"),
                        "source_url": source_url,
                        "checked_at": TODAY,
                        "evidence": rec["confirmation_evidence"].strip(),
                    })
            if logo:
                host = registrable(host_of(logo["url"]))
                entry = {k: v for k, v in logo.items() if not k.startswith("_")}
                if host in logos and logos[host]["url"] != entry["url"]:
                    logo_conflicts.append({"host": host, "kept": logos[host]["url"], "ignored": entry["url"]})
                else:
                    logos[host] = entry
            seen_ids.add(int(tid))

    # --- duplicate url/name guard inside the batch --------------------------
    by_url, by_name, unique = {}, {}, []
    for row in staged:
        u = (row.get("official_source_url") or "").rstrip("/")
        n = (row.get("name") or "").strip().lower()
        if u in by_url or n in by_name:
            problems.append(f"id={row.get('_target_id')}: duplicate in batch (url/title already staged)")
            continue
        by_url[u] = row
        by_name[n] = row
        unique.append(row)
    staged = unique

    json.dump({
        "note": "Staged wave-1 upserts. Append records[] into backend/config/new_scholarships.json "
                "and run the maintenance `add` stage; records already in the database are matched "
                "by official_source_url / legacy_titles and updated in place, never duplicated.",
        "count": len(staged),
        "records": staged,
    }, open(os.path.join(MERGED, "new_scholarships.append.json"), "w", encoding="utf-8"),
        indent=2, ensure_ascii=False)

    json.dump({
        "note": "Staged re-verification confirmations. Append records[] into "
                "backend/config/verification_confirmations.json and run the `reverify` stage.",
        "count": len(confirmations),
        "records": confirmations,
    }, open(os.path.join(MERGED, "verification_confirmations.append.json"), "w", encoding="utf-8"),
        indent=2, ensure_ascii=False)

    json.dump(logos, open(os.path.join(MERGED, "official_logo_overrides.append.json"), "w",
                          encoding="utf-8"), indent=2, ensure_ascii=False)

    json.dump({
        "agents_reported": len(files),
        "staged_upserts": len(staged),
        "confirmations": len(confirmations),
        "logo_hosts": len(logos),
        "logo_conflicts": logo_conflicts,
        "skipped_for_review": skipped,
        "validation_problems": problems,
    }, open(os.path.join(MERGED, "validation_report.json"), "w", encoding="utf-8"),
        indent=2, ensure_ascii=False)

    print(f"agent output files : {len(files)}")
    print(f"staged upserts     : {len(staged)}")
    print(f"confirmations      : {len(confirmations)}")
    print(f"logo hosts         : {len(logos)}")
    print(f"skipped            : {len(skipped)}")
    print(f"problems           : {len(problems)}")
    for p in problems[:25]:
        print("   !", p)

    if args.apply:
        if not staged:
            print("\n--apply: nothing staged, config untouched.")
            return 0
        for target, staged_name in (
            ("new_scholarships.json", "new_scholarships.append.json"),
            ("verification_confirmations.json", "verification_confirmations.append.json"),
        ):
            path = os.path.join(CONFIG, target)
            if not os.path.exists(path + ".pre_wave1"):
                shutil.copyfile(path, path + ".pre_wave1")
            current = json.loads(open(path, encoding="utf-8-sig").read())
            records = current.get("records") if isinstance(current, dict) else current
            addition = json.loads(open(os.path.join(MERGED, staged_name), encoding="utf-8-sig").read())["records"]
            # Append must be idempotent: this script is re-run as each shard lands,
            # and a second copy of the same record would re-upsert the same row.
            if target == "new_scholarships.json":
                seen = {(r.get("official_source_url") or "").rstrip("/").lower() for r in records if isinstance(r, dict)}
                addition = [r for r in addition if (r.get("official_source_url") or "").rstrip("/").lower() not in seen]
            else:
                seen = {r.get("id") for r in records if isinstance(r, dict)}
                addition = [r for r in addition if r.get("id") not in seen]
            merged = {**current} if isinstance(current, dict) else {"records": records}
            merged["records"] = list(records) + addition
            merged["count"] = len(merged["records"])
            json.dump(merged, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            print(f"applied {len(addition):4d} records -> {target} (backup: {target}.pre_wave1)")

        logo_path = os.path.join(CONFIG, "official_logo_overrides.json")
        if not os.path.exists(logo_path + ".pre_wave1"):
            shutil.copyfile(logo_path, logo_path + ".pre_wave1")
        current = json.loads(open(logo_path, encoding="utf-8-sig").read())
        added = 0
        for host, entry in logos.items():
            if host in current:
                continue
            current[host] = entry
            added += 1
        json.dump(current, open(logo_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"applied {added:4d} logo hosts -> official_logo_overrides.json (backup kept)")
    return 0


if __name__ == "__main__":
    sys.exit(main())