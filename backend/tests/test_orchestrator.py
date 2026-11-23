"""Tests for the bounded orchestrator."""

from __future__ import annotations

from app.services.orchestrator import (
    Orchestrator,
    TaskState,
    TaskBudget,
    ToolRegistry,
    ToolPermission,
)


def test_task_lifecycle():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"})
    assert task.state == TaskState.CREATED

    def plan(t, o):
        return {"ok": True}

    orch.run(task, plan)
    assert task.state == TaskState.COMPLETED
    assert task.result == {"ok": True}


def test_ownership_isolation():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"})
    assert orch.get_task(task.task_id, user_id=2) is None
    assert orch.get_task(task.task_id, user_id=1) is not None


def test_tool_permission_enforcement():
    reg = ToolRegistry()
    reg.register(
        ToolPermission(tool_name="search", allowed_for_task_types=frozenset({"research"}), max_calls_per_task=2),
        lambda q: f"result:{q}",
    )
    orch = Orchestrator(tool_registry=reg)
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"})

    # allowed
    r = reg.invoke("search", task, q="hello")
    assert r == "result:hello"
    assert task.tool_calls_used == 1

    # not allowed task type
    task2 = orch.create_task(user_id=1, task_type="other")
    try:
        reg.invoke("search", task2, q="x")
        assert False, "should raise"
    except PermissionError:
        pass


def test_budget_max_tool_calls():
    reg = ToolRegistry()
    reg.register(
        ToolPermission(tool_name="search", allowed_for_task_types=frozenset({"research"}), max_calls_per_task=1),
        lambda q: "r",
    )
    orch = Orchestrator(tool_registry=reg)
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"}, budget=TaskBudget(max_tool_calls=1))
    reg.invoke("search", task, q="a")
    try:
        reg.invoke("search", task, q="b")
        assert False, "should raise"
    except RuntimeError:
        pass


def test_cancel():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"})

    def plan(t, o):
        t.cancel()
        return None

    orch.run(task, plan)
    assert task.state == TaskState.CANCELLED


def test_task_failure():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"})

    def plan(t, o):
        raise ValueError("boom")

    orch.run(task, plan)
    assert task.state == TaskState.FAILED
    assert "boom" in (task.error or "")


def test_list_tasks_user_scoped():
    orch = Orchestrator()
    orch.create_task(user_id=1, task_type="a")
    orch.create_task(user_id=2, task_type="b")
    assert len(orch.list_tasks(1)) == 1
    assert len(orch.list_tasks(2)) == 1
