"""The campaign's published counts must match the evidence files.

The campaign directory holds a hundred evidence files and two documents
(``README.md``, ``ROLLOUT.md``) that quote their totals. A number in a document
is a claim about the data, and claims about data drift: the first draft of this
campaign reported "62 of the 91 newly researched records came back active" by
subtracting nothing from the 100-check total, which was wrong by four because 4
of the 62 were spot-checks of records that were already active.

These tests recompute every number the documents publish from the evidence
files, so a document that drifts from the data fails CI rather than shipping a
figure nobody can reproduce.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CAMPAIGN = Path(__file__).resolve().parents[2] / "verification" / "campaign-2026-10-12"

# What the documents claim. Kept as literals so a wrong edit to the documents
# fails here.
EXPECTED_ALL = {"active": 62, "needs_review": 29, "conflicting": 7, "quarantined": 2}
EXPECTED_VERIFY = {"active": 58, "needs_review": 26, "conflicting": 5, "quarantined": 2}
EXPECTED_SPOT = {"active": 4, "needs_review": 3, "conflicting": 2, "quarantined": 0}
EXPECTED_PROPOSALS = 45
EXPECTED_PROMOTIONS = ["23", "526", "631", "643", "657"]
SPOT_CHECK_FAILURES = ["131", "189", "245", "303", "422"]
FIVE_STILL_ACTIVE = SPOT_CHECK_FAILURES  # the same five: still `active` in the DB


def _load_evidence():
    loaded = []
    for path in sorted(CAMPAIGN.glob("*.json")):
        if path.name in {"campaign-report.json", "index.json", "proposed-verification-updates.json", "tasks-spot-check.json", "tasks-to-verify.json"}:
            continue
        if not path.stem.isdigit():
            continue
        loaded.append(json.loads(path.read_text(encoding="utf-8")))
    return loaded


def _kinds():
    index = json.loads((CAMPAIGN / "index.json").read_text(encoding="utf-8"))
    return {str(task["id"]): task["kind"] for task in index["tasks"]}


@pytest.fixture(scope="module")
def evidence():
    loaded = _load_evidence()
    assert len(loaded) == 100, f"expected 100 evidence files, found {len(loaded)}"
    return loaded


@pytest.fixture(scope="module")
def kinds():
    return _kinds()


@pytest.fixture(scope="module")
def proposals():
    return json.loads((CAMPAIGN / "proposed-verification-updates.json").read_text(encoding="utf-8"))["proposals"]


def _count(rows, verdict):
    return [row for row in rows if row["verdict"] == verdict]


def _split(evidence, kinds):
    verify = [row for row in evidence if kinds[str(row["id"])] != "spot-check"]
    spot = [row for row in evidence if kinds[str(row["id"])] == "spot-check"]
    return verify, spot


# ── the counts the documents publish ───────────────────────────────────


def test_every_evidence_file_is_valid_json(evidence):
    for row in evidence:
        for key in ("id", "verdict", "confidence", "checked_at", "sources", "findings"):
            assert key in row, f"id {row.get('id')} is missing {key}"
        assert row["verdict"] in {"active", "needs_review", "conflicting", "quarantined"}
        assert row["confidence"] in {"high", "medium", "low"}


def test_total_counts_across_all_100_checks(evidence):
    actual = {verdict: len(_count(evidence, verdict)) for verdict in EXPECTED_ALL}
    assert actual == EXPECTED_ALL
    assert sum(actual.values()) == 100


def test_the_91_newly_researched_records(evidence, kinds):
    verify, _ = _split(evidence, kinds)
    actual = {verdict: len(_count(verify, verdict)) for verdict in EXPECTED_VERIFY}
    assert actual == EXPECTED_VERIFY
    assert sum(actual.values()) == 91


def test_the_nine_spot_checks(evidence, kinds):
    _, spot = _split(evidence, kinds)
    actual = {verdict: len(_count(spot, verdict)) for verdict in EXPECTED_SPOT}
    assert actual == EXPECTED_SPOT
    assert sum(actual.values()) == 9


def test_the_two_groups_add_up_to_the_total(evidence, kinds):
    verify, spot = _split(evidence, kinds)
    for verdict in EXPECTED_ALL:
        assert len(_count(verify, verdict)) + len(_count(spot, verdict)) == EXPECTED_ALL[verdict], (
            f"{verdict}: the split does not add up to the published total"
        )


def test_no_record_was_confirmed_from_a_search_snippet_alone(evidence):
    low = [row["id"] for row in evidence if row["confidence"] == "low"]
    assert low, "expected the low-confidence cases to still be recorded"
    for row in evidence:
        if row["confidence"] == "low":
            assert row["verdict"] != "active", (
                f"id {row['id']} is marked active with low confidence"
            )
        for source in row.get("sources", []):
            assert source["url"].startswith("http"), f"id {row['id']} has a source without a URL"


# ── the proposals ──────────────────────────────────────────────────────


def test_proposal_counts(proposals):
    assert len(proposals) == EXPECTED_PROPOSALS
    by_verdict = {}
    for proposal in proposals:
        by_verdict[proposal["evidence_verdict"]] = by_verdict.get(proposal["evidence_verdict"], 0) + 1
    assert by_verdict == {"needs_review": 29, "conflicting": 7, "active": 7, "quarantined": 2}


def test_the_proposed_promotions(proposals, kinds):
    """The five records the evidence would promote to active.

    These are the ones the flag acts on, so they are called out explicitly -
    including in the rollout document, because promoting them before the
    downgrades is what makes the flag show bad records as verified.
    """
    promoted = sorted(
        p["id"]
        for p in proposals
        if p["evidence_verdict"] == "active" and p["current_status"] != "active"
    )
    assert promoted == sorted(EXPECTED_PROMOTIONS)


def test_no_proposal_promotes_a_record_without_a_status_change(proposals):
    for proposal in proposals:
        if proposal["evidence_verdict"] == "active" and proposal["current_status"] == "active":
            assert proposal["suggested_status"] == "active"
            # A status-unchanged row must carry a field change, or it is noise.
            fields = proposal["field_updates"]
            assert any(fields.get(key) for key in ("official_source_url", "deadline_text", "deadline_date")), (
                f"id {proposal['id']} proposes nothing"
            )


def test_the_five_spot_check_failures_are_all_proposed_for_review(proposals):
    """The five the spot check found against records marked active.

    They stay `active` in the database - this campaign changes nothing - which
    is the reason the validated-only flag must not be switched on yet.
    """
    proposed = {str(proposal["id"]): proposal for proposal in proposals}
    for record_id in FIVE_STILL_ACTIVE:
        assert record_id in proposed, f"spot-check failure {record_id} has no proposal"
        proposal = proposed[record_id]
        assert proposal["current_status"] == "active", (
            f"{record_id} is no longer marked active in the database; this test's premise is stale"
        )
        assert proposal["suggested_status"] in {"needs_review", "conflicting"}, (
            f"{record_id} must not be proposed for promotion"
        )


def test_every_proposal_keeps_its_evidence(proposals):
    for proposal in proposals:
        for suffix in (".json", ".md"):
            assert (CAMPAIGN / f"{proposal['id']}{suffix}").exists(), (
                f"proposal {proposal['id']} has no {suffix} evidence file"
            )


def test_no_proposal_puts_a_closed_round_back_on_sale(proposals):
    """A proposal whose evidence says the round is over must not suggest open.

    Read from the evidence rather than a hardcoded list, so a new proposal
    enters the same check automatically.
    """
    closed_markers = (
        "closed for applications",
        "no more grants",
        "no currently-open",
        "round has closed",
        "cycle has closed",
        "no cycle is open",
        "not currently open",
        "budget is exhausted",
        "deadline has passed",
        "has now closed",
        "is now closed",
    )
    promoted = []
    for proposal in proposals:
        if proposal["evidence_verdict"] != "active":
            continue
        evidence = json.loads((CAMPAIGN / f"{proposal['id']}.json").read_text(encoding="utf-8"))
        text = " ".join(
            str(value)
            for value in (
                evidence.get("notes_for_reviewer"),
                (evidence.get("findings") or {}).get("deadline", {}).get("detail"),
                (evidence.get("recommended_field_updates") or {}).get("verification_notes"),
            )
            if value
        ).lower()
        if any(marker in text for marker in closed_markers):
            promoted.append(proposal["id"])
    assert promoted == [], f"these promotions describe a closed round: {promoted}"


# ── the documents agree with the data ──────────────────────────────────


@pytest.fixture(scope="module")
def readme():
    return (CAMPAIGN / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rollout():
    return (CAMPAIGN / "ROLLOUT.md").read_text(encoding="utf-8")


def test_first_draft_did_not_report_the_total_as_the_91_record_figure(readme):
    """The first draft said 62 of the 91; the correct figure is 58.

    62 is the total across all 100 checks, and 4 of them are spot-checks of
    records that were already active.
    """
    assert "**58**" in readme, "the 91-record active count must be published"
    assert "62 of the 91" not in readme, "the 100-check total must not be reported as the 91-record figure"
    assert "62 of them" not in readme
    assert "including 62 this campaign just confirmed" not in readme


def test_readme_table_matches_the_evidence(evidence, kinds, readme):
    verify, spot = _split(evidence, kinds)
    for verdict in EXPECTED_ALL:
        total = len(_count(evidence, verdict))
        assert f"| `{verdict}` |" in readme, f"{verdict} is missing from the results table"
        assert f"**{total}**" in readme, f"{verdict} total {total} is not in the table"
        assert f"**{len(_count(verify, verdict))}**" in readme, f"{verdict} verify count is not in the table"
        spot_total = len(_count(spot, verdict))
        assert str(spot_total) in readme


def test_rollout_states_that_merging_applies_nothing(rollout):
    assert "applies nothing" in rollout


def test_rollout_names_the_five_records_the_flag_would_expose(rollout):
    """The rollout warning is the whole point of this PR's second half."""
    for record_id in FIVE_STILL_ACTIVE:
        assert record_id in rollout, f"rollout does not name {record_id}"


def test_rollout_states_both_directions(rollout):
    lowered = rollout.lower()
    assert "58" in rollout, "the rollout must say how many records the evidence supports"
    assert "hide" in lowered or "hidden" in lowered or "hiding" in rollout.lower()
    assert "expose" in lowered or "visible" in lowered


def test_rollout_orders_the_flag_after_the_status_updates(rollout):
    lowered = rollout.lower()
    assert "before a reviewed status update" in lowered
    assert "no redeploy" in lowered, "the switch's reversibility is part of the rollout advice"


def test_reconciliation_plan_exists_and_is_generated_from_the_data():
    plan = (CAMPAIGN / "RECONCILIATION-PLAN.md").read_text(encoding="utf-8")
    assert "build-reconciliation-plan.mjs" in plan
    # The five promotions are the rows a reader must not skip.
    for record_id in EXPECTED_PROMOTIONS:
        assert f"| {record_id} |" in plan, f"the plan does not list {record_id}"
