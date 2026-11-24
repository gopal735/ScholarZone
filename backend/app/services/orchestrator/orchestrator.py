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
    started_monotonic_at: float | None = None
    finished_monotonic_at: float | None = None
    _result: Any = field(default=None, repr=False)
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    tool_calls_used: int = 0
    tool_calls_by_tool: dict[str, int] = field(default_factory=dict)
    depth_used: int = 0
    running: bool = False
    confirmed_tools: set[str] = field(default_factory=set)
    context_chars_used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def result(self) -> Any:
        stored = self._result
        if stored is None:
            return None
        return _detach_result(stored, self.budget.max_context_chars)

    @result.setter
    def result(self, value: Any) -> None:
        if value is None:
            self._result = None
            return
        self._result = _detach_result(value, self.budget.max_context_chars)

    @property
    def elapsed_seconds(self) -> float:
        if self.started_monotonic_at is None:
            return 0.0
        end = self.finished_monotonic_at if self.finished_monotonic_at is not None else time.monotonic()
        return end - self.started_monotonic_at

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
                self.started_monotonic_at = time.monotonic()
            if new_state in TERMINAL_STATES:
                self.finished_at = time.time()
                self.finished_monotonic_at = time.monotonic()

    def cancel(self) -> None:
        with self._lock:
            if self.state in TERMINAL_STATES:
                return
            self.cancel_event.set()
            self.state = TaskState.CANCELLED
            self.finished_at = time.time()
            self.finished_monotonic_at = time.monotonic()

    def commit_completion(self, result: Any) -> bool:
        with self._lock:
            if self.state != TaskState.VALIDATING:
                return False
            self._result = result
            self.finished_at = time.time()
            self.finished_monotonic_at = time.monotonic()
            self.state = TaskState.COMPLETED
            return True

    def try_start_run(self) -> bool:
        with self._lock:
            if self.running or self.state in TERMINAL_STATES:
                return False
            self.running = True
            return True

    def finish_run(self) -> None:
        with self._lock:
            self.running = False

    def confirm_tool(self, tool_name: str) -> None:
        with self._lock:
            self.confirmed_tools.add(tool_name)

    def reserve_tool_call(self, tool_name: str, max_per_tool: int) -> str | None:
        with self._lock:
            if self.state in TERMINAL_STATES:
                return "cancelled" if self.state == TaskState.CANCELLED else "task_terminal"
            if self.cancel_event.is_set():
                return "cancelled"
            if self.tool_calls_used >= self.budget.max_tool_calls:
                return "max_tool_calls_exceeded"
            if self.tool_calls_by_tool.get(tool_name, 0) >= max_per_tool:
                return "tool_call_limit_exceeded"
            # Duration budget (cooperative): reject once expired.
            if self.started_monotonic_at is not None:
                end = self.finished_monotonic_at if self.finished_monotonic_at is not None else time.monotonic()
                elapsed = end - self.started_monotonic_at
                if elapsed >= self.budget.max_duration_seconds:
                    return "max_duration_exceeded"
            if self.depth_used >= self.budget.max_depth:
                return "max_depth_exceeded"
            if self.context_chars_used >= self.budget.max_context_chars:
                return "max_context_exceeded"
            self.tool_calls_used += 1
            self.tool_calls_by_tool[tool_name] = self.tool_calls_by_tool.get(tool_name, 0) + 1
            return None

    def record_tool_call(self) -> None:
        with self._lock:
            self.tool_calls_used += 1

    def record_context(self, chars: int) -> None:
        with self._lock:
            if isinstance(chars, bool) or not isinstance(chars, int):
                raise TypeError("invalid_context_chars")
            if chars < 0:
                raise ValueError("invalid_context_chars")
            if self.context_chars_used + chars > self.budget.max_context_chars:
                raise ValueError("max_context_exceeded")
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
        return task_type in perm.allowed_for_task_types

    def invoke(self, tool_name: str, task: TaskExecution, **kwargs) -> Any:
        """Invoke a tool with permission and budget checks."""
        if task is None:
            raise PermissionError("task is required")
        with task._lock:
            if task.state in TERMINAL_STATES:
                raise RuntimeError("task_terminal" if task.state != TaskState.CANCELLED else "cancelled")
            if task.cancel_event.is_set():
                raise RuntimeError("cancelled")
        perm = self._tools.get(tool_name)
        if perm is None:
            raise PermissionError(f"Tool {tool_name} is not registered")
        if task.task_type not in perm.allowed_for_task_types:
            raise PermissionError(f"Tool {tool_name} not allowed for task {task.task_type}")
        # Deny-by-default: tool must be in the task's explicit allowed set.
        if tool_name not in task.allowed_tools:
            raise PermissionError(f"Tool {tool_name} not in allowed set for task {task.task_id}")
        budget_error = task.reserve_tool_call(tool_name, perm.max_calls_per_task)
        if budget_error:
            raise RuntimeError(budget_error)
        if perm.requires_user_confirmation:
            with task._lock:
                if tool_name not in task.confirmed_tools:
                    raise PermissionError(f"Tool {tool_name} requires user confirmation")
                task.confirmed_tools.discard(tool_name)
        handler = self._handlers[tool_name]
        return handler(**kwargs)



def _result_size(value: Any, limit: int, _seen: set[int] | None = None, _depth: int = 0) -> int:
    """Return a bounded byte-size estimate for a structured result."""
    if _seen is None:
        _seen = set()
    if _depth > 50:
        raise ValueError("result_too_deep")
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if value is None or isinstance(value, bool):
        return 4
    if isinstance(value, int):
        if value.bit_length() > 63:
            raise ValueError("integer_too_large")
        return 8
    if isinstance(value, float):
        return 8
    obj_id = id(value)
    if obj_id in _seen:
        raise ValueError("circular_result")
    _seen.add(obj_id)
    try:
        if isinstance(value, (list, tuple)):
            total = 2
            for item in value:
                total += _result_size(item, limit, _seen, _depth + 1) + 1
                if total > limit:
                    return total
            return total
        if isinstance(value, dict):
            total = 2
            for key, item in value.items():
                total += _result_size(key, limit, _seen, _depth + 1)
                total += _result_size(item, limit, _seen, _depth + 1) + 1
                if total > limit:
                    return total
            return total
        raise TypeError("unsupported_result_type")
    finally:
        _seen.discard(obj_id)


def _detach_result(value: Any, limit: int, _seen: set[int] | None = None, _depth: int = 0, _budget: list[int] | None = None) -> Any:
    """Return a detached, supported copy of a structured result."""
    if _seen is None:
        _seen = set()
    if _budget is None:
        _budget = [limit]
    if _depth > 50:
        raise ValueError("result_too_deep")
    if value is None or isinstance(value, bool):
        if _budget[0] < 4:
            raise ValueError("result_too_large")
        _budget[0] -= 4
        return value
    if isinstance(value, str):
        cost = len(value.encode("utf-8"))
        if _budget[0] < cost:
            raise ValueError("result_too_large")
        _budget[0] -= cost
        return str(value)
    if isinstance(value, int):
        if value.bit_length() > 63:
            raise ValueError("integer_too_large")
        if _budget[0] < 8:
            raise ValueError("result_too_large")
        _budget[0] -= 8
        return value
    if isinstance(value, float):
        if _budget[0] < 8:
            raise ValueError("result_too_large")
        _budget[0] -= 8
        return value
    obj_id = id(value)
    if obj_id in _seen:
        raise ValueError("circular_result")
    _seen.add(obj_id)
    try:
        if isinstance(value, (list, tuple)):
            if _budget[0] < 2:
                raise ValueError("result_too_large")
            _budget[0] -= 2
            items = []
            for item in value:
                if _budget[0] < 1:
                    raise ValueError("result_too_large")
                _budget[0] -= 1
                items.append(_detach_result(item, limit, _seen, _depth + 1, _budget))
            return list(items) if isinstance(value, list) else tuple(items)
        if isinstance(value, dict):
            if _budget[0] < 2:
                raise ValueError("result_too_large")
            _budget[0] -= 2
            result: dict[Any, Any] = {}
            for key, item in value.items():
                if _budget[0] < 1:
                    raise ValueError("result_too_large")
                _budget[0] -= 1
                detached_key = _detach_result(key, limit, _seen, _depth + 1, _budget)
                detached_item = _detach_result(item, limit, _seen, _depth + 1, _budget)
                result[detached_key] = detached_item
            return result
        raise TypeError("unsupported_result_type")
    except RuntimeError as exc:
        raise ValueError("result_collection_changed") from exc
    finally:
        _seen.discard(obj_id)


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
        if not task.try_start_run():
            # Rejected duplicate run: do not mutate the active task's state.
            return task
        # Cooperative cancellation before planning.
        if task.cancel_event.is_set():
            task.cancel()
            task.finish_run()
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
                task.finish_run()
                return task
            # Restrict planning output size (structured).
            try:
                detached_result = _detach_result(result, task.budget.max_context_chars)
                size = _result_size(detached_result, task.budget.max_context_chars)
            except (TypeError, ValueError):
                raise RuntimeError("plan_output_too_large")
            if size > task.budget.max_context_chars:
                raise RuntimeError("plan_output_too_large")
            if task.context_chars_used > task.budget.max_context_chars:
                raise RuntimeError("max_context_exceeded")
            if task.elapsed_seconds >= task.budget.max_duration_seconds:
                raise RuntimeError("max_duration_exceeded")
            task.transition(TaskState.VALIDATING)
            committed = task.commit_completion(detached_result)
            if not committed:
                task.finish_run()
                return task
        except Exception as exc:  # noqa: BLE001
            if task.cancel_event.is_set():
                task.cancel()
            else:
                task.error = str(exc)[:500]
                try:
                    task.transition(TaskState.FAILED)
                except ValueError:
                    pass
        finally:
            task.finish_run()
        return task

    def confirm_tool(self, task_id: str, user_id: int, tool_name: str) -> bool:
        task = self.get_task(task_id, user_id)
        if task is None:
            return False
        perm = self._tool_registry._tools.get(tool_name)
        if perm is None or not perm.requires_user_confirmation:
            return False
        if tool_name not in task.allowed_tools:
            return False
        if task.task_type not in perm.allowed_for_task_types:
            return False
        task.confirm_tool(tool_name)
        return True

    def cancel_task(self, task_id: str, user_id: int) -> bool:
        task = self.get_task(task_id, user_id)
        if task is None:
            return False
        task.cancel()
        return True

    def list_tasks(self, user_id: int) -> list[TaskExecution]:
        with self._lock:
            return [t for t in self._tasks.values() if t.user_id == user_id]
