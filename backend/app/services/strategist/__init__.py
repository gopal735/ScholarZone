"""Study-to-Career Strategist service (pure composition over the corpus)."""

from .service import (
    CRITERIA,
    MAX_COMPARE_COUNTRIES,
    ValidationError,
    budget_interpretation,
    coverage_matrix,
    essential_criteria,
    funding_scenario,
    plan,
    pathway_timeline,
    subject_catalog,
)
from .subjects import SUBJECTS, Subject, get_subject, subject_keys

__all__ = [
    "CRITERIA",
    "MAX_COMPARE_COUNTRIES",
    "SUBJECTS",
    "Subject",
    "ValidationError",
    "budget_interpretation",
    "coverage_matrix",
    "essential_criteria",
    "funding_scenario",
    "get_subject",
    "plan",
    "pathway_timeline",
    "subject_catalog",
    "subject_keys",
]
