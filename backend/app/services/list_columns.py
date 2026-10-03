"""The one place that decides what a stored list column may contain.

Six ``scholarships`` columns are declared ``list[str]`` in both the ORM model
and the public detail contract:

    eligibility, benefits, coverage, requirements, documents,
    application_method

They are JSON columns, which means the database will happily store a JSON
*scalar* in them. ``"Apply through the DAAD portal"`` is valid JSON. So a row
can hold a bare string where the contract promises a list, and because the
directory response declares none of these fields the record still renders as a
card - it fails only on its own page, as a 500 from response validation.

That is not a hypothetical: it is how 117 of the 386 public records were
serving. The shape was produced by two write paths (a maintenance stage that
filed researched prose under a text mapping, and the discovery pipeline
passing an extractor's ``str`` field straight into a list column), stored
without constraint, and read back with a contract that had no coercion for it.

This module is the single deterministic rule for turning a stored value into
``list[str]``. It is deliberately narrow:

* ``None`` becomes ``[]`` - the column is non-nullable and an empty list says
  "nothing recorded", which is the truth.
* ``list`` is returned unchanged, element for element and in order. Members
  that are not strings are rejected rather than stringified: ``str(1)`` is a
  different fact from ``1``.
* ``str`` becomes a one-element list holding that exact string. The text is
  not stripped, split, re-wrapped or truncated. A researched paragraph stored
  in the wrong container is still that paragraph, and moving it must not edit
  it.
* Everything else - a number, a dict, a nested object - is refused. There is
  no defensible reading of those, so guessing is not an option.

The rule is total and idempotent: applying it twice returns the same value as
applying it once, which is what makes it safe to run against the whole table.
"""

from __future__ import annotations

#: The JSON columns that the model and the detail contract both declare as
#: ``list[str]``. ``required_documents`` is deliberately absent: it has no
#: column of its own and is an alias for ``documents``.
LIST_COLUMNS: tuple[str, ...] = (
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "application_method",
)


class ListColumnShapeError(ValueError):
    """A stored value cannot be reshaped into ``list[str]`` without guessing."""


def normalize_list_column(value: object, *, field: str | None = None) -> tuple[list[str], bool]:
    """Return ``(list_of_str, changed)`` for one stored list column.

    ``changed`` is ``True`` only when the stored value was not already a valid
    ``list[str]``, so a caller can report what it actually rewrote instead of
    how many rows it walked.
    """
    label = f"{field!r}: " if field else ""
    if value is None:
        return [], True
    if isinstance(value, list):
        for index, member in enumerate(value):
            if not isinstance(member, str):
                raise ListColumnShapeError(
                    f"{label}list member {index} is {type(member).__name__}, "
                    "not str; refusing to stringify a value that was not text"
                )
        return list(value), False
    if isinstance(value, str):
        # Preserved byte for byte. Only an entirely blank string is treated as
        # "nothing recorded"; a string with real content keeps its own spacing
        # and punctuation because callers quote it verbatim.
        return ([value] if value.strip() else []), True
    raise ListColumnShapeError(
        f"{label}expected a list, a string or null, got {type(value).__name__}"
    )


def normalize_list_columns(row: object, *, fields: tuple[str, ...] = LIST_COLUMNS) -> dict[str, list[str]]:
    """Return the normalized value of every named column on ``row``.

    Only columns that actually need reshaping appear in the result, so an
    unchanged row produces an empty dict and a caller cannot mistake a walk
    for a rewrite.
    """
    out: dict[str, list[str]] = {}
    for name in fields:
        value, changed = normalize_list_column(getattr(row, name, None), field=name)
        if changed:
            out[name] = value
    return out