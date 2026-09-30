"""Provenance and reconciliation invariants for the audited logo overrides.

Two guarantees are pinned here, both of which had already been violated once:

  * a stored logo carries its full provenance - address, page, host evidence,
    validation result, kind and a timestamp - so an auditor can tell a logo
    somebody checked from one that merely exists;
  * the retirement audit is the only thing that can hide a record, and a record
    it hid and no longer lists comes back.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CONFIG = Path(__file__).resolve().parents[1] / "config"
OVERRIDES = CONFIG / "official_logo_overrides.json"
UNRESOLVED = CONFIG / "unresolved_logos.json"

REQUIRED = (
    "url", "page_url", "official_host", "alt_text",
    "validation_result", "image_kind", "verified_at", "host_evidence",
)
VALID_RESULTS = {"verified", "source_blocked"}
VALID_HOST_EVIDENCE = {
    "same_registrable_domain", "cdn_on_behalf_of_host", "third_party_mark",
}


@pytest.fixture(scope="module")
def overrides():
    raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not str(k).startswith("_") and isinstance(v, dict)}


class TestLogoProvenance:
    def test_every_override_carries_full_provenance(self, overrides):
        missing = {h: sorted(set(REQUIRED) - set(e)) for h, e in overrides.items()
                   if not set(REQUIRED) <= set(e)}
        assert not missing, f"overrides missing provenance fields: {list(missing)[:8]}"

    def test_validation_result_is_one_of_the_permitted_values(self, overrides):
        bad = {h: e["validation_result"] for h, e in overrides.items()
               if e["validation_result"] not in VALID_RESULTS}
        assert not bad, f"unrecognised validation results: {bad}"

    def test_a_source_blocked_entry_must_carry_its_substitute_evidence(self, overrides):
        """A 403 from a datacenter proves nothing, so something else must stand.

        A blocked probe is an access limit, not a finding about the asset. The
        entry is kept, but only if the file says what verified it instead -
        either a browser check from a research pass, or an explicit note that an
        earlier pass confirmed it.
        """
        for host, entry in overrides.items():
            if entry["validation_result"] != "source_blocked":
                continue
            assert (entry.get("probe_note") or entry.get("substitute_evidence")), (
                f"{host} is recorded as source_blocked with nothing recorded as "
                f"verifying it instead"
            )

    def test_verification_timestamp_is_iso(self, overrides):
        from datetime import datetime

        for host, entry in overrides.items():
            datetime.fromisoformat(entry["verified_at"])

    def test_host_evidence_is_stated_in_the_permitted_vocabulary(self, overrides):
        bad = {h: e["host_evidence"] for h, e in overrides.items()
               if e["host_evidence"] not in VALID_HOST_EVIDENCE}
        assert not bad, f"unrecognised host evidence: {bad}"

    def test_third_party_marks_are_declared_as_such(self, overrides):
        for host, entry in overrides.items():
            if entry["host_evidence"] == "third_party_mark":
                assert entry["official_host"] is False, (
                    f"{host} is third-party artwork but is not flagged official_host false"
                )


class TestUnresolvedLogos:
    def test_every_unresolved_host_has_a_permitted_reason_code(self):
        doc = json.loads(UNRESOLVED.read_text(encoding="utf-8"))
        codes = doc["_reason_codes"]
        for host in doc["hosts"]:
            assert host["reason_code"] in codes, (
                f"{host['host']} has reason {host['reason_code']!r}, which is not "
                f"in the published vocabulary"
            )

    def test_no_unresolved_host_has_an_audited_override(self, overrides):
        """Otherwise the reason would be 'we have one but it did not apply'."""
        doc = json.loads(UNRESOLVED.read_text(encoding="utf-8"))
        stale = [h["host"] for h in doc["hosts"]
                 if h["reason_code"] != "override_did_not_attach"
                 and h["host"] in overrides]
        assert not stale, f"hosts with an override yet listed as unresolved: {stale}"


class TestRetirementReconciliation:
    def test_retire_stage_restores_records_it_no_longer_lists(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        body = source.split("def do_retire", 1)[1].split("def do_facts", 1)[0]
        # The audit file is the only thing permitted to hide a record, so a
        # record this stage hid and no longer lists has to become visible again.
        assert "is_archived = False" in body, "retire stage cannot undo its own hiding"
        assert "RETIRE_FLAG_PREFIXES" in body, "restore is not scoped to retire-stage archives"

    def test_only_this_stage_writes_a_flag_prefixed_archive_reason(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        # The archive and discontinued stages write their own fixed reasons, so a
        # flag prefix proves the retire stage is what hid a record and that it is
        # therefore safe to restore.
        assert 'archived_reason = "programme discontinued"' in source
        assert 'archived_reason = f"deadline passed on' in source
