"""Study planner private API for Dream AI Mentor 2.0."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_user
from ..models import User
from ..schemas_study_planner import (
    StudyPlanCreate,
    StudyPlanResponse,
    StudyPlanTaskCreate,
    StudyPlanTaskResponse,
    StudyPlanTaskUpdate,
    StudyPlanUpdate,
)
from ..services.study_planner import service as sp
from ..services.study_planner.service import StaleWriteError

router = APIRouter(prefix="/study-plans", tags=["study-plans"])


def _plan_to_response(plan) -> StudyPlanResponse:
    from ..services.study_planner import plan_progress
    tasks = sorted(plan.tasks, key=lambda t: t.position) if hasattr(plan, "tasks") else []
    return StudyPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        title=plan.title,
        goal=plan.goal,
        scholarship_id=plan.scholarship_id,
        status=plan.status,
        version=getattr(plan, "version", 1),
        tasks=[
            StudyPlanTaskResponse(
                id=t.id,
                plan_id=t.plan_id,
                title=t.title,
                description=t.description,
                priority=t.priority,
                due_date=t.due_date,
                status=t.status,
                related_scholarship_id=t.related_scholarship_id,
                rationale=t.rationale,
                position=t.position,
                version=getattr(t, "version", 1),
                completed_at=t.completed_at,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("", response_model=list[StudyPlanResponse])
def list_plans(db: Session = Depends(get_db), user: User = Depends(require_user)):
    plans = sp.list_plans(db, user)
    # filter out soft-deleted
    plans = [p for p in plans if p.status != "deleted"]
    return [_plan_to_response(p) for p in plans]


@router.post("", response_model=StudyPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(payload: StudyPlanCreate, db: Session = Depends(get_db), user: User = Depends(require_user)):
    try:
        plan = sp.create_plan(db, user, payload)
    except ValueError as exc:
        if str(exc) == "too_many_tasks":
            raise HTTPException(status_code=400, detail="Too many tasks for plan.")
        raise
    return _plan_to_response(plan)


@router.get("/{plan_id}", response_model=StudyPlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    plan = sp.get_plan(db, user, plan_id)
    if plan is None or plan.status == "deleted":
        raise HTTPException(status_code=404, detail="Plan not found.")
    return _plan_to_response(plan)


@router.patch("/{plan_id}", response_model=StudyPlanResponse)
def update_plan(plan_id: int, payload: StudyPlanUpdate, db: Session = Depends(get_db), user: User = Depends(require_user)):
    try:
        plan = sp.update_plan(db, user, plan_id, payload)
    except StaleWriteError:
        raise HTTPException(status_code=409, detail="Plan version conflict.")
    except ValueError as exc:
        if str(exc) == "too_many_tasks":
            raise HTTPException(status_code=400, detail="Too many tasks for plan.")
        raise
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return _plan_to_response(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    ok = sp.delete_plan(db, user, plan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Plan not found.")


@router.post("/{plan_id}/tasks", response_model=StudyPlanTaskResponse, status_code=status.HTTP_201_CREATED)
def add_task(plan_id: int, payload: StudyPlanTaskCreate, db: Session = Depends(get_db), user: User = Depends(require_user)):
    try:
        t = sp.add_task(db, user, plan_id, payload)
    except ValueError as exc:
        if str(exc) == "too_many_tasks":
            raise HTTPException(status_code=400, detail="Too many tasks for plan.")
        raise
    if t is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return StudyPlanTaskResponse(
        id=t.id, plan_id=t.plan_id, title=t.title, description=t.description,
        priority=t.priority, due_date=t.due_date, status=t.status,
        related_scholarship_id=t.related_scholarship_id, rationale=t.rationale,
        position=t.position, completed_at=t.completed_at,
        created_at=t.created_at, updated_at=t.updated_at,
    )


@router.patch("/tasks/{task_id}", response_model=StudyPlanTaskResponse)
def update_task(task_id: int, payload: StudyPlanTaskUpdate, db: Session = Depends(get_db), user: User = Depends(require_user)):
    try:
        t = sp.update_task(db, user, task_id, payload)
    except StaleWriteError:
        raise HTTPException(status_code=409, detail="Task version conflict.")
    except ValueError as exc:
        if str(exc) == "too_many_tasks":
            raise HTTPException(status_code=400, detail="Too many tasks for plan.")
        raise
    if t is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return StudyPlanTaskResponse(
        id=t.id, plan_id=t.plan_id, title=t.title, description=t.description,
        priority=t.priority, due_date=t.due_date, status=t.status,
        related_scholarship_id=t.related_scholarship_id, rationale=t.rationale,
        position=t.position, completed_at=t.completed_at,
        created_at=t.created_at, updated_at=t.updated_at,
    )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    ok = sp.delete_task(db, user, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found.")
