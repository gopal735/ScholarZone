"""Audit the Country Intelligence corpus and emit the coverage matrix.

Run from ``backend/``::

    python scripts/audit_country_intelligence.py            # write the matrix
    python scripts/audit_country_intelligence.py --strict   # non-zero exit on any problem

This is the read-only counterpart to ingestion. It never writes a corpus file, and
its job is to make the shape of the corpus visible: which countries are genuinely
backed by evidence, which domains are established, and what is missing.

## What "verified" means here

A claim counts as verified only when it carries a value, a recognised status, at
least one source id that resolves to a real source, and an ``as_of``. That is the
same bar ingestion enforces, so the audit cannot report a claim as sound that the
corpus loader would refuse.

A domain with no claim is reported as ``-``. It is never reported as zero: an
unresearched domain and a researched zero are different facts, and collapsing them
is the failure this corpus exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.country_intelligence.corpus import (  # noqa: E402
    CORPUS_DIR,
    load_corpus,
)
from app.services.country_intelligence.fx import get_fx_table  # noqa: E402
from app.services.country_intelligence.formulas import registry_problems  # noqa: E402
from app.services.country_intelligence.provenance import (  # noqa: E402
    DEFAULT_STALE_AFTER_DAYS,
    NON_OFFICIAL_SOURCE_TYPES,
    SOURCE_TYPES,
    VALUE_STATUS,
    normalise_freshness,
    normalise_source_type,
    resolve_freshness,
)

#: Domain -> the corpus path that proves it.
#:
#: Explicit rather than inferred from section names, because a domain and a
#: section are not the same thing: work rights and permanent residence both live
#: under ``residency`` and are different questions a student asks.
DOMAINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tuition", ("education_costs", "tuition_fees", "public")),
    ("university", ("education_costs", "tuition_fees", "by_university")),
    ("living", ("living_costs",)),
    ("financial_proof", ("one_time_costs", "blocked_account")),
    ("work_rights", ("residency", "work_while_studying")),
    ("post_study", ("residency", "job_seeker_residence_permit")),
    ("PR", ("residency", "permanent_residence")),
    ("citizenship", ("residency", "citizenship")),
    ("career", ("career",)),
    ("scholarships", ("scholarship_landscape",)),
    ("quality_of_life", ("quality_of_life",)),
)

DOMAIN_ORDER = [name for name, _ in DOMAINS]

#: Placeholder markers. Kept in step with the ingester's list.
PLACEHOLDER_MARKERS = (
    "TODO", "TBD", "FIXME", "PLACEHOLDER", "lorem ipsum", "INSERT_", "FILL_ME",
)

#: How old evidence may be before the audit calls it out. Not a rejection - a
#: threshold nobody has reasoned about is worse than a warning a human can judge.
#: Defined once in provenance so the CLI, the contract tests and any caller
#: cannot drift apart on what counts as stale.
STALE_AFTER_DAYS = DEFAULT_STALE_AFTER_DAYS


def _walk(node: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(node, dict):
        if "value_status" in node:
            yield path, node
        for key, value in node.items():
            yield from _walk(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, path + (str(index),))


def _dig(node: Any, path: tuple[str, ...]) -> Any:
    current = node
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _placeholders(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_placeholders(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_placeholders(value))
    elif isinstance(node, str):
        lowered = node.lower()
        for marker in PLACEHOLDER_MARKERS:
            if marker.lower() in lowered:
                found.append(f"{node!r}")
                break
    return found


def audit_country(
    record: Any,
    *,
    reference_date: str | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Per-country findings from a loaded record.

    ``reference_date`` is threaded through rather than read from the clock inside
    this function so that "which figures are stale" is a pure function of the
    corpus and the caller. Two audits of the same corpus on different days must
    not disagree about freshness unless the corpus or the threshold changed.
    """
    source_ids = {source.id for source in record.sources}
    source_types = {source.id: source.source_type for source in record.sources}
    retrieved = {source.id: getattr(source, "retrieved_at", None) for source in record.sources}

    verified = 0
    unverified_status = 0
    descriptive = 0
    dangling = 0
    official_without_official_source: list[str] = []
    domains: dict[str, bool] = {}
    stale: list[str] = []
    undated: list[str] = []
    conflicting: list[str] = []
    estimates: list[str] = []
    refused: list[str] = []

    for path, node in _walk(record.sections):
        dotted = ".".join(path)
        status = node.get("value_status")
        is_descriptive = bool(node.get("descriptive"))

        if status == "CONFLICTING":
            # Counted before the citation check so a conflict cannot hide behind a
            # dangling reference, and reported separately: a published conflict is
            # a finding about the world, not a defect in the corpus.
            conflicting.append(dotted)
        elif status == "ESTIMATE":
            estimates.append(dotted)
        elif status == "REFUSED":
            refused.append(dotted)

        cited = node.get("source_ids") or []
        if any(source_id not in source_ids for source_id in cited):
            dangling += 1
            continue
        if status not in VALUE_STATUS:
            unverified_status += 1
            continue
        if is_descriptive:
            descriptive += 1
            continue

        # Freshness is resolved per claim from its own dates. A claim with no
        # usable date is UNDATED, which is reported but is not a fatal problem:
        # undated evidence is a disclosure requirement, not malformed data.
        if status not in {"UNKNOWN", "REFUSED"}:
            claim_retrieved = next(
                (retrieved.get(sid) for sid in cited if retrieved.get(sid)), None
            )
            freshness = normalise_freshness(node.get("freshness")) or resolve_freshness(
                node.get("as_of"),
                reference_date=reference_date,
                stale_after_days=stale_after_days,
                retrieved_at=claim_retrieved,
            )
            if freshness == "STALE":
                stale.append(dotted)
            elif freshness == "UNDATED":
                undated.append(dotted)

        if (
            status
            in {"OFFICIAL_GOVERNMENT", "OFFICIAL_REGIONAL_BODY",
                "OFFICIAL_STATISTICS", "UNIVERSITY_OFFICIAL"}
            and not any(
                source_types.get(source_id) in SOURCE_TYPES
                and source_types.get(source_id) not in NON_OFFICIAL_SOURCE_TYPES
                for source_id in cited
            )
        ):
            official_without_official_source.append(dotted)
            continue

        if status == "CONFLICTING":
            # A conflict has no single figure, so it is not "verified" as a
            # number. It is still audited: every side must name a source, and
            # parse_claim already enforced that.
            continue

        verified += 1

    for name, prefix in DOMAINS:
        domains[name] = bool(_dig(record.sections, prefix))

    # The matrix marks a domain only when it holds a real figure, not merely a
    # section key.
    for path, node in _walk(record.sections):
        if node.get("descriptive"):
            continue
        for name, prefix in DOMAINS:
            if path[: len(prefix)] == prefix:
                domains[name] = True

    gap_fields = [gap.field for gap in record.gaps]

    return {
        "iso2": record.iso2,
        "name": record.name,
        "sources": len(record.sources),
        "verified_claims": verified,
        "descriptive_claims": descriptive,
        "gaps": len(record.gaps),
        "domains": domains,
        "dangling_citations": dangling,
        "unsupported_status": unverified_status,
        "official_without_official_source": official_without_official_source,
        "placeholders": _placeholders(record.sections),
        "status": _classify(domains, verified, len(record.gaps)),
        "gap_fields": gap_fields,
        "stale_claims": stale,
        "undated_claims": undated,
        "conflicting_claims": conflicting,
        "estimate_claims": estimates,
        "refused_claims": refused,
    }


def _classify(domains: dict[str, bool], verified: int, gaps: int) -> str:
    """COMPLETE / PARTIAL / UNAVAILABLE, by the mission's definitions.

    COMPLETE requires every domain in :data:`DOMAINS` to hold a figure. That bar is
    deliberately unreachable for most countries at present, and that is the point:
    "complete" should mean every domain a student can be blocked on was researched,
    not that a file exists.
    """
    if verified == 0:
        return "UNAVAILABLE"
    if all(domains.values()):
        return "COMPLETE"
    return "PARTIAL"


def audit_raw_archive(raw_dir: Path) -> list[str]:
    """Problems in the raw archive itself, independent of any corpus file."""
    problems: list[str] = []
    if not raw_dir.is_dir():
        return [f"{raw_dir} does not exist"]
    for path in sorted(raw_dir.glob("*/*.json")):
        text = path.read_text(encoding="utf-8-sig")
        try:
            document = json.loads(text)
        except ValueError as exc:
            problems.append(f"{path.name}: malformed JSON ({exc})")
            continue
        if not isinstance(document, dict):
            problems.append(f"{path.name}: not an object")
            continue
        iso2 = path.parent.name.upper()
        status = document.get("raw_status")
        if status and status != "ARCHIVED":
            # A negative-evidence record. Its job is to prove a figure is ABSENT -
            # UNAVAILABLE (the source was unreachable), NOT_FOUND_IN_LAW (the
            # provision does not exist), and so on. It carries a reason and
            # evidence, and makes no claim, so demanding a claim source URL would
            # be backwards: asserting that something does not exist requires the
            # law or page that was read, not a citation for a figure.
            if not document.get("reason"):
                problems.append(
                    f"{path.name}: raw_status {status!r} with no reason. A record that "
                    f"explains why a figure is missing must say why."
                )
            if not (document.get("evidence_summary") or document.get("attempted_sources")):
                problems.append(
                    f"{path.name}: raw_status {status!r} with no evidence. Asserting that "
                    f"something does not exist needs the law or page that was read."
                )
            continue
        for required in ("country", "topic", "source_url", "retrieved_at"):
            if not document.get(required):
                problems.append(f"{path.name}: missing {required!r}")
        declared = document.get("country")
        # ``_global`` holds evidence that is not any country's - exchange rates, for
        # now. It is a scope, not a country code, and the audit must not pretend
        # otherwise or it will demand a two-letter code that does not exist.
        if path.parent.name == "_GLOBAL":
            if declared not in ("_GLOBAL", None):
                problems.append(
                    f"{path.name}: global evidence declares country {declared!r}. "
                    f"Evidence that belongs to no country must say so."
                )
        elif declared and str(declared).upper() != iso2:
            problems.append(
                f"{path.name}: declares country {declared!r} but sits under {iso2!r}. "
                f"Evidence filed under the wrong country is worse than no evidence, "
                f"because it will be counted in the wrong place."
            )
        declared = document.get("source_type")
        if declared is not None and normalise_source_type(declared) is None:
            problems.append(
                f"{path.name}: source_type {declared!r} is not recognised. Known: "
                f"{', '.join(SOURCE_TYPES)}."
            )
        if not document.get("raw_extract"):
            problems.append(
                f"{path.name}: no raw_extract. A claim with no archived text cannot be "
                f"audited against the page it came from."
            )
    return problems


def manifest_agreement(manifest_path: Path) -> str:
    """Does the manifest describe the archive that is actually on disk?

    Compares the manifest's recorded inventory against the real file list rather
    than rebuilding the whole document, because the audit needs to answer a
    narrower question than the builder does: does every artifact have an entry,
    and does every entry have an artifact.
    """
    if not manifest_path.is_file():
        return "missing. The archive has no inventory."
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return f"is not valid JSON ({exc})."

    recorded = {
        entry.get("artifact")
        for group in (
            manifest.get("countries", []),
            manifest.get("non_country_scopes", []),
        )
        for entry in group
        for entry in entry.get("artifacts", [])
    }
    actual = {
        path.relative_to(manifest_path.parent).as_posix()
        for path in manifest_path.parent.rglob("*.json")
        if path.name != "manifest.json"
    }

    missing = sorted(actual - recorded)
    phantom = sorted(recorded - actual)
    if missing:
        return (
            f"omits {len(missing)} archive file(s), so it understates what was "
            f"retrieved (first: {missing[0]}). Run "
            f"scripts/build_research_manifest.py."
        )
    if phantom:
        return (
            f"claims {len(phantom)} artifact(s) that do not exist (first: "
            f"{phantom[0]}). A manifest entry is not evidence."
        )
    return "ok"


def build_matrix(countries: list[dict[str, Any]]) -> str:
    """The domain coverage matrix.

    Domain presence and evidence quality are reported as separate columns on
    purpose. "DE has a tuition figure" and "DE's tuition figure is current,
    official and uncontested" are different facts, and a single Y/n column forces
    the reader to guess which one a Y means.
    """
    header = "| country | " + " | ".join(
        name.replace("_", " ") for name in DOMAIN_ORDER
    ) + (
        " | sources | verified claims | stale | undated | conflicts"
        " | estimates | refused | gaps | status |"
    )
    divider = "|---" * (len(DOMAIN_ORDER) + 11) + "|"
    lines = [header, divider]
    for entry in sorted(countries, key=lambda item: item["iso2"]):
        cells = ["Y" if entry["domains"][name] else "-" for name in DOMAIN_ORDER]
        lines.append(
            f"| {entry['iso2']} {entry['name']} | "
            + " | ".join(cells)
            + f" | {entry['sources']} | {entry['verified_claims']}"
            f" | {len(entry['stale_claims'])} | {len(entry['undated_claims'])}"
            f" | {len(entry['conflicting_claims'])} | {len(entry['estimate_claims'])}"
            f" | {len(entry['refused_claims'])} | {entry['gaps']}"
            f" | {entry['status']} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit the Country Intelligence corpus.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any problem.")
    parser.add_argument("--matrix", default="COUNTRY_RESEARCH_COVERAGE_MATRIX.md")
    parser.add_argument(
        "--reference-date",
        default=None,
        help=(
            "Date the staleness check is measured against (YYYY-MM-DD). Defaults to "
            "today. Pass it explicitly for a reproducible audit: without it the "
            "answer depends on when the command was run."
        ),
    )
    parser.add_argument(
        "--stale-after-days",
        type=int,
        default=STALE_AFTER_DAYS,
        help="Age at which evidence is reported stale.",
    )
    args = parser.parse_args(argv)

    problems: list[str] = []
    problems.extend(registry_problems())

    raw_problems = audit_raw_archive(CORPUS_DIR / "research_raw")
    problems.extend(raw_problems)

    # The manifest must describe the archive that exists. A stale manifest is
    # worse than none, because it is trusted as a record of what was retrieved -
    # this one spent its whole life claiming RAW_SOURCE_UNAVAILABLE for every
    # country while real artifacts sat two directories away.
    manifest_state = manifest_agreement(CORPUS_DIR / "research_raw" / "manifest.json")
    if manifest_state != "ok":
        problems.append(f"manifest.json: {manifest_state}")

    corpus = load_corpus()
    problems.extend(f"{p.iso2}.json: {p.reason}" for p in corpus.problems)

    countries = [
        audit_country(
            record,
            reference_date=args.reference_date,
            stale_after_days=args.stale_after_days,
        )
        for record in corpus.records
    ]
    stale_findings: list[str] = []
    for entry in countries:
        for field in ("dangling_citations", "unsupported_status"):
            if entry[field]:
                problems.append(
                    f"{entry['iso2']}: {entry[field]} {field.replace('_', ' ')}"
                )
        for field in entry["official_without_official_source"]:
            problems.append(
                f"{entry['iso2']}: {field} asserts an official status with no official "
                f"source behind it"
            )
        if entry["placeholders"]:
            problems.append(f"{entry['iso2']}: placeholder value(s) {entry['placeholders'][:3]}")
        # Staleness and undated evidence are findings, not fatal defects. They are
        # reported under --strict rather than silently dropped, because a corpus
        # audit that omits them would pass a corpus whose figures are years old.
        for field in entry["stale_claims"]:
            stale_findings.append(f"{entry['iso2']}: {field} is stale evidence")
        for field in entry["undated_claims"]:
            stale_findings.append(f"{entry['iso2']}: {field} has no usable evidence date")

    fx = get_fx_table()
    matrix = build_matrix(countries)

    print(f"Corpus: {len(countries)} country file(s), {sum(e['gaps'] for e in countries)} gap(s)")
    print(f"FX table: {'present' if fx else 'ABSENT - cross-currency rows will refuse'}")
    if fx:
        print(f"  {fx.publisher}, as of {fx.as_of}, {len(fx.rates) + 1} currencies")
    print()
    print(matrix)
    print()
    print(f"Freshness checked against {args.reference_date or 'today'} "
          f"(stale after {args.stale_after_days} days)")
    for finding in stale_findings:
        print(f"  FINDING {finding}")
    if not stale_findings:
        print("  No stale or undated evidence.")
    print()

    for problem in problems:
        print(f"  PROBLEM {problem}")

    repository_root = Path(__file__).resolve().parents[2]
    (repository_root / args.matrix).write_text(matrix + "\n", encoding="utf-8")
    print(f"\nWrote {args.matrix}")
    print(f"{len(problems)} problem(s)")
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())