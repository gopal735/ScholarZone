"""Compatibility alias for Study Planner runtime readiness."""

from app.study_planner_readiness import *  # noqa: F401,F403
from app.study_planner_readiness import (
    REQUIRED_STUDY_PLANNER_TABLES,
    REQUIRED_STUDY_PLANNER_COLUMNS,
    StudyPlannerSchemaNotReadyError,
    is_study_planner_ready,
    ensure_study_planner_ready,
    study_planner_ready,
)

__all__ = [
    "REQUIRED_STUDY_PLANNER_TABLES",
    "REQUIRED_STUDY_PLANNER_COLUMNS",
    "StudyPlannerSchemaNotReadyError",
    "is_study_planner_ready",
    "ensure_study_planner_ready",
    "study_planner_ready",
]
