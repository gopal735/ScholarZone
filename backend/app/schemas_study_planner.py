"""Wire contracts for the study planner."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class StudyPlanTaskCreate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)

    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    due_date: Optional[date] = None
    related_scholarship_id: Optional[int] = None
    rationale: Optional[str] = None


class StudyPlanTaskUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = Field(default=None, pattern="^(low|medium|high)$")
    due_date: Optional[date] = None
    status: Optional[str] = Field(default=None, pattern="^(open|completed|reopened)$")
    rationale: Optional[str] = Field(default=None, max_length=2000)
    version: Optional[int] = Field(default=None, ge=1)


class StudyPlanTaskResponse(BaseModel):
    id: int
    plan_id: int
    title: str
    description: Optional[str] = None
    priority: str
    due_date: Optional[date] = None
    status: str
    related_scholarship_id: Optional[int] = None
    rationale: Optional[str] = None
    position: int
    version: int = 1
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class StudyPlanCreate(BaseModel):
    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=255)
    goal: Optional[str] = Field(default=None, max_length=2000)
    scholarship_id: Optional[int] = None
    tasks: list[StudyPlanTaskCreate] = Field(default_factory=list, max_length=100)


class StudyPlanUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    goal: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, pattern="^(active|paused|completed)$")
    version: Optional[int] = Field(default=None, ge=1)


class StudyPlanResponse(BaseModel):
    id: int
    user_id: int
    title: str
    goal: Optional[str] = None
    scholarship_id: Optional[int] = None
    status: str
    version: int = 1
    tasks: list[StudyPlanTaskResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
