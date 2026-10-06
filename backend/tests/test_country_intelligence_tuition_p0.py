"""P0 tuition-contract tests: the carry-forward zero guard and the Bachelor path shape.

Both P0 defects were invisible to the existing suite and to ``--check`` and to the
strict audit, which all passed on the broken corpus. These tests exist so that the
next regression of either defect fails here rather than in a student's total
investment.

The defects:

* **P0-A** - a zero cost claim survived when its evidence did not support it. The
  rule lived only in the fresh-build claim loop, where it could not run: it wrote to
  a ``node`` name the very next statement rebound, and the fresh path hardcodes
  ``archived: True`` so its condition was never true. The carry-forward path had no
  zero rule at all. Germany therefore published EUR 0/year for public Bachelor,
  Master and PhD tuition on the authority of a visa page, and ``derive_tuition``
  returned 0.0.

* **P0-B** - ``...tuition_fees.public.bachelor.bachelor`` persisted in 13 countries.
  The topic map, the level append and ``_put`` were all correct; ``_merge_existing``
  re-created the path by recursing on dict-key position instead of canonical path,
  carrying the old claim forward and discarding the correctly written fresh one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.country_intelligence.derive import (  # noqa: E402
    _find_tuition_claim,
    derive_tuition,
)
from scripts import ingest_country_intelligence as ingest  # noqa: E402

CANON = ("education_costs", "tuition_fees", "public", "bachelor")
COST = ("tuition_fees", "mandatory_fees", "blocked_account", "costs", "fee", "salary")


def _is_cost(path: str) -> bool:
    return "related_figures" not in path.split(".") and any(m in path for m in COST)


def _write_raw(root: Path, iso2: str, artifacts: list[dict]) -> Path:
    raw = root / "research_raw" / iso2
    raw.mkdir(parents=True, exist_ok=True)
    for index, artifact in enumerate(artifacts, start=1):
        (raw / f"{index:03d}_{artifact['topic']}.json").write_text(
            json.dumps(artifact), encoding="utf-8"
        )
    return raw


def _artifact(
    topic: str,
    *,
    value: float,
    unit: str = "EUR per year",
    source_id: str = "xx-s1",
    claim_id: str = "xx-c1",
    study_level: str | None = "bachelor",
    extract: str = "verbatim source text",
) -> dict:
    claim = {
        "claim_id": claim_id,
        "statement": f"The source states {value}.",
        "value": value,
        "unit": unit,
        "as_of": "2026",
    }
    if study_level:
        claim["study_level"] = study_level
    return {
        "country": "XX",
        "topic": topic,
        "source_id": source_id,
        "source_url": f"https://example.org/{source_id}",
        "source_type": "OFFICIAL_GOVERNMENT",
        "publisher": "Example Ministry",
        "retrieved_at": "2026-10-05",
        "as_of": "2026",
        "raw_extract": extract,
        "claims": [claim],
    }


def _build(tmp_path: Path, artifacts: list[dict], iso2: str = "XX") -> tuple[Path, dict]:
    corpus = tmp_path / "corpus"
    raw = _write_raw(corpus, iso2, artifacts)
    report = ingest.ingest_country_from_raw(iso2, corpus_dir=corpus, raw_dir=raw)
    document = {}
    path = corpus / f"{iso2}.json"
    if path.exists():
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    return path, {"report": report, "document": document}


def _dig(node, path):
    current = node
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _claim_paths(node, prefix="", out=None):
    out = [] if out is None else out
    if not isinstance(node, dict):
        return out
    if "value_status" in node:
        out.append((prefix, node))
        return out
    for key, value in node.items():
        _claim_paths(value, f"{prefix}.{key}" if prefix else key, out)
    return out


# ======================================================================================
# P0-A - the zero rule
# ======================================================================================


class TestZeroRule:
    def test_the_rule_is_one_function_called_from_both_paths(self):
        """Business logic must not be duplicated between fresh and carry-forward.

        Two copies of the rule is how the two paths drifted apart in the first
        place: the fresh copy could not run and the carry-forward copy did not
        exist. There is exactly one implementation, and both entry points call it.
        """
        source = (BACKEND / "scripts" / "ingest_country_intelligence.py").read_text(
            encoding="utf-8"
        )
        assert source.count("def zero_cost_refusal(") == 1
        assert source.count("def _demote_unpublishable_zero(") == 1
        # Exactly two call sites: the fresh claim boundary and the carried-claim
        # boundary. A third would mean the rule is being re-implemented somewhere.
        assert source.count("_demote_unpublishable_zero(") == 3  # 1 def + 2 calls

    def test_fresh_unsupported_zero_becomes_unknown(self, tmp_path: Path):
        """A zero with no stated period is not a defined quantity."""
        _, ctx = _build(
            tmp_path,
            [_artifact("bachelor_tuition", value=0, unit="EUR")],
        )
        node = _dig(ctx["document"].get("sections", {}), list(CANON))
        assert node is not None
        assert node["value"] is None
        assert node["value_status"] == "UNKNOWN"

    def test_fresh_zero_with_no_currency_becomes_unknown(self, tmp_path: Path):
        _, ctx = _build(
            tmp_path,
            [_artifact("bachelor_tuition", value=0, unit="no tuition fees payable")],
        )
        sections = ctx["document"].get("sections", {})
        published = [n for _, n in _claim_paths(sections) if n.get("value") == 0]
        cost_published = [n for p, n in _claim_paths(sections) if n.get("value") == 0 and _is_cost(p)]
        assert not cost_published, "a currencyless zero must never sit in a cost slot"
        # It is preserved as evidence, just not as a cost.
        assert published or any(
            "related_figures" in p for p, _ in _claim_paths(sections)
        )

    def test_archived_and_explicitly_sourced_zero_is_published(self, tmp_path: Path):
        """The positive case: a real, audited zero must survive the rule.

        A guard that refuses every zero is not a stricter guard, it is a broken one.
        TU Berlin's published "there are no tuition fees to pay" is exactly this
        shape, and refusing it would be as wrong as publishing the German visa-page
        zero.
        """
        _, ctx = _build(
            tmp_path,
            [_artifact("bachelor_tuition", value=0, unit="EUR per year")],
        )
        node = _dig(ctx["document"].get("sections", {}), list(CANON))
        assert node["value"] == 0
        assert node["value_status"] == "OFFICIAL_GOVERNMENT"
        assert derive_tuition(ctx["document"]["sections"], "bachelor", 0.0).value == 0.0

    def test_carried_forward_unsupported_zero_becomes_unknown(self, tmp_path: Path):
        """**The P0-A carry-forward bypass.**

        The claim is not re-derived by this build at all, so the fresh-path rule
        never sees it. It is exactly the path Germany's EUR 0/year travelled.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True)
        previous = {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {
                    "id": "xx-legacy",
                    "publisher": "Legacy",
                    "title": "legacy",
                    "url": "https://example.org/legacy",
                    "source_type": "OFFICIAL_GOVERNMENT",
                }
            ],
            "sections": {
                "education_costs": {
                    "tuition_fees": {
                        "public": {
                            "bachelor": {
                                "value": 0,
                                "value_status": "OFFICIAL_GOVERNMENT",
                                "currency": "EUR",
                                "per": "year",
                                "as_of": "2026",
                                "source_ids": ["xx-legacy"],
                            }
                        }
                    }
                }
            },
            "gaps": [],
        }
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("post_study_work", value=12, unit="months",
                                                  study_level="bachelor")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        document = json.loads((corpus / "XX.json").read_text(encoding="utf-8"))
        node = _dig(document["sections"], list(CANON))
        assert node["value"] is None, "a carried-forward unauditable zero was published"
        assert node["value_status"] == "UNKNOWN"
        assert derive_tuition(document["sections"], "bachelor", 0.0).value is None

    def test_carried_forward_zero_keeps_its_provenance(self, tmp_path: Path):
        """A refusal must stay reviewable, or the next pass cannot audit it."""
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True)
        previous = {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {
                    "id": "xx-legacy",
                    "publisher": "Legacy",
                    "title": "legacy",
                    "url": "https://example.org/legacy",
                    "source_type": "OFFICIAL_GOVERNMENT",
                }
            ],
            "sections": {
                "education_costs": {
                    "tuition_fees": {
                        "public": {
                            "bachelor": {
                                "value": 0,
                                "value_status": "OFFICIAL_GOVERNMENT",
                                "currency": "EUR",
                                "per": "year",
                                "as_of": "2026",
                                "source_ids": ["xx-legacy"],
                            }
                        }
                    }
                }
            },
            "gaps": [],
        }
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("post_study_work", value=12, unit="months",
                                                  study_level="bachelor")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        document = json.loads((corpus / "XX.json").read_text(encoding="utf-8"))
        node = _dig(document["sections"], list(CANON))
        assert node["source_ids"] == ["xx-legacy"]
        assert node["as_of"] == "2026"
        assert "not archived" in node["note"] or "cannot be audited" in node["note"]
        assert any(
            "bachelor" in gap["field"] for gap in document.get("gaps", [])
        ), "the refusal must be published as a gap"

    def test_a_zero_is_not_republished_by_its_own_refusal(self, tmp_path: Path):
        """A second ingest must not re-append the refusal note forever."""
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True)
        previous = {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {"id": "xx-legacy", "publisher": "L", "title": "l",
                 "url": "https://example.org/l", "source_type": "OFFICIAL_GOVERNMENT"}
            ],
            "sections": {
                "education_costs": {
                    "tuition_fees": {
                        "public": {
                            "bachelor": {
                                "value": 0, "value_status": "OFFICIAL_GOVERNMENT",
                                "currency": "EUR", "per": "year", "as_of": "2026",
                                "source_ids": ["xx-legacy"],
                            }
                        }
                    }
                }
            },
            "gaps": [],
        }
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("post_study_work", value=12, unit="months",
                                                  study_level="bachelor")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        first = (corpus / "XX.json").read_text(encoding="utf-8")
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        second = (corpus / "XX.json").read_text(encoding="utf-8")
        assert first == second, "a rebuild changed a file it should have left identical"

    def test_a_non_cost_zero_is_not_demoted(self, tmp_path: Path):
        """A count that happens to be zero is not a cost and must not be judged as one."""
        _, ctx = _build(
            tmp_path,
            [
                _artifact(
                    "bachelor_tuition",
                    value=0,
                    unit="bachelor degrees qualifying for tuition exemption",
                )
            ],
        )
        sections = ctx["document"].get("sections", {})
        zeros = [(p, n) for p, n in _claim_paths(sections) if n.get("value") == 0]
        assert zeros, "the evidence must be preserved"
        for path, node in zeros:
            assert not _is_cost(path), f"a non-cost zero was demoted at {path}"
            assert node["value_status"] != "UNKNOWN"

    def _carried_previous(self, node: dict) -> dict:
        """A previous canonical file whose only tuition claim is ``node``."""
        return {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {"id": "xx-legacy", "publisher": "L", "title": "l",
                 "url": "https://example.org/l", "source_type": "OFFICIAL_GOVERNMENT"}
            ],
            "sections": {
                "education_costs": {"tuition_fees": {"public": {"bachelor": node}}}
            },
            "gaps": [],
        }

    def _rebuild_over(self, previous: dict, tmp_path: Path) -> dict:
        """Rebuild a country whose previous file exists and whose new build says
        nothing about tuition, so the claim travels by carry-forward."""
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True, exist_ok=True)
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("post_study_work", value=12,
                                                  unit="months", study_level="bachelor")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        return json.loads((corpus / "XX.json").read_text(encoding="utf-8"))

    def test_carried_forward_zero_citing_no_source_is_refused(self, tmp_path: Path):
        """An unsourced zero is an assumption, and this path is the only one that
        can produce one: the fresh claim loop refuses a claim with no source id
        before it reaches a node, while a claim arriving by carry-forward is never
        re-checked for that."""
        document = self._rebuild_over(
            self._carried_previous(
                {"value": 0, "value_status": "OFFICIAL_GOVERNMENT", "currency": "EUR",
                 "per": "year", "as_of": "2026", "source_ids": []}
            ),
            tmp_path,
        )
        node = _dig(document["sections"], list(CANON))
        assert node["value"] is None
        assert node["value_status"] == "UNKNOWN"

    def test_carried_forward_zero_with_no_currency_is_refused(self, tmp_path: Path):
        """A zero that states no currency cannot be told apart from a count."""
        document = self._rebuild_over(
            self._carried_previous(
                {"value": 0, "value_status": "OFFICIAL_GOVERNMENT", "per": "year",
                 "as_of": "2026", "source_ids": ["xx-legacy"]}
            ),
            tmp_path,
        )
        node = _dig(document["sections"], list(CANON))
        assert node["value"] is None
        assert node["value_status"] == "UNKNOWN"

    def test_carried_forward_zero_with_no_period_is_refused(self, tmp_path: Path):
        """"Zero per year" and "zero per semester" are different claims."""
        document = self._rebuild_over(
            self._carried_previous(
                {"value": 0, "value_status": "OFFICIAL_GOVERNMENT", "currency": "EUR",
                 "as_of": "2026", "source_ids": ["xx-legacy"]}
            ),
            tmp_path,
        )
        node = _dig(document["sections"], list(CANON))
        assert node["value"] is None
        assert node["value_status"] == "UNKNOWN"

    def test_carried_forward_zero_fully_evidenced_is_published(self, tmp_path: Path):
        """The positive case on the carry-forward path too.

        The rule must not become "refuse every zero": a claim whose source is
        archived, which cites it, and which states both a currency and a period is
        audited evidence and is published.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True, exist_ok=True)
        previous = self._carried_previous(
            {"value": 0, "value_status": "UNIVERSITY_OFFICIAL", "currency": "EUR",
             "per": "year", "as_of": "2026", "source_ids": ["xx-s1"]}
        )
        # An archived artifact proving source xx-s1 exists for this country.
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("post_study_work", value=12,
                                                  unit="months", study_level="bachelor")])
        document = json.loads(json.dumps(previous))
        document["sources"].append(
            {"id": "xx-s1", "publisher": "P", "title": "t",
             "url": "https://example.org/s1", "source_type": "UNIVERSITY_OFFICIAL",
             "archived": True}
        )
        (corpus / "XX.json").write_text(json.dumps(document), encoding="utf-8")
        merged = ingest._merge_existing(
            {
                "country": previous["country"],
                "contract_version": previous["contract_version"],
                "research": previous["research"],
                "sources": document["sources"],
                "sections": {},
                "gaps": [],
            },
            corpus / "XX.json",
            type("R", (), {"warnings": [], "normalisations": [], "iso2": "XX"})(),
        )
        node = _dig(merged["sections"], list(CANON))
        assert node["value"] == 0, "a fully evidenced carried zero was wrongly refused"
        assert node["value_status"] == "UNIVERSITY_OFFICIAL"

    def test_carried_forward_zero_with_no_currency_is_refused(self, tmp_path: Path):
        """A zero that states no currency cannot be told apart from a count.

        The source here **is** archived, so the archive rule is satisfied and the
        currency rule is the only thing standing between this claim and a published
        cost. That separation is the point: "archived" answers whether the page can
        be re-read, not whether the figure is money.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True, exist_ok=True)
        previous = self._carried_previous(
            {"value": 0, "value_status": "OFFICIAL_GOVERNMENT", "per": "year",
             "as_of": "2026", "source_ids": ["xx-s1"]}
        )
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        # The fresh build archives source xx-s1, so the carried claim is backed.
        raw = _write_raw(
            corpus, "XX",
            [_artifact("post_study_work", value=12, unit="months",
                       study_level="bachelor", source_id="xx-s1")],
        )
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        document = json.loads((corpus / "XX.json").read_text(encoding="utf-8"))
        node = _dig(document["sections"], list(CANON))
        assert node["value"] is None, "a currencyless zero reached a cost slot"
        assert node["value_status"] == "UNKNOWN"

    def test_fresh_sub_section_the_previous_file_lacks_is_not_dropped(self, tmp_path: Path):
        """A fresh section under a key the previous build never had must survive.

        The walk iterates the *previous* file's keys, so without a union at every
        depth a fresh ``tuition_fees.public`` was read, ingested, and then discarded
        whenever the previous file happened to hold ``tuition_fees.by_state``. The
        evidence was on disk the whole time.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True, exist_ok=True)
        previous = {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {"id": "xx-legacy", "publisher": "L", "title": "l",
                 "url": "https://example.org/l", "source_type": "OFFICIAL_GOVERNMENT"}
            ],
            "sections": {
                "education_costs": {
                    "tuition_fees": {
                        "by_state": {
                            "somewhere": {
                                "non_eu_per_semester": {
                                    "value": 1500, "value_status": "OFFICIAL_GOVERNMENT",
                                    "currency": "EUR", "per": "semester", "as_of": "2025",
                                    "source_ids": ["xx-legacy"],
                                }
                            }
                        }
                    }
                }
            },
            "gaps": [],
        }
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("bachelor_tuition", value=500,
                                                  unit="EUR per year")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        document = json.loads((corpus / "XX.json").read_text(encoding="utf-8"))
        tuition = document["sections"]["education_costs"]["tuition_fees"]
        # The fresh section is present...
        assert "public" in tuition, "the fresh sub-section was dropped by the merge"
        assert _dig(tuition, ["public", "bachelor"])["value"] == 500
        # ...and the previous one is still carried forward.
        assert _dig(tuition, ["by_state", "somewhere", "non_eu_per_semester"])["value"] == 1500

    def test_a_nonzero_tuition_is_untouched(self, tmp_path: Path):
        _, ctx = _build(
            tmp_path, [_artifact("bachelor_tuition", value=1234, unit="EUR per year")]
        )
        node = _dig(ctx["document"]["sections"], list(CANON))
        assert node["value"] == 1234
        assert node["value_status"] == "OFFICIAL_GOVERNMENT"


# ======================================================================================
# P0-B - the Bachelor path shape
# ======================================================================================


class TestBachelorPathShape:
    def test_the_writer_refuses_to_emit_a_doubled_level(self):
        """The invariant lives in the one function every canonical write passes through."""
        sections: dict = {}
        ingest._put(sections, ["education_costs", "tuition_fees", "public", "bachelor",
                               "bachelor"], {"value": 1, "value_status": "X"})
        node = _dig(sections, list(CANON))
        assert isinstance(node, dict) and node["value"] == 1
        assert "bachelor" not in node, "the doubled level reached the corpus"

    def test_canonical_claim_path_appends_the_level_only_once(self):
        base = ["education_costs", "tuition_fees", "public"]
        assert ingest.canonical_claim_path(base + ["bachelor"]) == base + ["bachelor"]
        assert ingest.canonical_claim_path(base + ["bachelor", "bachelor"]) == base + ["bachelor"]
        # Idempotent, and it does not touch a path naming two *different* levels.
        once = ingest.canonical_claim_path(base + ["bachelor"])
        assert ingest.canonical_claim_path(once) == once
        assert ingest.canonical_claim_path(base + ["master", "phd"]) == base + ["master", "phd"]

    def test_a_fresh_build_writes_the_canonical_path(self, tmp_path: Path):
        _, ctx = _build(
            tmp_path, [_artifact("bachelor_tuition", value=500, unit="EUR per year")]
        )
        node = _dig(ctx["document"]["sections"], list(CANON))
        assert node["value"] == 500

    def test_merge_does_not_re_nest_a_legacy_doubled_path(self, tmp_path: Path):
        """**The P0-B defect, reproduced in isolation.**

        The previous file holds ``...public.bachelor.bachelor``; this build writes
        ``...public.bachelor``. Before the fix the merge recursed one level too far,
        carried the old claim forward and dropped the fresh one, so the output kept
        the malformed shape and the researched figure never reached
        ``derive_tuition``.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True)
        previous = {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {"id": "xx-legacy", "publisher": "L", "title": "l",
                 "url": "https://example.org/l", "source_type": "OFFICIAL_GOVERNMENT"}
            ],
            "sections": {
                "education_costs": {
                    "tuition_fees": {
                        "public": {
                            "bachelor": {
                                "bachelor": {
                                    "value": 1, "value_status": "UNIVERSITY_OFFICIAL",
                                    "currency": "EUR", "per": "year", "as_of": "2025",
                                    "source_ids": ["xx-legacy"],
                                }
                            }
                        }
                    }
                }
            },
            "gaps": [],
        }
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("bachelor_tuition", value=500,
                                                  unit="EUR per year")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        document = json.loads((corpus / "XX.json").read_text(encoding="utf-8"))
        sections = document["sections"]

        doubled = [p for p, _ in _claim_paths(sections) if p.split(".").count("bachelor") > 1]
        assert not doubled, f"the merge re-created a doubled level: {doubled}"

        node = _dig(sections, list(CANON))
        assert node["value"] == 500, "the fresh canonical claim was discarded by the merge"
        assert derive_tuition(sections, "bachelor", 0.0).value == 500.0

    def test_a_legacy_claim_with_no_fresh_evidence_is_kept_not_deleted(self, tmp_path: Path):
        """Re-shaping history must not cost evidence."""
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True)
        previous = {
            "country": {"iso2": "XX", "name_en": "X", "currency": None},
            "contract_version": ingest.CONTRACT_VERSION,
            "research": {"researched_at": "", "evidence_artifact_count": 1},
            "sources": [
                {"id": "xx-legacy", "publisher": "L", "title": "l",
                 "url": "https://example.org/l", "source_type": "OFFICIAL_GOVERNMENT"}
            ],
            "sections": {
                "education_costs": {
                    "tuition_fees": {
                        "public": {
                            "bachelor": {
                                "bachelor": {
                                    "value": 42, "value_status": "UNIVERSITY_OFFICIAL",
                                    "currency": "EUR", "per": "year", "as_of": "2025",
                                    "source_ids": ["xx-legacy"],
                                    "note": "a reviewed hand-curated figure",
                                }
                            }
                        }
                    }
                }
            },
            "gaps": [],
        }
        (corpus / "XX.json").write_text(json.dumps(previous), encoding="utf-8")
        raw = _write_raw(corpus, "XX", [_artifact("post_study_work", value=12, unit="months",
                                                  study_level="bachelor")])
        ingest.ingest_country_from_raw("XX", corpus_dir=corpus, raw_dir=raw)
        document = json.loads((corpus / "XX.json").read_text(encoding="utf-8"))
        node = _dig(document["sections"], list(CANON))
        assert node is not None, "the legacy claim was deleted instead of re-shaped"
        assert node["value"] == 42
        assert node["source_ids"] == ["xx-legacy"], "lineage was lost in the re-shape"
        assert node["note"].startswith("a reviewed hand-curated figure")

    #: Countries whose canonical file ingestion currently refuses to regenerate, so
    #: the shared merge fix cannot reach them. This is **not** the P0-B defect - the
    #: malformed path in these files was produced by that defect and will be repaired
    #: the moment ingestion can rebuild the file. The blocker is separate and
    #: pre-existing: ``_find_placeholders`` scans every string in a raw artifact,
    #: including free-text prose, and a researcher's honest *disclaimer* containing
    #: the word "placeholder" rejects the entire country before anything is written.
    #:
    #: US/030_net_monthly_income.json says "the underlying gross wage here is a
    #: placeholder: no BLS graduate-specific wage was established in this pass". Its
    #: four claim values are real and derive from a verbatim IRS Publication 15-T
    #: extract. The guard cannot tell a disclosure from a placeholder, so the country
    #: is dropped and its file keeps the shape the merge bug left behind.
    #:
    #: Left as a named set rather than worked around: hand-editing US.json would
    #: violate the rule that generated canonical JSON is never edited to paper over a
    #: pipeline defect, and narrowing the placeholder guard is a different contract
    #: that was explicitly ruled out of scope for this change.
    UNREBUILDABLE_COUNTRIES = frozenset({"US"})

    def _doubled_bachelor_paths(self) -> list[str]:
        corpus = BACKEND / "config" / "country_intelligence"
        offenders: list[str] = []
        for path in sorted(corpus.glob("*.json")):
            if len(path.stem) != 2:
                continue
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            for claim_path, _ in _claim_paths(document.get("sections", {})):
                if claim_path.split(".").count("bachelor") > 1:
                    offenders.append(f"{path.stem}: {claim_path}")
        return offenders

    def test_no_rebuildable_country_has_a_doubled_bachelor_path(self):
        """The end state Phase 8 requires, for every country ingestion can rebuild."""
        offenders = [
            offender
            for offender in self._doubled_bachelor_paths()
            if offender.split(":", 1)[0] not in self.UNREBUILDABLE_COUNTRIES
        ]
        assert not offenders, "doubled bachelor paths remain: " + "; ".join(offenders)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "P0-B is fixed at the shared contract and repairs 12 of the 13 affected "
            "countries. US is the 13th and cannot be rebuilt yet: a pre-existing, "
            "independently-diagnosed defect in _find_placeholders rejects the whole "
            "country because a research note contains the word 'placeholder' in a "
            "disclaimer. strict=True so that fixing the blocker turns this into a "
            "hard failure that forces the marker to be removed, rather than leaving a "
            "malformed path in the corpus unnoticed."
        ),
    )
    def test_the_shipped_corpus_has_no_doubled_bachelor_path(self):
        """The full Phase 8 invariant across every country in the corpus."""
        offenders = self._doubled_bachelor_paths()
        assert not offenders, "doubled bachelor paths remain: " + "; ".join(offenders)

    def test_the_unrebuildable_set_is_still_accurate(self):
        """If US becomes rebuildable, this names the discrepancy instead of hiding it."""
        actual = {
            offender.split(":", 1)[0]
            for offender in self._doubled_bachelor_paths()
        }
        stale = actual - self.UNREBUILDABLE_COUNTRIES
        assert not stale, (
            f"{sorted(stale)} now has a doubled bachelor path but is not in "
            f"UNREBUILDABLE_COUNTRIES; the exclusion list must not become a loophole"
        )

    def test_the_shipped_corpus_publishes_no_unsupported_cost_zero(self):
        """The end state Phase 10 requires of Germany's committed record."""
        corpus = BACKEND / "config" / "country_intelligence"
        offenders = []
        for path in sorted(corpus.glob("*.json")):
            if len(path.stem) != 2:
                continue
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            for claim_path, node in _claim_paths(document.get("sections", {})):
                if node.get("value") == 0 and _is_cost(claim_path):
                    offenders.append(f"{path.stem}: {claim_path}")
        assert not offenders, "unsupported cost zeros remain: " + "; ".join(offenders)


# ======================================================================================
# derive_tuition - Phase 9: no fallbacks, no guessing
# ======================================================================================


class TestDerivationContract:
    def test_it_reads_only_the_canonical_path(self):
        sections = {"education_costs": {"tuition_fees": {"public": {"bachelor": {
            "value": 100, "value_status": "OFFICIAL_GOVERNMENT", "currency": "EUR",
        }}}}}
        assert derive_tuition(sections, "bachelor", 0.0).value == 100.0

    def test_it_refuses_when_the_canonical_path_is_absent(self):
        """No fallback search: a value under any other path is not tuition."""
        sections = {"education_costs": {"tuition_fees": {
            "by_university": {"tum": {"bachelor": {
                "value": 3000, "value_status": "UNIVERSITY_OFFICIAL", "currency": "EUR",
            }}},
            "public": {"phd": {"value": 0, "value_status": "OFFICIAL_GOVERNORMAL"}},
        }}}
        result = derive_tuition(sections, "bachelor", 0.0)
        assert result.value is None
        assert "No fallback path is searched" in result.reason

    def test_it_refuses_a_doubled_level_rather_than_guessing(self):
        """Malformed nesting must not become readable by accident."""
        sections = {"education_costs": {"tuition_fees": {"public": {"bachelor": {
            "bachelor": {"value": 56120, "value_status": "UNIVERSITY_OFFICIAL",
                         "currency": "AUD"},
        }}}}}
        assert derive_tuition(sections, "bachelor", 0.0).value is None

    def test_it_labels_a_period_child_rather_than_silently_substituting(self):
        """A semester figure is a different quantity and is labelled, not substituted."""
        sections = {"education_costs": {"tuition_fees": {"public": {"bachelor": {
            "semester": {"value": 726.72, "value_status": "OFFICIAL_REGIONAL_BODY",
                         "currency": "EUR", "per": "semester"},
        }}}}}
        result = derive_tuition(sections, "bachelor", 0.0)
        # It is returned, because a registered period representation is part of the
        # formula contract - but the refusal reason must say where it came from and
        # that it is not an annual figure.
        _, reason = _find_tuition_claim(sections, "bachelor")
        assert "semester" in reason
        assert "different" in reason and "quantity" in reason

