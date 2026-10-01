"""Router modules must not reference names they never imported.

The homepage statistics endpoint returned HTTP 500 in production with
``NameError: name 'public_visibility_conditions' is not defined``. The helper had
been moved into the repository module so the directory and the homepage could
share one definition of "publicly visible", but the router that calls it was
never given the import. Every test passed, because no test exercised the stats
endpoint.

The check uses :mod:`symtable`, which is the compiler's own view of scope, rather
than walking the AST by hand. A hand-rolled version reports every local variable
as undefined; symtable already knows which names a function binds itself and
which ones it looks up in the module namespace, so the only names left are the
ones that would raise NameError at runtime.
"""

from __future__ import annotations

import builtins
import importlib
import inspect
import symtable

import pytest

ROUTER_MODULES = [
    "app.routers.scholarships",
    "app.routers.verification",
    "app.routers.admin_image_review",
    "app.routers.discovery",
    "app.routers.admin_dashboard",
    "app.routers.enrichment",
]


def _walk(table: symtable.SymbolTable):
    yield table
    for child in table.get_children():
        yield from _walk(child)


def undefined_globals(module) -> set[str]:
    """Names the module reads from module scope without defining them."""
    source = inspect.getsource(module)
    table = symtable.symtable(source, module.__file__, "exec")

    defined = {symbol.get_name() for symbol in table.get_symbols()}
    defined |= set(vars(module))
    # len, int, Exception and the rest resolve through builtins, so they are
    # found in every scope and are not a missing import.
    defined |= set(dir(builtins))

    missing: set[str] = set()
    for scope in _walk(table):
        if scope.get_type() == "module":
            continue
        for symbol in scope.get_symbols():
            # is_global() means "bound in the module namespace", which is
            # exactly the lookup that raises NameError if it is not there.
            if symbol.is_global() and not symbol.is_assigned():
                missing.add(symbol.get_name())
    return {name for name in missing if name not in defined}


@pytest.mark.parametrize("module_name", ROUTER_MODULES)
def test_router_references_only_names_it_defines(module_name):
    module = importlib.import_module(module_name)
    missing = undefined_globals(module)
    assert not missing, (
        f"{module_name} reads names it never defines or imports: {sorted(missing)}"
    )


def test_name_resolution_check_detects_a_missing_import():
    """The check has to be capable of failing, or it proves nothing."""
    source = "def handler():\n    return some_helper()\n"
    table = symtable.symtable(source, "<probe>", "exec")
    function_scope = table.get_children()[0]
    globals_read = {
        symbol.get_name()
        for symbol in function_scope.get_symbols()
        if symbol.is_global() and not symbol.is_assigned()
    }
    assert "some_helper" in globals_read


def test_stats_endpoint_can_resolve_its_visibility_helper():
    """The exact regression: the stats endpoint's helper was not imported."""
    router = importlib.import_module("app.routers.scholarships")
    repository = importlib.import_module("app.repositories.scholarships")
    assert hasattr(router, "public_visibility_conditions")
    assert (
        router.public_visibility_conditions
        is repository.public_visibility_conditions
    ), (
        "the router must use the repository's single definition, not a copy; "
        "a second copy is how the homepage and the directory disagree"
    )


def test_directory_and_stats_share_one_visibility_rule():
    repository = importlib.import_module("app.repositories.scholarships")
    source = inspect.getsource(repository)
    assert source.count("def public_visibility_conditions") == 1, (
        "there must be exactly one definition of public visibility"
    )