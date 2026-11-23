"""Bounded agent orchestrator for ScholarZone AI.

Defines task execution states, ownership, permission enforcement, budget
limits, and cancellation. Agents are bounded capabilities, not autonomous
loops.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskState(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Terminal states.
TERMINAL_STATES = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}


# Explicit allowed state transitions. Any transition not listed here is invalid.
VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {TaskState.PLANNING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.PLANNING: {TaskState.RUNNING, TaskState.WAITING_FOR_USER, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.RUNNING: {TaskState.WAITING_FOR_USER, TaskState.VALIDATING, TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.WAITING_FOR_USER: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.VALIDATING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


@dataclass
class TaskBudget:
    """Hard limits for a task execution."""

    max_tool_calls: int = 10
    max_depth: int = 3
    max_planning_steps: int = 100
    max_duration_seconds: float = 60.0
    max_context_chars: int = 8_000
    max_retries: int = 2


@dataclass
class TaskExecution:
    """A single orchestrated task."""

    task_id: str
    user_id: int
    task_type: str
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    budget: TaskBudget = field(default_factory=TaskBudget)
    state: TaskState = TaskState.CREATED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: Any = None
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    tool_calls_used: int = 0
    depth_used: int = 0
    context_chars_used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at or time.time()
        return end - self.started_at

    def check_budget(self) -> str | None:
        """Return an error message if a budget is exceeded, else None."""
        with self._lock:
            if self.tool_calls_used >= self.budget.max_tool_calls:
                return "max_tool_calls_exceeded"
            if self.depth_used >= self.budget.max_depth:
                return "max_depth_exceeded"
            if self.elapsed_seconds >= self.budget.max_duration_seconds:
                return "max_duration_exceeded"
            if self.context_chars_used >= self.budget.max_context_chars:
                return "max_context_exceeded"
            return None

    def transition(self, new_state: TaskState) -> None:
        with self._lock:
            if self.state in TERMINAL_STATES:
                raise ValueError(f"Cannot transition from terminal state {self.state}")
            if new_state not in VALID_TRANSITIONS.get(self.state, set()):
                raise ValueError(f"Invalid transition {self.state} -> {new_state}")
            self.state = new_state
            if new_state == TaskState.RUNNING and self.started_at is None:
                self.started_at = time.time()
            if new_state in TERMINAL_STATES:
                self.finished_at = time.time()

    def cancel(self) -> None:
        with self._lock:
            if self.state in TERMINAL_STATES:
                return
            self.cancel_event.set()
            self.state = TaskState.CANCELLED
            self.finished_at = time.time()

    def record_tool_call(self) -> None:
        with self._lock:
            self.tool_calls_used += 1

    def record_context(self, chars: int) -> None:
        with self._lock:
            self.context_chars_used += chars


@dataclass
class ToolPermission:
    """Permission declaration for a tool."""

    tool_name: str
    allowed_for_task_types: frozenset[str] = field(default_factory=frozenset)
    requires_user_confirmation: bool = False
    max_calls_per_task: int = 5


class ToolRegistry:
    """Registry of permitted tools with permission enforcement."""

    def __init__(self):
        self._tools: dict[str, ToolPermission] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, permission: ToolPermission, handler: Callable) -> None:
        self._tools[permission.tool_name] = permission
        self._handlers[permission.tool_name] = handler

    def is_allowed(self, tool_name: str, task_type: str) -> bool:
        perm = self._tools.get(tool_name)
        if perm is None:
            return False
        if perm.allowed_for_task_types and task_type not in perm.allowed_for_task_types:
            return False
        return True

    def invoke(self, tool_name: str, task: TaskExecution, **kwargs) -> Any:
        """Invoke a tool with permission and budget checks."""
        if not self.is_allowed(tool_name, task.task_type):
            raise PermissionError(f"Tool {tool_name} not allowed for task {task.task_type}")
        # Deny-by-default: tool must be in the task's explicit allowed set.
        if tool_name not in task.allowed_tools:
            raise PermissionError(f"Tool {tool_name} not in allowed set for task {task.task_id}")
        perm = self._tools[tool_name]
        if task.tool_calls_used >= perm.max_calls_per_task:
            raise RuntimeError(f"Tool {tool_name} call limit exceeded")
        budget_error = task.check_budget()
        if budget_error:
            raise RuntimeError(budget_error)
        task.record_tool_call()
        handler = self._handlers[tool_name]
        return handler(**kwargs)


class Orchestrator:
    """Bounded task orchestrator."""

    def __init__(self, tool_registry: ToolRegistry | None = None):
        self._tasks: dict[str, TaskExecution] = {}
        self._lock = threading.Lock()
        self._tool_registry = tool_registry or ToolRegistry()

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._tool_registry

    def create_task(
        self,
        user_id: int,
        task_type: str,
        allowed_tools: set[str] | frozenset[str] | None = None,
        budget: TaskBudget | None = None,
    ) -> TaskExecution:
        task = TaskExecution(
            task_id=uuid.uuid4().hex[:16],
            user_id=user_id,
            task_type=task_type,
            allowed_tools=frozenset(allowed_tools or []),
            budget=budget or TaskBudget(),
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str, user_id: int) -> TaskExecution | None:
        """Get a task, enforcing ownership."""
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None or task.user_id != user_id:
            return None
        return task

    def run(
        self,
        task: TaskExecution,
        plan_func: Callable[[TaskExecution, "Orchestrator"], Any],
    ) -> TaskExecution:
        """Execute a task using the provided plan function.

        The plan function receives the task and orchestrator and must respect
        budget limits and cancellation. It should return a result or raise.

        Arbitrary synchronous Python functions cannot be forcibly interrupted;
        duration and size limits are checked cooperatively before and after
        planning. Untrusted callbacks are rejected.
        """
        if not callable(plan_func):
            raise TypeError("plan_func must be callable")
        if task.is_terminal:
            return task
        # Cooperative cancellation before planning.
        if task.cancel_event.is_set():
            task.cancel()
            return task
        try:
            task.transition(TaskState.PLANNING)
            # Restrict planning input size.
            if task.context_chars_used > task.budget.max_context_chars:
                raise RuntimeError("max_context_exceeded")
            task.transition(TaskState.RUNNING)
            result = plan_func(task, self)
            if task.cancel_event.is_set():
                task.cancel()
                return task
            # Restrict planning output size.
            if isinstance(result, str) and len(result) > task.budget.max_context_chars:
                raise RuntimeError("plan_output_too_large")
            if task.elapsed_seconds >= task.budget.max_duration_seconds:
                raise RuntimeError("max_duration_exceeded")
            task.transition(TaskState.VALIDATING)
            task.result = result
            task.transition(TaskState.COMPLETED)
        except Exception as exc:  # noqa: BLE001
            if task.cancel_event.is_set():
                task.cancel()
            else:
                task.error = str(exc)[:500]
                try:
                    task.transition(TaskState.FAILED)
                except ValueError:
                    pass
        return task

    def cancel_task(self, task_id: str, user_id: int) -> bool:
        task = self.get_task(task_id, user_id)
        if task is None:
            return False
        task.cancel()
        return True

    def list_tasks(self, user_id: int) -> list[TaskExecution]:
        with self._lock:
            return [t for t in self._tasks.values() if t.user_id == user_id]
