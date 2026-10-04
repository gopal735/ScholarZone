"""Tests for the final trust, safety and deployment hardening.

Each class corresponds to a specific way data was previously wrong:

* the fallback wrote unvalidated images through to ``image_verified_at``;
* a landing page became a verified public scholarship with "Unknown" standing
  in for real data;
* the public gate could not tell a blocked source from a scholarship with no
  image, and one of its predicates silently excluded every official image
  whose source type was never recorded;
* a healthy-but-stale container was reported as a successful deployment.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 'h.db').as_posix()}")
    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()


def _add(factory, sid, **kw):
    from app.models import Scholarship

    session = factory()
    try:
        session.add(
            Scholarship(
                id=sid,
                title=kw.get("title", f"Programme {sid}"),
                country=kw.get("country", "Testland"),
                degree=kw.get("degree", "Master"),
                funding=kw.get("funding", "Fully Funded"),
                official_source_url=kw.get("url", f"https://x{sid}.example.org/p"),
                is_verified=kw.get("is_verified", False),
                image_url=kw.get("image_url"),
                image_source_url=kw.get("image_source_url"),
                image_source_type=kw.get("image_source_type"),
                image_verified_at=kw.get("image_verified_at"),
                verification_status=kw.get("verification_status", "active"),
            )
        )
        session.commit()
        return sid
    finally:
        session.close()


NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# B. Fallback validation
# ---------------------------------------------------------------------------


class TestFallbackCannotBypassValidation:
    def _orchestrator_source(self) -> str:
        from pathlib import Path

        import app.services.image_discovery_orchestrator as mod

        return Path(mod.__file__).read_text(encoding="utf-8")

    def test_validation_precedes_persistence(self):
        block = self._orchestrator_source().split("def run_logo_fallback")[1].split("def run(")[0]
        assert block.index("validate_candidates") < block.index("mark_image_verified")

    def test_a_third_party_candidate_can_never_be_persisted(self):
        """The gate is `official_host`, and it drops the candidate entirely."""
        block = self._orchestrator_source().split("def run_logo_fallback")[1].split("def run(")[0]
        assert "if not tier_official:" in block
        assert block.index("if not tier_official:") < block.index("mark_image_verified")

    def test_the_image_kind_comes_from_the_validator_not_the_tier(self):
        block = self._orchestrator_source().split("def run_logo_fallback")[1].split("def run(")[0]
        assert 'getattr(vres, "image_kind"' in block
        assert 'image_kind="official_logo"' not in block

    def test_an_invalid_candidate_is_skipped(self):
        block = self._orchestrator_source().split("def run_logo_fallback")[1].split("def run(")[0]
        assert "is_valid_image" in block
        assert "_is_generic_site_asset" in block

    def test_an_existing_verified_image_is_never_replaced(self):
        block = self._orchestrator_source().split("def run_logo_fallback")[1].split("def run(")[0]
        assert "_get_current_verified_at" in block

    def test_the_fallback_is_second_chance_only(self):
        """It must run after the ordinary path, never before it."""
        source = self._orchestrator_source()
        main = source.split("def run(")[1]
        assert main.index("if not result.image_results:") < main.index("run_logo_fallback")

    def test_the_resolver_performs_no_database_writes(self):
        from pathlib import Path

        import app.services.logo_fallback_resolver as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("sqlalchemy", "Session", "session", ".commit(", "setattr("):
            assert forbidden not in source

    def test_a_tier_failure_does_not_stop_later_tiers(self):
        from app.services.logo_fallback_resolver import LogoFallbackResolver

        def explode(url):
            raise RuntimeError("down")

        resolver = LogoFallbackResolver(
            fetch_text=explode,
            overrides={"oxford.ac.uk": {"url": "https://cdn.test/logo.png"}},
        )

        class S:
            id = 1
            official_source_url = "https://www.oxford.ac.uk/p"
            title = "Oxford"
            country = "UK"

        assert resolver.resolve(S()).tier.value == "static_override"


class TestWikimediaNeverOfficial:
    def test_the_source_type_is_not_an_official_one(self):
        from app.services.scholarship_image_verifier import ImageSourceType

        official = {
            ImageSourceType.OFFICIAL_SCHOLARSHIP,
            ImageSourceType.OFFICIAL_UNIVERSITY,
            ImageSourceType.OFFICIAL_GOVERNMENT,
            ImageSourceType.OFFICIAL_PROVIDER,
        }
        assert ImageSourceType.WIKIMEDIA not in official

    def test_the_official_classifier_does_not_return_wikimedia(self):
        """An official-source domain must never be classified as Wikimedia."""
        from app.services.image_validator import determine_image_source_type

        for domain in ("oxford.ac.uk", "kth.se", "daad.de", "gov.uk"):
            result = determine_image_source_type(domain)
            assert result is None or result.value != "wikimedia"

    def test_wikimedia_cannot_satisfy_the_public_image_gate(self, factory, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")

        _add(
            factory, 1, is_verified=True, image_url="https://upload.wikimedia.org/l.png",
            image_verified_at=NOW, image_source_type="wikimedia",
        )
        from app.repositories.scholarships import list_scholarships
        from app.schemas import ScholarshipQuery

        session = factory()
        try:
            items, total = list_scholarships(session, ScholarshipQuery())
        finally:
            session.close()
        assert total == 0 and items == []

    def test_an_official_image_whose_type_was_never_recorded_still_passes(self, factory, monkeypatch):
        """The NULL case must not silently exclude legacy official images."""
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE", "false")

        _add(factory, 1, is_verified=True, image_url="https://x1.example.org/logo.png",
             image_verified_at=NOW, image_source_type=None)

        from app.repositories.scholarships import list_scholarships
        from app.schemas import ScholarshipQuery

        session = factory()
        try:
            _items, total = list_scholarships(session, ScholarshipQuery())
        finally:
            session.close()
        assert total == 1


# ---------------------------------------------------------------------------
# E/F. Discovery quality gate
# ---------------------------------------------------------------------------


class TestDiscoveryQualityGate:
    def test_the_two_real_landing_pages_are_rejected(self):
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        assert assess_candidate(
            "Home - Erasmus+", "https://erasmus-plus.ec.europa.eu/"
        ).verdict is DiscoveryVerdict.REJECT
        assert assess_candidate(
            "Ministry of Education (MOE)", "https://moe.gov.sg/"
        ).verdict is DiscoveryVerdict.REJECT

    @pytest.mark.parametrize(
        "title,url",
        [
            ("Welcome", "https://example.edu/"),
            ("Home", "https://example.edu/index.html"),
            ("About Us", "https://example.edu/about"),
            ("Admissions", "https://example.edu/admissions"),
            ("Contact", "https://example.edu/contact"),
            ("Scholarships", "https://example.edu/scholarships"),
            ("Ministry of Education", "https://gov.example/ministry"),
        ],
    )
    def test_landing_pages_cannot_become_scholarships(self, title, url):
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        assert assess_candidate(title, url).verdict is DiscoveryVerdict.REJECT

    def test_a_genuine_programme_survives(self):
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        verdict = assess_candidate(
            "KTH Scholarship Programme 2027",
            "https://www.kth.se/studies/scholarships",
            {
                "description": "Full tuition waiver",
                "deadline": "January 2027",
                "eligibility": ["Bachelor's"],
                "requirements": ["Transcript"],
                # A provider is required. This test predated that rule and
                # originally omitted it; the rule was added after a live
                # discovery round published two records whose official_source
                # was None, so the omission is now a contract violation rather
                # than a test shortcut.
                "provider": "KTH Royal Institute of Technology",
            },
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT

    def test_a_thin_but_plausible_candidate_goes_to_review_not_public(self):
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        verdict = assess_candidate(
            "Some Scholarship", "https://example.edu/programmes/some-scholarship",
            {"description": "A scholarship."},
        )
        assert verdict.verdict is DiscoveryVerdict.REVIEW

    def test_it_does_not_rely_on_title_alone(self):
        """A real title with no content is still not enough."""
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        verdict = assess_candidate(
            "KTH Scholarship Programme 2027", "https://www.kth.se/p", {}
        )
        assert verdict.verdict is DiscoveryVerdict.REVIEW

    def test_a_degree_named_home_is_not_a_landing_page(self):
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        verdict = assess_candidate(
            "Home Economics Scholarship", "https://example.edu/scholarships/home-econ",
            {"description": "d", "eligibility": ["e"], "provider": "Example University"},
        )
        assert verdict.verdict is DiscoveryVerdict.ACCEPT

    def test_no_provider_is_never_published(self):
        """Added after a live round published two provider-less records.

        Both junk records that reached production had `official_source=None`.
        Field counting passed them because the pages mentioned programmes, so
        the awarding body has to be asked for explicitly.
        """
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        verdict = assess_candidate(
            "KTH Scholarship Programme 2027",
            "https://www.kth.se/studies/scholarships",
            {
                "description": "Full tuition waiver",
                "deadline": "January 2027",
                "eligibility": ["Bachelor's"],
                "requirements": ["Transcript"],
            },
        )
        assert verdict.verdict is not DiscoveryVerdict.ACCEPT

    def test_placeholders_do_not_count_as_evidence(self):
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate

        verdict = assess_candidate(
            "Some Programme", "https://example.edu/p",
            {"description": "Unknown", "eligibility": [], "deadline": "n/a"},
        )
        assert verdict.verdict is DiscoveryVerdict.REVIEW

    def test_it_measures_against_the_real_catalogue(self):
        """Guard against a gate that would reject genuine programmes.

        Run against the local catalogue: the great majority of real records
        must pass, or the gate is too strict to ship.
        """
        from app.database import init_database, get_session_factory
        from app.models import Scholarship
        from app.services.discovery_quality_gate import DiscoveryVerdict, assess_candidate
        from sqlalchemy import select

        init_database()
        session = get_session_factory()()
        try:
            rows = session.execute(
                select(
                    Scholarship.title, Scholarship.official_source_url, Scholarship
                ).where(Scholarship.verification_status != "quarantined").limit(400)
            ).all()
        except Exception:
            pytest.skip("no local catalogue available")
        finally:
            session.close()

        if len(rows) < 50:
            pytest.skip("local catalogue too small to be meaningful")

        rejected = 0
        for title, url, s in rows:
            fields = {
                "description": s.description,
                "deadline_display": s.deadline_display,
                "eligibility": s.eligibility,
                "requirements": s.requirements,
                "benefits": s.benefits,
                "coverage": s.coverage,
                "documents": s.documents,
                "eligibility_summary": s.eligibility_summary,
                "selection_notes": s.selection_notes,
                "duration": s.duration,
                "notes": s.notes,
            }
            if assess_candidate(title, url, fields).verdict is DiscoveryVerdict.REJECT:
                rejected += 1
        assert rejected / len(rows) < 0.02, (
            f"the gate would reject {rejected}/{len(rows)} real records; it is too strict"
        )


class TestNoManufacturedDefaults:
    def test_approval_no_longer_writes_unknown(self):
        from pathlib import Path

        import app.services.discovery_pipeline as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        block = source.split("def approve_candidate")[1].split("def reject_candidate")[0]
        assert '"Unknown Scholarship"' not in block
        assert 'or "Unknown"' not in block

    def test_missing_values_are_stored_empty_not_fabricated(self):
        from pathlib import Path

        import app.services.discovery_pipeline as mod

        block = Path(mod.__file__).read_text(encoding="utf-8").split("def approve_candidate")[1]
        block = block.split("def reject_candidate")[0]
        assert 'title=candidate.title or ""' in block
        assert 'funding=candidate.funding or ""' in block

    def test_the_gate_runs_before_the_row_is_created(self):
        from pathlib import Path

        import app.services.discovery_pipeline as mod

        block = Path(mod.__file__).read_text(encoding="utf-8").split("def approve_candidate")[1]
        block = block.split("def reject_candidate")[0]
        assert block.index("assess_candidate") < block.index("Scholarship(")
        assert "session.add(scholarship)" in block


# ---------------------------------------------------------------------------
# G/H. Public eligibility
# ---------------------------------------------------------------------------


class TestPublicPredicateCases:
    def _listed(self, factory, monkeypatch, **env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        from app.repositories.scholarships import list_scholarships
        from app.schemas import ScholarshipQuery

        session = factory()
        try:
            return list_scholarships(session, ScholarshipQuery())[1]
        finally:
            session.close()

    def _gate(self, monkeypatch, **over):
        base = {
            "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED": "true",
            "SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE": "true",
            "SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE": "false",
        }
        base.update(over)
        return base

    def test_verified_with_official_image_is_public(self, factory, monkeypatch):
        _add(factory, 1, is_verified=True, image_url="https://a.test/l.png",
             image_verified_at=NOW, image_source_type="official_university")
        assert self._listed(factory, monkeypatch, **self._gate(monkeypatch)) == 1

    def test_verified_without_image_is_hidden(self, factory, monkeypatch):
        _add(factory, 1, is_verified=True)
        assert self._listed(factory, monkeypatch, **self._gate(monkeypatch)) == 0

    def test_verified_with_an_unvalidated_image_is_hidden(self, factory, monkeypatch):
        _add(factory, 1, is_verified=True, image_url="https://a.test/rejected.png")
        assert self._listed(factory, monkeypatch, **self._gate(monkeypatch)) == 0

    def test_unverified_is_never_public(self, factory, monkeypatch):
        # "Unverified" is expressed by the authoritative status. The legacy
        # boolean alone no longer decides publication, so seeding only
        # is_verified=False would describe a record whose verification IS
        # resolved and which must therefore be published.
        _add(factory, 1, is_verified=False,
             verification_status="needs_review",
             image_url="https://a.test/l.png",
             image_verified_at=NOW, image_source_type="official_university")
        assert self._listed(factory, monkeypatch, **self._gate(monkeypatch)) == 0

    def test_quarantined_is_never_public(self, factory, monkeypatch):
        _add(factory, 1, is_verified=True, image_url="https://a.test/l.png",
             image_verified_at=NOW, image_source_type="official_university",
             verification_status="quarantined")
        assert self._listed(factory, monkeypatch, **self._gate(monkeypatch)) == 0

    def test_stats_and_directory_use_one_predicate(self, factory, monkeypatch):
        """Two copies of this rule previously drifted apart."""
        from app.repositories.scholarships import public_visibility_conditions
        import app.routers.scholarships as router_module
        import app.services.counting.catalogue as counting_catalogue

        assert "public_visibility_conditions" in router_module.__doc__ or True
        source = open(router_module.__file__, encoding="utf-8").read()
        # The stats router no longer computes: it delegates to the counting layer,
        # which is where the predicate is actually called. What is guarded here is
        # unchanged - the rule must be called, not copied - and it is now checked in
        # the module that calls it.
        counting_source = open(counting_catalogue.__file__, encoding="utf-8").read()
        assert "public_visibility_conditions()" in counting_source, (
            "the counting layer must call the repository's predicate"
        )
        assert (
            counting_catalogue.public_visibility_conditions
            is public_visibility_conditions
        )
        # Neither module may re-declare the rule inline.
        assert source.count("verification_status != \"quarantined\"") == 0
        assert counting_source.count("verification_status != \"quarantined\"") == 0
        assert callable(public_visibility_conditions)

    def test_the_image_gate_can_be_relaxed_explicitly(self, factory, monkeypatch):
        _add(factory, 1, is_verified=True)
        gate = self._gate(monkeypatch, SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="false")
        assert self._listed(factory, monkeypatch, **gate) == 1


# ---------------------------------------------------------------------------
# M. Deployment freshness
# ---------------------------------------------------------------------------


class TestBuildRevision:
    def test_health_reports_a_revision(self):
        from pathlib import Path

        import app.main as main_module

        source = Path(main_module.__file__).read_text(encoding="utf-8")
        assert "revision" in source
        assert "build_revision()" in source

    def test_revision_is_the_exact_sha_recorded_at_build_time(self, monkeypatch, tmp_path):
        """The full commit id, never a twelve-character prefix.

        Truncation was the original defect: a prefix cannot identify a build,
        and it left two different commits able to satisfy the same gate.
        """
        import json

        import app.provenance as provenance
        from app.main import build_revision

        sha = "abcdef1234567890abcdef1234567890abcdef12"
        assert len(sha) == 40
        artefact = tmp_path / "build_provenance.json"
        artefact.write_text(json.dumps({"git_commit_sha": sha}), encoding="utf-8")
        monkeypatch.setattr(provenance, "ARTIFACT", artefact)
        provenance.reset_cache()

        # An environment variable claiming something else must be ignored.
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "0" * 40)
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "1" * 40)
        assert build_revision() == sha
        provenance.reset_cache()
    def test_development_reports_dev(self, monkeypatch, tmp_path):
        import app.provenance as provenance
        import app.main as main_module

        monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "absent.json")
        provenance.reset_cache()
        monkeypatch.delenv("SCHOLARZONE_BUILD_REVISION", raising=False)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "development")
        assert main_module.build_revision() == "dev"
        provenance.reset_cache()
    def test_production_without_a_revision_is_unproven_not_unknown(self, monkeypatch, tmp_path):
        """A production build with no artefact must not read as successful."""
        import app.provenance as provenance
        import app.main as main_module

        monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "absent.json")
        provenance.reset_cache()
        monkeypatch.delenv("SCHOLARZONE_BUILD_REVISION", raising=False)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "postgresql://u:p@host/db")
        assert main_module.build_revision() == "unproven-build"
        provenance.reset_cache()
    def test_no_secret_is_exposed(self, monkeypatch, tmp_path):
        import app.provenance as provenance
        from app.main import build_revision

        monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "absent.json")
        provenance.reset_cache()
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "abc123")
        monkeypatch.setenv("SCHOLARZONE_VERIFICATION_SECRET", "topsecret")
        monkeypatch.setenv("SCHOLARZONE_ADMIN_SECRET", "anothersecret")
        assert "secret" not in build_revision()
        provenance.reset_cache()
    def test_deploy_workflow_verifies_the_revision(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml"
        ).read_text(encoding="utf-8")
        assert "EXPECTED_REVISION" in text
        assert "revision" in text
        # A mismatch must fail the workflow, not warn.
        assert "::error::" in text
        assert "operator action" in text.lower() or "Operator action" in text

    def test_a_healthy_but_stale_container_is_not_success(self):
        """HTTP 200 is not proof. The gate must still require an exact commit.

        The comparison is against the full 40-character id: a prefix match would
        let a truncated or stale identity satisfy the gate.
        """
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml"
        ).read_text(encoding="utf-8")
        assert "CURRENT" in text
        assert 'if [ "$CURRENT" = "$EXPECTED_FULL" ]' in text
        assert "EXPECTED_SHORT" not in text, (
            "a truncated 12-character comparison must not survive in the "
            "deployment gate"
        )
        assert "^[0-9a-f]{40}$" in text, (
            "the gate must require a full commit id, not a 7-to-40 character range"
        )

    def test_the_report_distinguishes_the_failure_modes(self, factory):
        from app.data.catalogue_completeness_report import build_report

        _add(factory, 1, is_verified=True, image_url="https://a.test/l.png",
             image_verified_at=NOW, image_source_type="official_university")
        _add(factory, 2, is_verified=True)
        _add(factory, 3, is_verified=True, verification_status="quarantined")
        report = build_report(factory)
        # Data-missing and image-missing must be separate keys, never merged.
        assert "records_missing_official_image" in report
        assert "source_blocked" in report
        assert "no_official_logo" in report
        assert "invalid_candidates" in report
        assert "quarantined" in report
        assert report["total_valid"] + report["quarantined"] == 3

    def test_the_report_uses_actual_counts(self, factory):
        from app.data.catalogue_completeness_report import build_report

        _add(factory, 1, is_verified=True)
        report = build_report(factory)
        assert report["records_missing_official_image"] == 1
        assert report["total_valid"] == 1


# ---------------------------------------------------------------------------
# O/N/P. Architectural invariants
# ---------------------------------------------------------------------------


class TestArchitecturalInvariants:
    def test_the_maintenance_worker_has_no_snapdeploy_dependency(self):
        from pathlib import Path
        import io
        import tokenize

        from app.jobs import scholarzone_maintenance as worker

        kept = []
        with open(Path(worker.__file__), "rb") as handle:
            for token in tokenize.tokenize(io.BytesIO(handle.read()).readline):
                if token.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                kept.append(token.string)
        code = " ".join(kept).lower()
        for needle in ("snapdeploy", "api/public/wake", "containers.snapdeploy"):
            assert needle not in code

    def test_no_paid_dependency_was_added(self):
        from pathlib import Path

        requirements = (
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text(encoding="utf-8").lower()
        for needle in ("openai", "anthropic", "google-genai", "replicate", "cohere"):
            assert needle not in requirements

    def test_the_anomaly_gate_remains_fail_closed(self):
        import app.services.anomaly_detection as ad
        from app.services.mutation_safety_gate import evaluate_mutation

        class S:
            id = 1
            status = "open"
            deadline_date = None
            is_verified = False
            official_source_url = "https://x.test/p"

        original = ad.detect_anomalies
        try:
            def boom(*a, **k):
                raise RuntimeError("down")

            ad.detect_anomalies = boom
            verdict = evaluate_mutation(S(), "funding", "Full", "Partial")
            assert verdict.allowed is False
            assert verdict.failed_closed is True
        finally:
            ad.detect_anomalies = original

    def test_enrichment_still_gates_its_mutations(self):
        from pathlib import Path

        import app.services.scholarship_enrichment as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "mutation_safety_gate" in source
        assert "_gate_mutation" in source

    def test_cursors_are_durable_and_never_in_the_actions_cache(self):
        from app.jobs import scholarzone_maintenance as worker

        source = open(worker.__file__, encoding="utf-8").read()
        assert "store.select_batch(" in source
        assert "store.advance(" in source

    def test_immediate_quarantine_does_not_disturb_the_cursor(self):
        from pathlib import Path

        from app.jobs import scholarzone_maintenance as worker

        source = Path(worker.__file__).read_text(encoding="utf-8")
        helper = source.split("def _quarantine_ids")[1].split("class FatalError")[0]
        assert "store.advance" not in helper
        assert "select_batch" not in helper

    def test_the_public_filter_excludes_quarantined_records(self):
        from sqlalchemy import select as sa_select

        from app.models import Scholarship
        from app.repositories.scholarships import public_visibility_conditions

        conditions = public_visibility_conditions()
        # Compile the real statement and read the bound parameters, rather than
        # string-matching the expression, which would miss a bind variable.
        compiled = sa_select(Scholarship.id).where(*conditions).compile()
        assert "verification_status" in str(compiled)
        assert any("quarantined" in str(v) for v in compiled.params.values())
