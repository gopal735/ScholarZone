"""Runtime readiness guard for the Dream AI Mentor 2.0 Study Planner.

The Study Planner is an optional feature backed by its own tables.  A deployed
application must never issue Study Planner queries against a database that does
not contain the required schema.  This module provides a FastAPI dependency that
verifies the schema on every request, failing closed with HTTP 503 when the
tables or required columns are absent or inaccessible.

The guard is deliberately *not* the cached ``_db_ready`` flag from
``app.main``: that flag is set once during startup on a background thread and
can be stale.  Each request inspects the database it is actually using, so a
schema that becomes valid after deployment is honoured without a restart and a
missing schema can never be reported as ready.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from .database import get_db

logger = logging.getLogger(__name__)

# Tables the Study Planner requires.
REQUIRED_STUDY_PLANNER_TABLES: frozenset[str] = frozenset(
    {"study_plans", "study_plan_tasks"}
)

# Minimum columns required by the active ORM and service code.  Table existence
# alone is not sufficient: a partially migrated table must also be rejected.
REQUIRED_STUDY_PLANNER_COLUMNS: dict[str, frozenset[str]] = {
    "study_plans": frozenset(
        {"id", "user_id", "title", "status", "version"}
    ),
    "study_plan_tasks": frozenset(
        {"id", "plan_id", "title", "status", "version", "related_scholarship_id"}
    ),
}


class StudyPlannerSchemaNotReadyError(Exception):
    """Raised when the Study Planner schema is absent or incomplete."""


def _bind(db: Any) -> Any:
    """Return the SQLAlchemy bind (engine/connection) for a session or engine."""
    getter = getattr(db, "get_bind", None)
    if callable(getter):
        try:
            bind = getter()
            if bind is not None:
                return bind
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(db, "bind") and db.bind is not None:
        return db.bind
    return db


def _inspect_schema(db: Any) -> None:
    """Raise ``StudyPlannerSchemaNotReadyError`` if the schema is unusable."""
    bind = _bind(db)
    try:
        inspector = sa_inspect(bind)
        tables = set(inspector.get_table_names())
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Study Planner readiness inspection failed: %s", type(exc).__name__)
        raise StudyPlannerSchemaNotReadyError("database") from exc

    if not REQUIRED_STUDY_PLANNER_TABLES.issubset(tables):
        raise StudyPlannerSchemaNotReadyError("study_plans")

    for table, required in REQUIRED_STUDY_PLANNER_COLUMNS.items():
        try:
            actual = {column["name"] for column in inspector.get_columns(table)}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Study Planner column inspection failed: %s", type(exc).__name__)
            raise StudyPlannerSchemaNotReadyError(table) from exc
        if not required.issubset(actual):
            raise StudyPlannerSchemaNotReadyError(table)


def is_study_planner_ready(db: Any) -> bool:
    """Return ``True`` when the Study Planner schema is usable."""
    try:
        _inspect_schema(db)
    except StudyPlannerSchemaNotReadyError:
        return False
    return True


def ensure_study_planner_ready(db: Any) -> None:
    """Raise ``StudyPlannerSchemaNotReadyError`` unless the schema is usable."""
    _inspect_schema(db)


def study_planner_ready(db: Session = Depends(get_db)) -> None:
    """FastAPI dependency enforcing Study Planner schema readiness."""
    try:
        _inspect_schema(db)
    except StudyPlannerSchemaNotReadyError as exc:
        logger.info("Study Planner request rejected: schema not ready (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Study planner is not available.",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Study Planner readiness check failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Study planner is not available.",
        ) from exc


__all__ = [
    "REQUIRED_STUDY_PLANNER_TABLES",
    "REQUIRED_STUDY_PLANNER_COLUMNS",
    "StudyPlannerSchemaNotReadyError",
    "is_study_planner_ready",
    "ensure_study_planner_ready",
    "study_planner_ready",
]
