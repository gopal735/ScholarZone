"""Study planner service for Dream AI Mentor 2.0.

Provides authenticated CRUD for user-owned study plans and tasks. The system
never silently overwrites user edits. Completion/reopen are explicit actions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ...models import StudyPlan, StudyPlanTask, User
from ...schemas_study_planner import (
    StudyPlanCreate,
    StudyPlanTaskCreate,
    StudyPlanTaskUpdate,
    StudyPlanUpdate,
)


class StaleWriteError(Exception):
    """Raised when an update is based on a stale version."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


MAX_TASKS_PER_PLAN = 100


def list_plans(db: Session, user: User) -> list[StudyPlan]:
    stmt = (
        select(StudyPlan)
        .where(StudyPlan.user_id == user.id, StudyPlan.status != "deleted")
        .order_by(StudyPlan.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_plan(db: Session, user: User, plan_id: int) -> StudyPlan | None:
    stmt = select(StudyPlan).where(
        StudyPlan.id == plan_id,
        StudyPlan.user_id == user.id,
        StudyPlan.status != "deleted",
    )
    return db.execute(stmt).scalar_one_or_none()


def create_plan(db: Session, user: User, payload: StudyPlanCreate) -> StudyPlan:
    plan = StudyPlan(
        user_id=user.id,
        title=payload.title,
        goal=payload.goal,
        scholarship_id=payload.scholarship_id,
        status="active",
    )
    if len(payload.tasks) > MAX_TASKS_PER_PLAN:
        raise ValueError("too_many_tasks")
    db.add(plan)
    db.flush()
    for idx, task in enumerate(payload.tasks):
        t = StudyPlanTask(
            plan_id=plan.id,
            title=task.title,
            description=task.description,
            priority=task.priority,
            due_date=task.due_date,
            related_scholarship_id=task.related_scholarship_id,
            rationale=task.rationale,
            position=idx,
            status="open",
        )
        db.add(t)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, user: User, plan_id: int, payload: StudyPlanUpdate) -> StudyPlan | None:
    plan = get_plan(db, user, plan_id)
    if plan is None:
        return None
    if payload.version != plan.version:
        raise StaleWriteError("stale_plan_version")
    values: dict = {}
    if payload.title is not None:
        values["title"] = payload.title
    if payload.goal is not None:
        values["goal"] = payload.goal
    if payload.status is not None:
        values["status"] = payload.status
    values["version"] = StudyPlan.version + 1
    values["updated_at"] = _now()
    result = db.execute(
        update(StudyPlan)
        .where(
            StudyPlan.id == plan_id,
            StudyPlan.user_id == user.id,
            StudyPlan.status != "deleted",
            StudyPlan.version == payload.version,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.rollback()
        raise StaleWriteError("stale_plan_version")
    db.commit()
    return get_plan(db, user, plan_id)


def delete_plan(db: Session, user: User, plan_id: int) -> bool:
    plan = get_plan(db, user, plan_id)
    if plan is None:
        return False
    result = db.execute(
        update(StudyPlan)
        .where(
            StudyPlan.id == plan_id,
            StudyPlan.user_id == user.id,
            StudyPlan.status != "deleted",
        )
        .values(status="deleted", version=StudyPlan.version + 1, updated_at=_now())
    )
    db.commit()
    return result.rowcount == 1


def add_task(db: Session, user: User, plan_id: int, payload: StudyPlanTaskCreate) -> StudyPlanTask | None:
    plan_stmt = select(StudyPlan).where(
        StudyPlan.id == plan_id,
        StudyPlan.user_id == user.id,
        StudyPlan.status != "deleted",
    ).with_for_update()
    plan = db.execute(plan_stmt).scalar_one_or_none()
    if plan is None:
        return None
    stmt = select(StudyPlanTask).where(StudyPlanTask.plan_id == plan.id)
    tasks = list(db.execute(stmt).scalars().all())
    if len(tasks) >= MAX_TASKS_PER_PLAN:
        raise ValueError("too_many_tasks")
    next_pos = (max((t.position for t in tasks), default=-1) + 1)
    t = StudyPlanTask(
        plan_id=plan.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        related_scholarship_id=payload.related_scholarship_id,
        rationale=payload.rationale,
        position=next_pos,
        status="open",
    )
    db.add(t)
    plan.updated_at = _now()
    db.commit()
    db.refresh(t)
    return t


def get_task(db: Session, user: User, task_id: int) -> StudyPlanTask | None:
    t = db.get(StudyPlanTask, task_id)
    if t is None:
        return None
    stmt = select(StudyPlan).where(
        StudyPlan.id == t.plan_id,
        StudyPlan.user_id == user.id,
        StudyPlan.status != "deleted",
    )
    plan = db.execute(stmt).scalar_one_or_none()
    if plan is None:
        return None
    return t


def update_task(db: Session, user: User, task_id: int, payload: StudyPlanTaskUpdate) -> StudyPlanTask | None:
    t = get_task(db, user, task_id)
    if t is None:
        return None
    if payload.version != t.version:
        raise StaleWriteError("stale_task_version")
    values: dict = {}
    if payload.title is not None:
        values["title"] = payload.title
    if payload.description is not None:
        values["description"] = payload.description
    if payload.priority is not None:
        values["priority"] = payload.priority
    if "due_date" in payload.model_fields_set:
        values["due_date"] = payload.due_date
    if payload.status is not None:
        if payload.status == "completed":
            values["status"] = "completed"
            values["completed_at"] = _now()
        elif payload.status in ("open", "reopened"):
            values["status"] = payload.status
            values["completed_at"] = None
        else:
            return None
    if payload.rationale is not None:
        values["rationale"] = payload.rationale
    values["version"] = StudyPlanTask.version + 1
    values["updated_at"] = _now()
    result = db.execute(
        update(StudyPlanTask)
        .where(
            StudyPlanTask.id == task_id,
            StudyPlanTask.version == payload.version,
            StudyPlanTask.plan_id.in_(
                select(StudyPlan.id).where(
                    StudyPlan.user_id == user.id,
                    StudyPlan.status != "deleted",
                )
            ),
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.rollback()
        raise StaleWriteError("stale_task_version")
    db.commit()
    return get_task(db, user, task_id)


def delete_task(db: Session, user: User, task_id: int) -> bool:
    t = get_task(db, user, task_id)
    if t is None:
        return False
    db.delete(t)
    db.commit()
    return True


def plan_progress(plan: StudyPlan) -> dict:
    """Compute progress summary for a plan."""
    tasks = list(plan.tasks) if hasattr(plan, "tasks") else []
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    return {
        "total": total,
        "completed": completed,
        "percent": round((completed / total * 100) if total else 0.0, 1),
    }
