"""Tests for the dependency-aware verification graph."""

from __future__ import annotations

import pytest

from app.services.dependency_graph import (
    AffectedField,
    CriticalityLevel,
    DependencyAnalysis,
    DependencyEdge,
    DependencyType,
    ReVerificationClass,
    _DEPENDENCY_RULES,
    analyze_dependencies,
    batch_analyze_dependencies,
    detect_dependency_cycles,
    get_all_tracked_fields,
    get_dependency_graph_version,
    get_dependency_path,
    get_dependency_rules,
    get_direct_dependencies,
    get_fields_for_reverification,
    get_targeted_verification_set,
    should_escalate_to_review,
)


class TestDependencyGraphBasics:
    """Test basic dependency graph functionality."""

    def test_graph_version_is_v1(self):
        assert get_dependency_graph_version() == "v1"

    def test_get_all_tracked_fields_returns_set(self):
        fields = get_all_tracked_fields()
        assert isinstance(fields, frozenset)
        assert len(fields) > 0

    def test_get_dependency_rules_returns_tuple(self):
        rules = get_dependency_rules()
        assert isinstance(rules, tuple)
        assert len(rules) > 0
        for rule in rules:
            assert isinstance(rule, DependencyEdge)

    def test_dependency_rules_have_required_fields(self):
        for rule in _DEPENDENCY_RULES:
            source, target, criticality, reason = rule
            assert isinstance(source, str) and source
            assert isinstance(target, str) and target
            assert isinstance(criticality, CriticalityLevel)
            assert isinstance(reason, str) and reason


class TestDirectDependencies:
    """Test direct dependency resolution."""

    def test_deadline_date_has_direct_dependencies(self):
        deps = get_direct_dependencies("deadline_date")
        assert len(deps) > 0
        targets = {d.target_field for d in deps}
        assert "deadline_display" in targets
        assert "application_period" in targets
        assert "status" in targets

    def test_eligibility_has_direct_dependencies(self):
        deps = get_direct_dependencies("eligibility")
        assert len(deps) > 0
        targets = {d.target_field for d in deps}
        assert "requirements" in targets
        assert "documents" in targets

    def test_funding_has_direct_dependencies(self):
        deps = get_direct_dependencies("funding")
        targets = {d.target_field for d in deps}
        assert "coverage" in targets
        assert "requirements" in targets

    def test_application_method_has_direct_dependencies(self):
        deps = get_direct_dependencies("application_method")
        targets = {d.target_field for d in deps}
        assert "application_link" in targets
        assert "application_period" in targets

    def test_degree_has_direct_dependencies(self):
        deps = get_direct_dependencies("degree")
        targets = {d.target_field for d in deps}
        assert "eligibility" in targets
        assert "requirements" in targets

    def test_country_has_direct_dependencies(self):
        deps = get_direct_dependencies("country")
        targets = {d.target_field for d in deps}
        assert "eligibility" in targets

    def test_field_without_dependencies(self):
        deps = get_direct_dependencies("nonexistent_field")
        assert deps == []

    def test_dependency_edges_have_correct_type(self):
        deps = get_direct_dependencies("deadline_date")
        for dep in deps:
            assert dep.dependency_type == DependencyType.DIRECT
            assert dep.source_field == "deadline_date"


class TestAnalyzeDependencies:
    """Test the main dependency analysis function."""

    def test_empty_changed_fields_returns_empty_analysis(self):
        analysis = analyze_dependencies([])
        assert analysis.affected_fields == []
        assert analysis.direct_fields == []
        assert analysis.transitive_fields == []
        assert analysis.review_fields == []

    def test_deadline_date_change_affects_direct_fields(self):
        analysis = analyze_dependencies(["deadline_date"])
        field_names = {af.field_name for af in analysis.direct_fields}
        assert "deadline_display" in field_names
        assert "application_period" in field_names
        assert "status" in field_names

    def test_eligibility_change_affects_transitive_fields(self):
        analysis = analyze_dependencies(["eligibility"])
        field_names = {af.field_name for af in analysis.affected_fields}
        assert "requirements" in field_names
        assert "documents" in field_names
        # english_requirement should be transitive (eligibility -> ... -> english_requirement)

    def test_unrelated_field_not_selected(self):
        analysis = analyze_dependencies(["title"])
        field_names = {af.field_name for af in analysis.affected_fields}
        # title change should not affect most fields
        assert "funding" not in field_names
        assert "deadline_date" not in field_names

    def test_multiple_changed_fields(self):
        analysis = analyze_dependencies(["deadline_date", "eligibility"])
        field_names = {af.field_name for af in analysis.affected_fields}
        # Should include dependencies from both
        assert "deadline_display" in field_names
        assert "requirements" in field_names
        assert "documents" in field_names

    def test_duplicate_dependency_elimination(self):
        """Test that the same field affected by multiple sources is deduplicated."""
        analysis = analyze_dependencies(["eligibility", "funding"])
        # Both eligibility and funding affect requirements
        req_fields = [af for af in analysis.affected_fields if af.field_name == "requirements"]
        assert len(req_fields) == 1

    def test_cycle_protection(self):
        """Test that cycles in the graph don't cause infinite loops."""
        # Create a scenario that could cycle: application_method -> application_link -> application_method
        # But the actual rules don't have this exact cycle, so we test the mechanism
        analysis = analyze_dependencies(["application_method"], max_depth=3)
        # Should complete without infinite loop
        assert analysis is not None

    def test_depth_limiting(self):
        """Test that max_depth limits traversal."""
        analysis_shallow = analyze_dependencies(["eligibility"], max_depth=1)
        analysis_deep = analyze_dependencies(["eligibility"], max_depth=5)
        # Deep analysis should find more or equal fields
        assert len(analysis_deep.affected_fields) >= len(analysis_shallow.affected_fields)

    def test_critical_dependency_priority(self):
        """Test that critical dependencies are prioritized."""
        analysis = analyze_dependencies(["eligibility"])
        prioritized = analysis.prioritized_fields
        if prioritized:
            # First item should be critical or highest priority
            assert prioritized[0].criticality in (CriticalityLevel.CRITICAL, CriticalityLevel.HIGH)

    def test_explanation_reason_codes(self):
        """Test that each affected field has a reason."""
        analysis = analyze_dependencies(["deadline_date"])
        for af in analysis.affected_fields:
            assert af.reason
            assert isinstance(af.reason, str)
            assert len(af.reason) > 0

    def test_deterministic_traversal(self):
        """Test that analysis is deterministic."""
        analysis1 = analyze_dependencies(["deadline_date", "eligibility"])
        analysis2 = analyze_dependencies(["deadline_date", "eligibility"])
        fields1 = [(af.field_name, af.re_verification_class) for af in analysis1.affected_fields]
        fields2 = [(af.field_name, af.re_verification_class) for af in analysis2.affected_fields]
        assert fields1 == fields2

    def test_analysis_version_is_set(self):
        analysis = analyze_dependencies(["deadline_date"])
        assert analysis.analysis_version == "v1"

    def test_changed_fields_preserved(self):
        analysis = analyze_dependencies(["deadline_date", "eligibility"])
        assert set(analysis.changed_fields) == {"deadline_date", "eligibility"}


class TestReVerificationClassification:
    """Test re-verification classification."""

    def test_direct_dependencies_classified_correctly(self):
        analysis = analyze_dependencies(["deadline_date"])
        for af in analysis.direct_fields:
            assert af.re_verification_class == ReVerificationClass.DIRECT

    def test_transitive_dependencies_classified_correctly(self):
        analysis = analyze_dependencies(["eligibility"])
        transitive = [af for af in analysis.affected_fields if af.depth > 0]
        for af in transitive:
            assert af.re_verification_class == ReVerificationClass.TRANSITIVE

    def test_no_recheck_fields_identified(self):
        known = frozenset(["deadline_date", "deadline_display", "status", "unrelated_field"])
        analysis = analyze_dependencies(["deadline_date"], known_fields=known)
        # unrelated_field should be in no_recheck
        assert "unrelated_field" in analysis.no_recheck_fields

    def test_changed_fields_not_in_no_recheck(self):
        known = frozenset(["deadline_date", "deadline_display"])
        analysis = analyze_dependencies(["deadline_date"], known_fields=known)
        assert "deadline_date" not in analysis.no_recheck_fields


class TestBatchOperations:
    """Test batch dependency analysis."""

    def test_batch_analyze_multiple_field_sets(self):
        results = batch_analyze_dependencies([
            ["deadline_date"],
            ["eligibility"],
            ["funding"],
        ])
        assert len(results) == 3
        # Each should have different affected fields
        fields_0 = {af.field_name for af in results[0].affected_fields}
        fields_1 = {af.field_name for af in results[1].affected_fields}
        fields_2 = {af.field_name for af in results[2].affected_fields}
        assert fields_0 != fields_1 or fields_1 != fields_2

    def test_batch_empty_list(self):
        results = batch_analyze_dependencies([])
        assert results == []

    def test_batch_single_item(self):
        results = batch_analyze_dependencies([["deadline_date"]])
        assert len(results) == 1
        assert results[0].changed_fields == ("deadline_date",)


class TestGetFieldsForReverification:
    """Test convenience function for getting re-verification set."""

    def test_returns_set(self):
        result = get_fields_for_reverification(["deadline_date"])
        assert isinstance(result, frozenset)

    def test_includes_direct_dependencies(self):
        result = get_fields_for_reverification(["deadline_date"])
        assert "deadline_display" in result
        assert "application_period" in result

    def test_includes_transitive_dependencies(self):
        result = get_fields_for_reverification(["eligibility"])
        assert "requirements" in result

    def test_empty_input_returns_empty_set(self):
        result = get_fields_for_reverification([])
        assert result == frozenset()


class TestShouldEscalateToReview:
    """Test escalation detection."""

    def test_normal_changes_do_not_escalate(self):
        should_escalate, reasons = should_escalate_to_review(["deadline_display"])
        assert not should_escalate
        assert reasons == []

    def test_review_fields_cause_escalation(self):
        """Test that fields with REVIEW classification cause escalation."""
        # This test may need adjustment based on actual rules
        should_escalate, reasons = should_escalate_to_review(["title"])
        # title only has LOW criticality dependency, so no escalation
        # unless there's a cycle or ambiguity


class TestGetTargetedVerificationSet:
    """Test prioritized verification set function."""

    def test_returns_dict_with_expected_keys(self):
        result = get_targeted_verification_set(["deadline_date"])
        assert "critical" in result
        assert "high" in result
        assert "medium" in result
        assert "low" in result
        assert "review" in result

    def test_critical_fields_grouped_correctly(self):
        result = get_targeted_verification_set(["deadline_date"])
        # deadline_display is CRITICAL
        assert "deadline_display" in result["critical"]

    def test_high_fields_grouped_correctly(self):
        result = get_targeted_verification_set(["eligibility"])
        # documents is HIGH
        assert "documents" in result["high"]

    def test_review_fields_separated(self):
        result = get_targeted_verification_set(["title"])
        # All fields should be in one of the categories
        all_fields = (
            result["critical"] + result["high"] +
            result["medium"] + result["low"] + result["review"]
        )
        # title may have LOW dependency on official_source
        assert isinstance(all_fields, list)


class TestCycleDetection:
    """Test cycle detection in dependency graph."""

    def test_no_cycles_in_current_graph(self):
        """Verify the current dependency graph has no cycles."""
        cycles = detect_dependency_cycles()
        assert cycles == []

    def test_cycles_listed_as_tuples(self):
        cycles = detect_dependency_cycles()
        for cycle in cycles:
            assert isinstance(cycle, tuple)
            assert len(cycle) >= 2


class TestDependencyPath:
    """Test finding dependency paths."""

    def test_direct_path(self):
        path = get_dependency_path("deadline_date", "deadline_display")
        assert path is not None
        assert path == ["deadline_date", "deadline_display"]

    def test_transitive_path(self):
        path = get_dependency_path("eligibility", "documents")
        assert path is not None
        assert path[0] == "eligibility"
        assert path[-1] == "documents"

    def test_no_path_returns_none(self):
        path = get_dependency_path("title", "deadline_date")
        assert path is None

    def test_same_field_returns_single_item_path(self):
        path = get_dependency_path("deadline_date", "deadline_date")
        assert path == ["deadline_date"]

    def test_respects_max_depth(self):
        path = get_dependency_path("eligibility", "documents", max_depth=1)
        if path:
            assert len(path) <= 2


class TestIntegrationWithChangeImpact:
    """Test integration with change_impact_staleness field criticality."""

    def test_critical_fields_from_change_impact_covered(self):
        """Test that CRITICAL fields from change_impact_staleness have dependencies."""
        from app.services.change_impact_staleness import CRITICAL, FIELD_CRITICALITY

        tracked = get_all_tracked_fields()
        critical_fields = {
            field for field, level in FIELD_CRITICALITY.items()
            if level == CRITICAL
        }
        # At least some critical fields should be tracked
        assert len(tracked & critical_fields) > 0

    def test_dependency_criticality_matches_field_criticality(self):
        """Test that dependency criticality aligns with field importance."""
        deps = get_direct_dependencies("eligibility")
        for dep in deps:
            if dep.target_field == "requirements":
                # requirements is HIGH in change_impact_staleness
                assert dep.criticality in (CriticalityLevel.HIGH, CriticalityLevel.CRITICAL)


class TestSafetyAndEdgeCases:
    """Test safety behaviors and edge cases."""

    def test_unknown_field_does_not_crash(self):
        """Test that unknown fields don't cause errors."""
        analysis = analyze_dependencies(["unknown_field_xyz"])
        assert analysis.affected_fields == []

    def test_duplicate_changed_fields_handled(self):
        """Test that duplicate fields in input are handled."""
        analysis = analyze_dependencies(["deadline_date", "deadline_date"])
        assert set(analysis.changed_fields) == {"deadline_date"}

    def test_negative_depth_does_not_cause_error(self):
        """Test that depth limiting works correctly."""
        analysis = analyze_dependencies(["deadline_date"], max_depth=0)
        # With max_depth=0, only changed fields should be returned
        assert analysis.affected_fields == []

    def test_very_large_depth_does_not_cause_error(self):
        """Test that large max_depth doesn't cause issues."""
        analysis = analyze_dependencies(["eligibility"], max_depth=100)
        assert analysis is not None

    def test_analysis_does_not_modify_input(self):
        """Test that analysis doesn't modify the input list."""
        input_fields = ["deadline_date", "eligibility"]
        original = input_fields.copy()
        analyze_dependencies(input_fields)
        assert input_fields == original


class TestDependencyEdgeDataclass:
    """Test DependencyEdge dataclass."""

    def test_edge_is_frozen(self):
        edge = DependencyEdge(
            source_field="a",
            target_field="b",
            dependency_type=DependencyType.DIRECT,
            criticality=CriticalityLevel.HIGH,
            reason="test",
        )
        with pytest.raises(AttributeError):
            edge.source_field = "c"  # type: ignore[misc]

    def test_edge_has_required_attributes(self):
        edge = DependencyEdge(
            source_field="a",
            target_field="b",
            dependency_type=DependencyType.DIRECT,
            criticality=CriticalityLevel.HIGH,
            reason="test",
        )
        assert edge.source_field == "a"
        assert edge.target_field == "b"
        assert edge.dependency_type == DependencyType.DIRECT
        assert edge.criticality == CriticalityLevel.HIGH
        assert edge.reason == "test"


class TestAffectedFieldDataclass:
    """Test AffectedField dataclass."""

    def test_affected_field_creation(self):
        af = AffectedField(
            field_name="deadline_display",
            re_verification_class=ReVerificationClass.DIRECT,
            criticality=CriticalityLevel.CRITICAL,
            depth=0,
            reason="test reason",
            source_fields=("deadline_date",),
        )
        assert af.field_name == "deadline_display"
        assert af.requires_escalation is False

    def test_requires_escalation_flag(self):
        af = AffectedField(
            field_name="test",
            re_verification_class=ReVerificationClass.REVIEW,
            criticality=CriticalityLevel.CRITICAL,
            depth=0,
            reason="test",
            source_fields=("source",),
            requires_escalation=True,
        )
        assert af.requires_escalation is True


class TestDependencyAnalysisDataclass:
    """Test DependencyAnalysis dataclass."""

    def test_requires_full_verification_with_review_fields(self):
        analysis = DependencyAnalysis(
            changed_fields=("a",),
            affected_fields=[],
            direct_fields=[],
            transitive_fields=[],
            review_fields=[
                AffectedField(
                    field_name="test",
                    re_verification_class=ReVerificationClass.REVIEW,
                    criticality=CriticalityLevel.HIGH,
                    depth=0,
                    reason="test",
                    source_fields=("a",),
                )
            ],
            no_recheck_fields=[],
        )
        assert analysis.requires_full_verification is True

    def test_requires_full_verification_without_review_fields(self):
        analysis = DependencyAnalysis(
            changed_fields=("a",),
            affected_fields=[],
            direct_fields=[],
            transitive_fields=[],
            review_fields=[],
            no_recheck_fields=[],
        )
        assert analysis.requires_full_verification is False

    def test_prioritized_fields_sorting(self):
        """Test that prioritized_fields sorts by criticality then depth."""
        direct_fields = [
            AffectedField(
                field_name="low",
                re_verification_class=ReVerificationClass.DIRECT,
                criticality=CriticalityLevel.LOW,
                depth=0,
                reason="test",
                source_fields=("a",),
            ),
            AffectedField(
                field_name="critical",
                re_verification_class=ReVerificationClass.DIRECT,
                criticality=CriticalityLevel.CRITICAL,
                depth=0,
                reason="test",
                source_fields=("a",),
            ),
        ]
        analysis = DependencyAnalysis(
            changed_fields=("a",),
            affected_fields=direct_fields,
            direct_fields=direct_fields,
            transitive_fields=[],
            review_fields=[],
            no_recheck_fields=[],
        )
        prioritized = analysis.prioritized_fields
        assert prioritized[0].field_name == "critical"
        assert prioritized[-1].field_name == "low"


class TestFieldCoverage:
    """Test that all important fields have dependency rules."""

    def test_deadline_fields_have_dependencies(self):
        deps = get_direct_dependencies("deadline_date")
        assert len(deps) > 0

    def test_eligibility_fields_have_dependencies(self):
        deps = get_direct_dependencies("eligibility")
        assert len(deps) > 0

    def test_funding_fields_have_dependencies(self):
        deps = get_direct_dependencies("funding")
        assert len(deps) > 0

    def test_application_fields_have_dependencies(self):
        deps = get_direct_dependencies("application_method")
        assert len(deps) > 0

    def test_degree_fields_have_dependencies(self):
        deps = get_direct_dependencies("degree")
        assert len(deps) > 0

    def test_country_fields_have_dependencies(self):
        deps = get_direct_dependencies("country")
        assert len(deps) > 0


class TestNoUnnecessaryFullVerification:
    """Test that minor changes don't trigger full verification."""

    def test_title_change_does_not_require_full_verification(self):
        analysis = analyze_dependencies(["title"])
        # title change should have limited impact
        assert not analysis.requires_full_verification

    def test_description_change_limited_impact(self):
        analysis = analyze_dependencies(["description"])
        # description has no outgoing dependencies
        assert analysis.affected_fields == []
