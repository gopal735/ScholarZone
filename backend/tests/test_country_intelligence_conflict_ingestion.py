"""What happens when several archived figures land on one corpus field.

This file exists because an earlier version of the pipeline got this wrong, and
the wrong version was more confident than the right one.

Two artifacts reaching the same canonical path were being promoted to a
``CONFLICTING`` claim - the status that tells a student two credible sources
disagree. But a path collision is not a contradiction. Looking at what actually
collided in this corpus:

- Australia publishes three financial-capacity figures (a living-expenses
  element, an income-route figure and a travel element) under one topic.
- A Canadian tuition page gives a first-year figure, a later-year figure and an
  incidental fee.
- A Swiss work-rights topic carries 15 hours a week and a six-month job search,
  which do not even share a unit.

Labelling those "sources disagree" would assert something false and alarming
about authorities that never contradicted themselves. That is false precision in
the opposite direction to the one a conflict status prevents, and it is worse
than the honest alternative: a gap naming every figure.

So the rule under test is: a collision publishes a gap that names each figure and
says the schema cannot separate them; no value is averaged and no single figure is
presented as *the* answer. The ``CONFLICTING`` status itself remains available and
is covered in ``test_country_intelligence_status_contract.py`` for research that
explicitly declares a genuine disagreement.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_spec = importlib.util.spec_from_file_location(
    "ingest_country_intelligence", BACKEND / "scripts" / "ingest_country_intelligence.py"
)
assert _spec and _spec.loader
ingest = importlib.util.module_from_spec(_spec)
# Registered before execution: the module's dataclasses resolve their own
# namespace through sys.modules, and an unregistered module makes the decorator
# fail with an opaque AttributeError.
sys.modules["ingest_country_intelligence"] = ingest
_spec.loader.exec_module(ingest)


def _artifact(claim_id: str, value, unit: str, source_id: str, url: str, statement: str):
    """One archived artifact asserting one figure for the ``bachelor_tuition`` topic."""
    return {
        "country": "DE",
        "topic": "bachelor_tuition",
        "source_id": source_id,
        "source_url": url,
        "source_type": "UNIVERSITY_OFFICIAL",
        "publisher": f"Publisher {source_id}",
        "retrieved_at": "2026-10-05",
        "as_of": "2026",
        "raw_extract": statement,
        "claims": [
            {
                "claim_id": claim_id,
                "value": value,
                "unit": unit,
                "as_of": "2026",
                "study_level": "bachelor",
                "statement": statement,
            }
        ],
    }


@pytest.fixture
def colliding_archive(tmp_path):
    """Two artifacts from the same publisher giving different figures.

    Same source on purpose. A same-source collision cannot be a conflict between
    authorities, which is exactly the case the earlier version mislabelled.
    """
    raw = tmp_path / "research_raw" / "DE"
    raw.mkdir(parents=True)
    (raw / "001_first.json").write_text(
        json.dumps(
            _artifact(
                "de-bach-1", 66110, "CAD per year", "utsc",
                "https://utsc.utoronto.ca/costs/financial-support",
                "First-year tuition is CAD 66,110.",
            )
        ),
        encoding="utf-8",
    )
    (raw / "002_second.json").write_text(
        json.dumps(
            _artifact(
                "de-bach-2", 2286, "CAD per year", "utsc",
                "https://utsc.utoronto.ca/costs/financial-support",
                "Incidental fees are CAD 2,286.",
            )
        ),
        encoding="utf-8",
    )
    return tmp_path


def _load_de(root: Path):
    from app.services.country_intelligence.corpus import load_corpus

    corpus = load_corpus(root)
    return next(r for r in corpus.records if r.iso2 == "DE")


def _find(node, status):
    if isinstance(node, dict):
        if node.get("value_status") == status:
            yield node
        for value in node.values():
            yield from _find(value, status)
    elif isinstance(node, list):
        for item in node:
            yield from _find(item, status)


class TestCollisionsAreNotConflicts:
    def test_the_archive_ingests(self, colliding_archive):
        report = ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive,
            raw_dir=colliding_archive / "research_raw" / "DE",
        )
        assert report.written, report.reason

    def test_no_conflicting_claim_is_invented(self, colliding_archive):
        """The central regression guard.

        A same-source path collision must not be promoted to CONFLICTING. Telling a
        student that two authorities disagree when one publisher simply published
        several figures is a false claim about a real authority.
        """
        ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive,
            raw_dir=colliding_archive / "research_raw" / "DE",
        )
        record = _load_de(colliding_archive)
        assert list(_find(record.sections, "CONFLICTING")) == []

    def test_no_value_is_averaged(self, colliding_archive):
        ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive,
            raw_dir=colliding_archive / "research_raw" / "DE",
        )
        record = _load_de(colliding_archive)
        published = [
            claim.value
            for claim in record.claims.values()
            if claim.value is not None
        ]
        # The midpoint of 66110 and 2286 is 34198. If it appears, something averaged.
        assert 34198 not in published

    def test_every_figure_is_preserved(self, colliding_archive):
        """Nothing may be dropped: the second figure travels attached to the first
        so that a reviewer can see what else the topic contained."""
        ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive,
            raw_dir=colliding_archive / "research_raw" / "DE",
        )
        record = _load_de(colliding_archive)
        colliding = list(_find(record.sections, "UNIVERSITY_OFFICIAL"))
        found = [
            item.get("value")
            for node in colliding
            for item in node.get("colliding_values", [])
        ]
        assert sorted(found) == [2286, 66110]

    def test_the_gap_names_every_figure(self, colliding_archive):
        ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive,
            raw_dir=colliding_archive / "research_raw" / "DE",
        )
        record = _load_de(colliding_archive)
        reasons = " ".join(gap.reason for gap in record.gaps)
        assert "66110" in reasons
        assert "2286" in reasons
        assert "no average was computed" in reasons.lower()

    def test_the_gap_says_it_is_not_necessarily_a_contradiction(self, colliding_archive):
        """The wording has to stop a reader from concluding the authorities
        disagreed, because that is the inference the gap must not invite."""
        ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive,
            raw_dir=colliding_archive / "research_raw" / "DE",
        )
        record = _load_de(colliding_archive)
        reasons = " ".join(gap.reason for gap in record.gaps).lower()
        assert "not necessarily a contradiction" in reasons

    def test_rebuilding_does_not_grow_the_collision_list(self, colliding_archive):
        raw = colliding_archive / "research_raw" / "DE"
        for _ in range(3):
            ingest.ingest_country_from_raw(
                "DE", corpus_dir=colliding_archive, raw_dir=raw
            )
        record = _load_de(colliding_archive)
        colliding = list(_find(record.sections, "UNIVERSITY_OFFICIAL"))
        assert all(len(node.get("colliding_values", [])) == 2 for node in colliding)

    def test_the_gap_list_does_not_grow_across_rebuilds(self, colliding_archive):
        raw = colliding_archive / "research_raw" / "DE"
        ingest.ingest_country_from_raw("DE", corpus_dir=colliding_archive, raw_dir=raw)
        first = len(_load_de(colliding_archive).gaps)
        for _ in range(3):
            ingest.ingest_country_from_raw(
                "DE", corpus_dir=colliding_archive, raw_dir=raw
            )
        assert len(_load_de(colliding_archive).gaps) == first

    def test_colliding_values_are_not_validated_as_nested_claims(self, colliding_archive):
        """The walker must not descend into the collision list.

        It did this with the conflict list, and each alternative inherited the
        parent status and was validated as a standalone claim - which made every
        conflict unpublishable.
        """
        raw = colliding_archive / "research_raw" / "DE"
        report = ingest.ingest_country_from_raw(
            "DE", corpus_dir=colliding_archive, raw_dir=raw
        )
        assert report.written
        assert not any("colliding_values[" in problem.reason for problem in
                       __import__("app.services.country_intelligence.corpus",
                                  fromlist=["load_corpus"]).load_corpus(
                                      colliding_archive).problems)

