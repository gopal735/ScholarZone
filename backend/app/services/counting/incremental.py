"""Incremental counting, with an honest fallback.

The abstraction is a classification step, not an optimisation. Each change is
labelled with what kind of delta it is, and the counting engine decides per
partition whether that delta can be applied to a running count or whether the
partition must be recomputed.

The default is full recomputation, and it is the default on purpose.

A counter that says "27" is a claim about a specific candidate set under specific
predicates. Maintaining it incrementally means reasoning about whether *this* change
moves *that* count, which is a proof obligation for every partition and every
interaction between them. The interactions are where incremental counting fails:
a record that changes both its country and its funding state moves a country facet
and a funding facet and possibly an eligibility partition, and a change that
crosses the deadline boundary also moves the timing bucket, which changes the
number of records the filter retains, which changes every facet's denominator.

So a change is only ever applied incrementally when it is *provably* local - one
record, one dimension, no other partition affected. Everything else falls back, and
the fallback is published as ``FULL_RECOMPUTE`` rather than hidden.

No persistent counters are introduced. There is no table, no migration, and no
state that can survive a restart and disagree with the data it describes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .types import CountIncrement, IncrementalOutcome


STRATEGY_INCREMENTAL = "INCREMENTAL"
STRATEGY_FULL_RECOMPUTE = "FULL_RECOMPUTE"

#: The conceptual change kinds the architecture names.
CHANGE_NEW = "NEW_SCHOLARSHIP"
CHANGE_MODIFIED = "CHANGED_SCHOLARSHIP"
CHANGE_ARCHIVED = "ARCHIVED_SCHOLARSHIP"
CHANGE_REMOVED = "REMOVED_OR_HIDDEN"
CHANGE_DEADLINE = "CHANGED_DEADLINE"
CHANGE_ELIGIBILITY = "CHANGED_ELIGIBILITY_EVIDENCE"
CHANGE_FUNDING = "CHANGED_FUNDING"
CHANGE_FIELD = "CHANGED_FIELD"

#: Change kinds that cannot move exactly one partition, because the dimension they
#: touch is read by several. Deadline changes move the timing bucket *and* how many
#: days remain, which changes eligibility at the gate. Funding and eligibility
#: evidence changes move the eligibility gate, which moves three partitions.
INTERACTING_CHANGES: frozenset[str] = frozenset(
    {CHANGE_DEADLINE, CHANGE_ELIGIBILITY, CHANGE_FUNDING, CHANGE_FIELD}
)

#: Which partition each simple change kind is confined to.
LOCAL_PARTITION_FOR: dict[str, str] = {
    CHANGE_NEW: "eligibility",
    CHANGE_MODIFIED: "eligibility",
    CHANGE_ARCHIVED: "eligibility",
    CHANGE_REMOVED: "eligibility",
}


@dataclass(frozen=True)
class IncrementPlan:
    """What a set of changes implies for the counting strategy."""

    strategy: str
    updated_partitions: tuple[str, ...]
    recomputed_partitions: tuple[str, ...]
    increments: tuple[CountIncrement, ...]
    note: str


def classify_increment(
    change_type: str, scholarship_id: int, detail: str = ""
) -> CountIncrement:
    """Label one change, deciding whether it can be applied to a running count.

    A change touching a dimension read by more than one partition is marked for
    full recomputation, with the reason recorded. It is not applied optimistically
    and then corrected later.
    """
    if change_type in INTERACTING_CHANGES:
        return CountIncrement(
            change_type=change_type,
            scholarship_id=scholarship_id,
            detail=detail,
            requires_full_recompute=True,
            reason=(
                f"{change_type} is read by more than one partition, and the "
                "partitions do not move independently. Recomputed."
            ),
        )
    return CountIncrement(
        change_type=change_type,
        scholarship_id=scholarship_id,
        detail=detail,
        requires_full_recompute=False,
        reason="",
    )


def plan_increments(
    changes: Iterable[tuple[str, int, str]],
    *,
    partitions: Sequence[str],
) -> IncrementPlan:
    """Plan how to move from one count set to the next.

    Incremental only when every change is local *and* there is exactly one: a batch
    of changes is recomputed, because the interaction between them cannot be ruled
    out without inspecting each one, and a batch is exactly where that reasoning
    gets expensive.
    """
    classified = tuple(
        classify_increment(change_type, scholarship_id, detail)
        for change_type, scholarship_id, detail in changes
    )

    local = [item for item in classified if not item.requires_full_recompute]
    interactive = [item for item in classified if item.requires_full_recompute]

    if not classified:
        return IncrementPlan(
            strategy=STRATEGY_FULL_RECOMPUTE,
            updated_partitions=(),
            recomputed_partitions=tuple(partitions),
            increments=(),
            note="No changes supplied, so nothing is asserted about the previous counts.",
        )

    if len(classified) > 1 or interactive:
        reasons = sorted({item.reason for item in interactive if item.reason})
        note = (
            "Multiple interacting changes, so every partition is recomputed. "
            + " ".join(reasons)
        ) if interactive else (
            "More than one change, so every partition is recomputed. A batch is where "
            "interactions between changes become possible, and ruling them out per "
            "partition costs more than recomputing."
        )
        return IncrementPlan(
            strategy=STRATEGY_FULL_RECOMPUTE,
            updated_partitions=(),
            recomputed_partitions=tuple(partitions),
            increments=classified,
            note=note,
        )

    changed_partition = LOCAL_PARTITION_FOR.get(classified[0].change_type)
    if changed_partition is None:
        return IncrementPlan(
            strategy=STRATEGY_FULL_RECOMPUTE,
            updated_partitions=(),
            recomputed_partitions=tuple(partitions),
            increments=classified,
            note=f"Unknown change kind {classified[0].change_type!r}; recomputed.",
        )

    return IncrementPlan(
        strategy=STRATEGY_INCREMENTAL,
        updated_partitions=(changed_partition,),
        recomputed_partitions=tuple(name for name in partitions if name != changed_partition),
        increments=classified,
        note=(
            f"A single {classified[0].change_type} is confined to the "
            f"{changed_partition} partition, so it can be applied without recomputing "
            "the others."
        ),
    )


def apply_plan(plan: IncrementPlan, recomputed_summary: dict | None = None) -> IncrementalOutcome:
    """Materialise a plan into a published outcome.

    ``recomputed_summary`` is required whenever anything is recomputed. Without it
    the outcome would report partitions as recomputed while publishing no numbers,
    which is the least useful thing this layer could do.
    """
    if plan.recomputed_partitions and recomputed_summary is None:
        raise ValueError(
            "a plan that recomputes partitions must be given the recomputed summary; "
            "reporting a recomputation without its figures publishes nothing"
        )

    return IncrementalOutcome(
        strategy=plan.strategy,
        updated_partitions=list(plan.updated_partitions),
        recomputed_partitions=list(plan.recomputed_partitions),
        increments=list(plan.increments),
        recomputed_summary=recomputed_summary,
        note=plan.note,
    )


__all__ = [
    "CHANGE_ARCHIVED",
    "CHANGE_DEADLINE",
    "CHANGE_ELIGIBILITY",
    "CHANGE_FIELD",
    "CHANGE_FUNDING",
    "CHANGE_MODIFIED",
    "CHANGE_NEW",
    "CHANGE_REMOVED",
    "INTERACTING_CHANGES",
    "IncrementPlan",
    "STRATEGY_FULL_RECOMPUTE",
    "STRATEGY_INCREMENTAL",
    "apply_plan",
    "classify_increment",
    "plan_increments",
]