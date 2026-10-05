"""The one-shot Supervisor trigger's bounds, asserted rather than documented.

``routers/supervisor_trigger.py`` claims seven properties: one scholarship, no
country path, no batch path, no maintenance, no scholarship DiscoveryCandidate
seeding, no browser rendering, and classification before persistence. Each is a
structural claim - something about what the module can reach - so each is tested
as one. A comment cannot fail a build; these can.

The bounded-scope tests read the module's own source and imports rather than
trying to infer intent, because the properties are about what is *reachable*, and
reachability is decided by imports and call sites.
"""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.routers import supervisor_trigger  # noqa: E402
from app.routers.supervisor_trigger import _verify_secret, discover_one  # noqa: E402

SOURCE_PATH = (
    Path(inspect.getfile(supervisor_trigger)).resolve()
)


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def _code_only() -> str:
    """The module's code with docstrings, strings and comments removed.

    Several of these tests assert that a name does not appear in the module. The
    module explains each property in prose, and that prose necessarily names the
    thing it is forbidding - so searching the raw source would match the
    explanation and fail every run. What matters is whether the name can be
    *executed*, which is what the token stream without literals answers.
    """
    import io
    import tokenize

    kept: list[str] = []
    with SOURCE_PATH.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (tokenize.STRING, tokenize.COMMENT):
                continue
            kept.append(token.string)
    return " ".join(kept)


def _imported_names() -> set[str]:
    """Every name the trigger module imports, fully qualified where possible."""
    tree = ast.parse(_source())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * (node.level or 0)
            module = f"{prefix}{node.module or ''}"
            for alias in node.names:
                names.add(f"{module}.{alias.name}")
    return names


# ---------------------------------------------------------------------------
# A. exactly one scholarship
# ---------------------------------------------------------------------------


def test_the_route_takes_one_id_and_offers_no_collection():
    """A path parameter, and no route that could name more than one."""
    paths = {
        route.path: sorted(route.methods or [])
        for route in supervisor_trigger.router.routes
    }
    assert paths == {"/internal/supervisor/discover/{scholarship_id}": ["POST"]}, (
        f"the trigger must expose exactly one route, got {paths}"
    )
    # And the id is a path segment, so it cannot be a list.
    assert "{scholarship_id}" in next(iter(paths))


def test_the_batch_entry_point_is_not_reachable_from_the_trigger():
    """``run_discovery_batch`` is the only thing that widens the set."""
    imports = _imported_names()
    assert not any(name.endswith("run_discovery_batch") for name in imports), (
        "the trigger must not import the batch runner; it is what would let a "
        "call cover more than the one scholarship named"
    )


def test_the_widening_parameters_are_absent():
    """No ``limit``, no ``max_workers``, no ``force``, no render budget."""
    code = _code_only()
    for token in ("limit", "max_workers", "force", "render_budget", "run_discovery_batch"):
        assert token not in code, f"{token!r} must not appear in the trigger's code"


# ---------------------------------------------------------------------------
# B/C/D. no country, no batch, no maintenance, no DiscoveryCandidate seeding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden",
    [
        # scholarship-discovery subsystem: country and batch discovery
        "run_discovery_round",
        "batch_discover_next_cycles",
        "discover_next_cycle",
        "DiscoveryPipeline",
        "DomainRateLimiter",
        "seed_approved_sources",
        # scholarship candidate rows
        "DiscoveryCandidate",
        "next_cycle_discovery",
        "discovery_pipeline",
        # maintenance
        "scholarzone_maintenance",
        "maintenance_slot_store",
        "maintenance_dispatch",
        "internal_maintenance",
        "lifecycle_manager",
        "apply_lifecycle_transition",
        "evaluate_lifecycle",
    ],
)
def test_nothing_from_a_forbidden_subsystem_is_imported(forbidden):
    imports = _imported_names()
    offenders = [
        name for name in imports
        if forbidden in name or name.endswith(f".{forbidden}")
    ]
    assert not offenders, (
        f"the trigger must not import {forbidden!r}; found {offenders}. "
        f"These are the paths to country-wide discovery, batch discovery, "
        f"scholarship candidate seeding and maintenance."
    )


def test_the_only_discovery_call_is_the_single_scholarship_one():
    """One call, to the one-scholarship function, with no render budget."""
    calls = [
        node
        for node in ast.walk(ast.parse(_source()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "discover_for_scholarship"
    ]
    assert len(calls) == 1, "exactly one discovery call site"
    keywords = {kw.arg for kw in calls[0].keywords}
    assert "render_budget" not in keywords, (
        "passing a render_budget is the only way this endpoint could launch a "
        "browser; the batch path omits it for the same reason"
    )


# ---------------------------------------------------------------------------
# E. browser rendering stays separate
# ---------------------------------------------------------------------------


def test_the_trigger_does_not_read_or_set_the_render_flag():
    code = _code_only()
    assert "SCHOLARZONE_SUPERVISOR_RENDER_ENABLED" not in code, (
        "the render switch belongs to the render subsystem. A discovery trigger "
        "that reads it would couple the two; a trigger that set it could turn "
        "browser rendering on from a one-shot discovery call."
    )
    assert "supervisor_render" not in code
    assert "build_driver" not in code


def test_the_render_flag_is_still_off_by_default():
    """Discovery activation and render activation are different switches."""
    from app.services.supervisor_render import rendering_enabled

    assert rendering_enabled() is False, (
        "browser rendering must remain off unless an operator turns it on"
    )


# ---------------------------------------------------------------------------
# authentication
# ---------------------------------------------------------------------------


def test_a_missing_or_wrong_secret_is_refused(monkeypatch):
    monkeypatch.delenv("SCHOLARZONE_VERIFICATION_SECRET", raising=False)
    assert _verify_secret(None) is False
    assert _verify_secret("anything") is False
    assert _verify_secret("") is False


def test_the_configured_secret_is_accepted(monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_VERIFICATION_SECRET", "unit-test-secret")
    assert _verify_secret("unit-test-secret") is True
    assert _verify_secret("unit-test-secre") is False


def test_the_secret_cannot_appear_in_a_response():
    """The handler returns the outcome, never the credential that allowed it."""
    body = _code_only()
    returned = body[body.index("return {") :]
    assert "x_verification_secret" not in returned, (
        "the response body must not echo the credential"
    )
    assert "provided_secret" not in returned
    assert "verification_secret" not in returned


def test_the_unauthorised_path_logs_no_credential():
    code = _code_only()
    logger_calls = [part for part in code.split("logger") if "warning" in part]
    assert logger_calls, "an unauthorised attempt should be logged"
    for part in logger_calls:
        assert "secret" not in part.lower() or "attempt" in part.lower(), (
            f"the log line must not interpolate the credential: {part!r}"
        )


# ---------------------------------------------------------------------------
# signature: one id, no widening knobs
# ---------------------------------------------------------------------------


def test_the_handler_signature_exposes_no_widening_parameter():
    parameters = list(inspect.signature(discover_one).parameters)
    assert parameters == ["scholarship_id", "x_verification_secret", "session"], (
        f"unexpected parameters: {parameters}"
    )