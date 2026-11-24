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


def test_result_setter_input_isolation():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    data = {"items": [1, 2]}
    task.result = data
    data["items"].append(3)
    data["extra"] = "x"
    assert task.result == {"items": [1, 2]}


def test_result_getter_output_isolation():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.result = {"items": [1, 2]}
    out = task.result
    out["items"].append(3)
    assert task.result == {"items": [1, 2]}


def test_direct_completion_isolation():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)
    original = {"nested": {"value": 7}}
    assert task.commit_completion(original) is True
    original["nested"]["value"] = 999
    assert task.result == {"nested": {"value": 7}}


def test_direct_completion_invalid_result_leaves_state():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)
    before = task.finished_at
    assert task.commit_completion(object()) is False
    assert task.state == TaskState.VALIDATING
    assert task.result is None
    assert task.finished_at == before


def test_direct_completion_cannot_repeat():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)
    assert task.commit_completion({"ok": True}) is True
    assert task.commit_completion({"ok": False}) is False
    assert task.result == {"ok": True}
    assert task.state == TaskState.COMPLETED


def test_unconfirmed_tool_does_not_consume_quota():
    reg = ToolRegistry()
    reg.register(
        ToolPermission(tool_name="search", allowed_for_task_types=frozenset({"research"}), requires_user_confirmation=True, max_calls_per_task=2),
        lambda q: "r",
    )
    orch = Orchestrator(tool_registry=reg)
    task = orch.create_task(user_id=1, task_type="research", allowed_tools={"search"})
    before = task.tool_calls_used
    try:
        reg.invoke("search", task, q="x")
        assert False, "should raise"
    except PermissionError:
        pass
    assert task.tool_calls_used == before


def test_result_setter_rejected_after_completed():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)
    assert task.commit_completion({"final": True}) is True
    try:
        task.result = {"replacement": True}
        assert False, "should raise"
    except RuntimeError:
        pass
    assert task.result == {"final": True}


def test_result_setter_rejected_after_failed():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.FAILED)
    try:
        task.result = {"replacement": True}
        assert False, "should raise"
    except RuntimeError:
        pass


def test_result_setter_rejected_after_cancelled():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.cancel()
    try:
        task.result = {"replacement": True}
        assert False, "should raise"
    except RuntimeError:
        pass


def test_result_setter_rejected_clear_after_terminal():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)
    assert task.commit_completion({"final": True}) is True
    try:
        task.result = None
        assert False, "should raise"
    except RuntimeError:
        pass
    assert task.result == {"final": True}


def test_result_setter_invalid_does_not_overwrite():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.result = {"kept": True}
    try:
        task.result = object()
        assert False, "should raise"
    except (TypeError, ValueError):
        pass
    assert task.result == {"kept": True}


import threading


def test_concurrent_completion_exactly_one_wins():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)

    barrier = threading.Barrier(2)
    results = []

    def worker(value):
        barrier.wait()
        results.append(task.commit_completion({value: True}))

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert results.count(True) == 1
    assert results.count(False) == 1
    assert task.state == TaskState.COMPLETED


def test_cancellation_before_completion_wins():
    orch = Orchestrator()
    task = orch.create_task(user_id=1, task_type="research", allowed_tools=set())
    task.transition(TaskState.PLANNING)
    task.transition(TaskState.RUNNING)
    task.transition(TaskState.VALIDATING)
    task.cancel()
    assert task.commit_completion({"final": True}) is False
    assert task.state == TaskState.CANCELLED
    assert task.result is None
