"""Rebuild ``research_raw/manifest.json`` from the archive that actually exists.

Run from ``backend/``::

    python scripts/build_research_manifest.py
    python scripts/build_research_manifest.py --check

Why this exists
---------------

The manifest was first written against a research run that produced nothing
retrievable, and it recorded ``RAW_SOURCE_UNAVAILABLE`` for every country. Later
passes archived real artifacts per country and topic. The manifest was never
updated, so it went on asserting that no source documents existed for any country
that in fact had dozens of them on disk two directories away.

That is the specific hazard a manifest creates. It is trusted as a record of what
was retrieved, so a stale entry is worse than no entry: it says "do not trust this
country" while the evidence sits next to it, and a reader has no way to tell which
of the two is out of date.

So the manifest is **derived**, not authored. This script reads the archive and
writes what it finds. Two rules keep it honest:

- Nothing is deleted. Historical research task ids, notes and the original
  unavailable/retired classification are carried through. Evidence that became
  unusable is recorded as such, not erased, because "we tried this and it was not
  retrievable" is itself a finding worth keeping.
- Nothing is invented. An entry exists because a file exists, and every field
  comes from that file.

Output is deterministic: entries are sorted, and no timestamp or UUID is
generated. Re-running it on an unchanged archive must produce identical bytes, or
``--check`` fails and the file is not trustworthy.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.country_intelligence.corpus import CORPUS_DIR  # noqa: E402

RAW_DIR = CORPUS_DIR / "research_raw"
MANIFEST = RAW_DIR / "manifest.json"

#: How an artifact may present itself. Anything else is not silently accepted.
RAW_STATUSES: dict[str, str] = {
    "ARCHIVED": "The document is stored under research_raw/ and may be ingested.",
    "UNAVAILABLE": (
        "Research reached this topic but the source could not be retrieved. No "
        "figure may be ingested; the attempt and its blocking reason are kept."
    ),
    "NOT_FOUND_IN_LAW": (
        "The provision sought does not exist in the primary source that was read. "
        "This is a positive finding, not a retrieval failure, and it must never be "
        "ingested as a figure."
    ),
}

#: Fields an archived, ingestible artifact must carry. Missing any of these is
#: what the raw-evidence audit flags; the manifest records the same verdict so the
#: archive's state is visible without reading every file.
REQUIRED_FOR_ARCHIVED = (
    "source_id",
    "source_url",
    "source_type",
    "publisher",
    "retrieved_at",
)


def _load(path: Path) -> dict[str, Any] | None:
    """Load one artifact, rejecting duplicate JSON keys.

    Duplicate keys are rejected rather than tolerated because ``json.loads`` keeps
    the last value silently. An artifact whose ``claims`` key appeared twice could
    therefore ingest differently from how it reads, which is the same class of
    problem as an unauditable conflict.
    """
    text = path.read_text(encoding="utf-8-sig")

    def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError(f"duplicate key {key!r}")
            seen[key] = value
        return seen

    try:
        return json.loads(text, object_pairs_hook=_no_duplicates)
    except ValueError:
        return None


def _artifact_entry(path: Path, document: dict[str, Any] | None) -> dict[str, Any]:
    """One inventory record for one file on disk."""
    relative = path.relative_to(RAW_DIR).as_posix()
    country = path.parent.name
    global_scope = country == "_global"

    if document is None:
        return {
            "artifact": relative,
            "country": None if global_scope else country,
            "parse_status": "UNPARSEABLE",
            "raw_status": None,
            "ingestion_eligible": False,
            "missing_fields": ["<file did not parse>"],
        }

    raw_status = document.get("raw_status") or "ARCHIVED"
    claims = document.get("claims") or []
    missing = [
        field
        for field in REQUIRED_FOR_ARCHIVED
        if raw_status == "ARCHIVED" and not document.get(field)
    ]
    # An archived artifact making claims must carry the verbatim text they came
    # from. Without it the claim cannot be checked against the page it names.
    if raw_status == "ARCHIVED" and claims and not document.get("raw_extract"):
        missing.append("raw_extract")

    return {
        "artifact": relative,
        "country": None if global_scope else country,
        "topic": document.get("topic"),
        "source_id": document.get("source_id"),
        "source_url": document.get("source_url"),
        "source_type": document.get("source_type"),
        "publisher": document.get("publisher"),
        "retrieved_at": document.get("retrieved_at"),
        "as_of": document.get("as_of"),
        "raw_status": raw_status,
        "parse_status": "PARSED",
        "raw_extract_present": bool(document.get("raw_extract")),
        "claim_count": len(claims),
        "study_levels": sorted(
            {str(claim.get("study_level")) for claim in claims if claim.get("study_level")}
        ),
        "missing_fields": missing,
        "ingestion_eligible": raw_status == "ARCHIVED" and not missing and bool(claims),
        "reason": document.get("reason"),
    }


def build_manifest() -> dict[str, Any]:
    """The manifest the current archive justifies."""
    previous = _load(MANIFEST) or {}
    previous_countries = {
        entry["iso2"]: entry
        for entry in previous.get("countries", [])
        if isinstance(entry, dict) and entry.get("iso2")
    }

    artifacts: list[dict[str, Any]] = []
    for path in sorted(RAW_DIR.rglob("*.json")):
        if path.name == "manifest.json":
            continue
        artifacts.append(_artifact_entry(path, _load(path)))

    by_country: dict[str, list[dict[str, Any]]] = {}
    for entry in artifacts:
        by_country.setdefault(entry.get("country") or "_global", []).append(entry)

    countries: list[dict[str, Any]] = []
    for country in sorted(by_country):
        entries = by_country[country]
        historical = previous_countries.get(country, {})
        eligible = [item for item in entries if item["ingestion_eligible"]]
        blocked = [item for item in entries if item["parse_status"] == "UNPARSEABLE"]
        negative = [
            item
            for item in entries
            if item.get("raw_status") and item["raw_status"] != "ARCHIVED"
        ]

        record: dict[str, Any] = {
            "iso2": country if country != "_global" else None,
            # History is carried, never cleared. The task ids and the original
            # notes are the record of what was attempted and why, which outlives
            # any single research pass.
            "research_task_ids": historical.get("research_task_ids", []),
            "artifact_count": len(entries),
            "ingestion_eligible_count": len(eligible),
            "negative_evidence_count": len(negative),
            "unparseable_count": len(blocked),
            "raw_source": (
                "ARCHIVED"
                if eligible
                else (blocked and "UNPARSEABLE" or "RAW_SOURCE_UNAVAILABLE")
            ),
            "raw_status": "ARCHIVED" if eligible else "RAW_SOURCE_UNAVAILABLE",
            "truncated": bool(historical.get("truncated", False)),
            "transformation_status": (
                "CANONICAL_PRESENT"
                if (
                    not blocked
                    and (CORPUS_DIR / f"{country}.json").is_file()
                )
                else "CANONICAL_ABSENT"
            ),
            "validation_status": "VALIDATED" if not blocked else "UNVALIDATED",
            "canonical_file": (
                f"{country}.json" if country != "_global" and (CORPUS_DIR / f"{country}.json").is_file() else None
            ),
            "notes": historical.get("notes", []),
            "artifacts": entries,
        }

        # A note that says "no source document is in the repository" stops being
        # true the moment one is archived, and a manifest that keeps asserting it
        # is worse than one that never claimed it. The old note is kept as history
        # and superseded explicitly, so a reader can see what changed and when the
        # claim lapsed rather than inheriting a false statement.
        #
        # The marker is sticky: once a scope has been reconciled away from
        # RAW_SOURCE_UNAVAILABLE, later runs carry it forward instead of
        # re-deriving it. Without that the manifest would change on every run and
        # --check would never settle.
        already_superseded = bool(historical.get("superseded_raw_status"))
        if eligible and (
            historical.get("raw_status") == "RAW_SOURCE_UNAVAILABLE"
            or already_superseded
        ):
            if not already_superseded:
                record["notes"] = [
                    *record["notes"],
                    (
                        f"SUPERSEDED: the earlier RAW_SOURCE_UNAVAILABLE classification "
                        f"no longer applies. {len(eligible)} of {len(entries)} artifact(s) "
                        f"for this scope are now archived and ingestion-eligible. The "
                        f"original note is retained above as a record of what the earlier "
                        f"research pass had to work with."
                    ),
                ]
            record["superseded_raw_status"] = "RAW_SOURCE_UNAVAILABLE"

        countries.append(record)

    # The FX reference table is evidence like any other but it is not a country,
    # so it is kept out of ``countries``. Putting a null ISO2 in that list would
    # mean every consumer of the manifest has to filter a sentinel out, and a
    # "which countries did we research?" query would answer with a scope that has
    # no flag, no migration and no student.
    global_records = [
        item for item in countries if item["iso2"] is None
    ]
    countries = [item for item in countries if item["iso2"] is not None]

    return {
        "manifest_version": 2,
        "corpus_contract_version": previous.get("corpus_contract_version"),
        "note": (
            "Derived from the archive by scripts/build_research_manifest.py, not "
            "authored by hand. Every entry corresponds to a file under "
            "research_raw/; historical research task ids and notes are carried "
            "forward rather than deleted. Re-run the script after changing the "
            "archive and use --check to prove it agrees with the filesystem."
        ),
        "raw_source_statuses": RAW_STATUSES,
        "artifact_statuses": RAW_STATUSES,
        "archive_file_count": len(artifacts),
        "countries": countries,
        "non_country_scopes": global_records,
        "pending_claims": previous.get("pending_claims", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift without writing; non-zero exit if the manifest is stale.",
    )
    args = parser.parse_args(argv)

    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    if args.check:
        current = MANIFEST.read_text(encoding="utf-8") if MANIFEST.is_file() else ""
        if current != payload:
            print("  PROBLEM manifest.json does not match the archive on disk.")
            print("  Run python scripts/build_research_manifest.py to reconcile it.")
            return 1
        print(f"manifest agrees with the archive ({manifest['archive_file_count']} artifact(s))")
        return 0

    MANIFEST.write_text(payload, encoding="utf-8", newline="\n")
    countries = manifest["countries"]
    eligible = sum(item["ingestion_eligible_count"] for item in countries)
    negative = sum(item["negative_evidence_count"] for item in countries)
    print(f"Wrote {MANIFEST.name}: {manifest['archive_file_count']} artifact(s) across "
          f"{len(countries)} scope(s); {eligible} ingestion-eligible, {negative} negative-evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())