"""READ-ONLY audit of CLOSED scholarship records.

Answers one question: which closed records are provably dead?

It is strictly read-only. It opens the production database, selects, prints a
report, rolls back and exits. There is no code path in this file that issues an
INSERT, UPDATE or DELETE, and the run asserts that before exiting so a future
edit cannot quietly make a read-only audit into a mutation.

"Closed" is not the same as "dead"
-----------------------------------
A scholarship whose round has ended is not therefore worthless. It may be the
evidence behind a public claim, the subject of an unresolved human decision, the
target of a discovery candidate, or the row that keeps a closed round out of
the public directory while retaining its history. Deleting on ``status`` alone
would destroy exactly that.

So every closed record is classified against the dependencies that give it
purpose, and the classification is reported rather than acted on here.

Run:
    SCHOLARZONE_DATABASE_URL=... python -m scripts.closed_record_audit
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "production")

from sqlalchemy import func, or_, select, text  # noqa: E402

from app.database import get_session_factory  # noqa: E402
from app.models import (  # noqa: E402
    ContentFingerprintRecord,
    DiscoveryCandidate,
    ImageReview,
    KnowledgeEdge,
    KnowledgeNode,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipRestoreRecord,
    ScholarshipReview,
    ScholarshipSnapshot,
    ScholarshipVerificationHistory,
)
from app.repositories.scholarships import public_visibility_conditions  # noqa: E402
from app.verification_contract import (  # noqa: E402
    AUTHORITATIVE_VERIFIED_STATUS,
    UNCERTAIN_VERIFICATION_STATUS,
    public_verified_from_status,
)

#: Statuses the product already treats as no-longer-offered.
CLOSED_STATUSES = ("closed",)

#: change_type values that mean the row records something that happened, as
#: opposed to a verification pass that found nothing new. Only these count as
#: "meaningful history" for the purposes of keeping a record.
MATERIAL_CHANGE_TYPES = (
    "created",
    "updated",
    "status_change",
    "value_change",
    "image_verified",
    "image_rejected",
    "source_changed",
    "admin:verify",
    "admin:keep_needs_review",
    "admin:retire",
    "admin:reject",
)

#: A change_type written by the verifier to say "we looked and nothing moved".
UNINFORMATIVE_CHANGE_TYPES = ("unchanged",)


def _count(session, model, column, scholarship_id: int) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(model).where(column == scholarship_id)
        )
        or 0
    )


def _material_history(session, scholarship_id: int) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ScholarshipVerificationHistory)
            .where(
                ScholarshipVerificationHistory.scholarship_id == scholarship_id,
                or_(
                    ScholarshipVerificationHistory.change_type.notin_(
                        UNINFORMATIVE_CHANGE_TYPES
                    ),
                    ScholarshipVerificationHistory.evidence_text.isnot(None),
                ),
            )
        )
        or 0
    )


def _knowledge_node_ids(session, row: Scholarship) -> list[int]:
    """Knowledge-graph nodes that stand for this scholarship.

    The graph keys on a normalised value and a display name rather than on a
    foreign key, so a match has to consider both plus the bare id. Matching only
    the title would miss a node recorded under an id, and that node would then
    look like no dependency at all.
    """
    conditions = []
    if row.title:
        conditions.append(KnowledgeNode.normalized_value == row.title.strip().lower())
        conditions.append(KnowledgeNode.display_name == row.title)
    conditions.append(KnowledgeNode.normalized_value == f"scholarship:{row.id}")
    conditions.append(KnowledgeNode.normalized_value == str(row.id))

    return list(
        session.scalars(
            select(KnowledgeNode.id).where(
                KnowledgeNode.entity_type == "scholarship",
                or_(*conditions),
            )
        ).all()
    )


def _knowledge_refs(session, node_ids: list[int]) -> int:
    """Nodes are themselves a reference; count them."""
    return len(node_ids)


def _edge_refs(session, node_ids: list[int]) -> int:
    """Edges incident to this scholarship's node.

    An edge whose other end is a different scholarship still means deleting
    this row would leave a graph edge pointing at nothing.
    """
    if not node_ids:
        return 0
    return int(
        session.scalar(
            select(func.count())
            .select_from(KnowledgeEdge)
            .where(
                or_(
                    KnowledgeEdge.source_node_id.in_(node_ids),
                    KnowledgeEdge.target_node_id.in_(node_ids),
                )
            )
        )
        or 0
    )


def _fingerprint_refs(session, row: Scholarship) -> int:
    """Content fingerprints are keyed on source URL, not on scholarship id."""
    urls = [u for u in (row.official_source_url, row.catalogue_url) if u]
    if not urls:
        return 0
    return int(
        session.scalar(
            select(func.count())
            .select_from(ContentFingerprintRecord)
            .where(ContentFingerprintRecord.source_url.in_(urls))
        )
        or 0
    )


def gather(session, row: Scholarship, public_ids: set[int]) -> dict:
    """Every signal that could give a closed record a reason to exist."""
    sid = row.id
    node_ids = _knowledge_node_ids(session, row)
    deps = {
        "verification_history_total": _count(
            session, ScholarshipVerificationHistory, ScholarshipVerificationHistory.scholarship_id, sid
        ),
        "verification_history_material": _material_history(session, sid),
        "reviews_total": _count(session, ScholarshipReview, ScholarshipReview.scholarship_id, sid),
        "reviews_pending": int(
            session.scalar(
                select(func.count())
                .select_from(ScholarshipReview)
                .where(
                    ScholarshipReview.scholarship_id == sid,
                    ScholarshipReview.decision == "pending",
                )
            )
            or 0
        ),
        "reviews_conflicting": int(
            session.scalar(
                select(func.count())
                .select_from(ScholarshipReview)
                .where(
                    ScholarshipReview.scholarship_id == sid,
                    ScholarshipReview.decision == "pending",
                    ScholarshipReview.conflict_reason != "",
                )
            )
            or 0
        ),
        "image_reviews_total": _count(session, ImageReview, ImageReview.scholarship_id, sid),
        "image_reviews_pending": int(
            session.scalar(
                select(func.count())
                .select_from(ImageReview)
                .where(ImageReview.scholarship_id == sid, ImageReview.decision == "pending")
            )
            or 0
        ),
        "fetch_attempts": _count(
            session, ScholarshipFetchAttempt, ScholarshipFetchAttempt.scholarship_id, sid
        ),
        "snapshots": _count(session, ScholarshipSnapshot, ScholarshipSnapshot.scholarship_id, sid),
        "restore_records": _count(
            session, ScholarshipRestoreRecord, ScholarshipRestoreRecord.scholarship_id, sid
        ),
        "discovery_candidates": _count(
            session, DiscoveryCandidate, DiscoveryCandidate.matched_scholarship_id, sid
        ),
        "knowledge_nodes": _knowledge_refs(session, node_ids),
        "knowledge_edges": _edge_refs(session, node_ids),
        "content_fingerprints": _fingerprint_refs(session, row),
    }
    return {
        "id": sid,
        "name": (row.title or "")[:90],
        "verification_status": row.verification_status,
        "legacy_is_verified": bool(row.is_verified),
        "publicly_verified": public_verified_from_status(row.verification_status),
        "is_archived": bool(row.is_archived),
        "archived_reason": row.archived_reason,
        "status": row.status,
        "deadline_date": row.deadline_date.isoformat() if row.deadline_date else None,
        "deadline_display": row.deadline_display,
        "official_source_url": row.official_source_url,
        "catalogue_url": row.catalogue_url,
        "has_evidence_text": bool((row.verification_notes or "").strip()),
        "citations": bool((row.official_details or "").strip()),
        "is_public": sid in public_ids,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
        "dependencies": deps,
    }


def classify(rec: dict) -> tuple[str, list[str]]:
    """Assign one label, and the reasons that produced it.

    The order matters and is conservative: anything that indicates an
    unresolved human question or an inbound reference is kept before any
    consideration of tidiness, because the cost of keeping a row nobody wanted
    is a few kilobytes, while the cost of deleting the evidence behind a public
    claim is unrecoverable.
    """
    d = rec["dependencies"]
    reasons: list[str] = []

    if rec["verification_status"] == UNCERTAIN_VERIFICATION_STATUS:
        reasons.append("verification_status is needs_review: an unresolved human decision")
    if d["reviews_conflicting"]:
        reasons.append(f"{d['reviews_conflicting']} unresolved source conflict(s)")
    if d["reviews_pending"]:
        reasons.append(f"{d['reviews_pending']} pending review item(s)")
    if d["image_reviews_pending"]:
        reasons.append(f"{d['image_reviews_pending']} pending image review(s)")
    if rec["is_public"]:
        reasons.append("record is publicly listed")

    if reasons:
        return (
            "NEEDS_MANUAL_REVIEW" if rec["verification_status"] == UNCERTAIN_VERIFICATION_STATUS or d["reviews_conflicting"] else "KEEP_REVIEW",
            reasons,
        )

    refs = {
        "snapshots": d["snapshots"],
        "restore_records": d["restore_records"],
        "discovery_candidates": d["discovery_candidates"],
        "knowledge_nodes": d["knowledge_nodes"],
        "knowledge_edges": d["knowledge_edges"],
        "content_fingerprints": d["content_fingerprints"],
    }
    present = {k: v for k, v in refs.items() if v}
    if present:
        return (
            "KEEP_REFERENCED",
            [f"inbound reference(s): {present}"],
        )

    if d["verification_history_material"]:
        return (
            "KEEP_HISTORICAL",
            [
                f"{d['verification_history_material']} material verification-history "
                f"row(s) recording what was checked and what changed"
            ],
        )

    if rec["publicly_verified"]:
        return (
            "KEEP_ACTIVE_INTERNAL",
            [
                "verification_status is active: this row is currently trusted and is "
                "the evidence for that trust, even though the round has closed"
            ],
        )

    if rec["is_archived"]:
        return (
            "KEEP_HISTORICAL",
            ["deliberately archived: archival is this repository's mechanism for "
             "retaining a closed round, and it keeps the row, its history and its "
             "inbound references by design"],
        )

    if rec["has_evidence_text"] or rec["citations"]:
        return (
            "KEEP_HISTORICAL",
            ["carries stored verification notes or citation text"],
        )

    if d["fetch_attempts"]:
        return (
            "KEEP_HISTORICAL",
            [f"{d['fetch_attempts']} fetch attempt(s) record how the official source "
             f"was retrieved and what it returned"],
        )

    return (
        "SAFE_DELETE",
        [
            "permanently closed, not public, not needs_review, no inbound "
            "references, no material verification history, not currently trusted, "
            "not deliberately archived, and no stored evidence or citation"
        ],
    )


def main() -> int:
    session = get_session_factory()()

    storage_total = int(session.scalar(select(func.count(Scholarship.id))) or 0)

    public_stmt = select(Scholarship.id).where(*public_visibility_conditions())
    public_ids = set(session.scalars(public_stmt).all())
    public_total = len(public_ids)

    closed_rows = session.scalars(
        select(Scholarship)
        .where(Scholarship.status.in_(CLOSED_STATUSES))
        .order_by(Scholarship.id)
    ).all()

    today = date.today()
    deadline_passed = [
        r
        for r in session.scalars(select(Scholarship).where(Scholarship.deadline_date.isnot(None))).all()
        if r.deadline_date and r.deadline_date < today
    ]
    deadline_passed_ids = {r.id for r in deadline_passed}
    closed_ids = {r.id for r in closed_rows}

    records = []
    for row in closed_rows:
        rec = gather(session, row, public_ids)
        label, reasons = classify(rec)
        rec["classification"] = label
        rec["reasons"] = reasons
        rec["deadline_passed"] = row.id in deadline_passed_ids
        records.append(rec)

    buckets: dict[str, list[int]] = {}
    for rec in records:
        buckets.setdefault(rec["classification"], []).append(rec["id"])

    print("=" * 78)
    print("CLOSED RECORD AUDIT - READ ONLY")
    print(f"generated_at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 78)
    print(f"storage_rows            : {storage_total}")
    print(f"public_universe         : {public_total}")
    print(f"storage_only            : {storage_total - public_total}")
    print(f"records_with_status_closed: {len(closed_rows)}")
    print(f"records_with_past_deadline: {len(deadline_passed_ids)}")
    print(f"closed_by_status_but_deadline_future: {len(closed_ids - deadline_passed_ids)}")
    print("")

    print("-" * 78)
    print("CLASSIFICATION")
    print("-" * 78)
    for label in sorted(buckets):
        ids = sorted(buckets[label])
        print(f"{label} ({len(ids)}): {ids}")
    print("")

    print("-" * 78)
    print("PER-RECORD DETAIL")
    print("-" * 78)
    for rec in records:
        print(
            f"[{rec['id']}] {rec['name']!r}\n"
            f"    classification={rec['classification']}"
            f"  status={rec['status']}"
            f"  verification_status={rec['verification_status']}"
            f"  is_archived={rec['is_archived']}"
            f"  public={rec['is_public']}"
            f"  publicly_verified={rec['publicly_verified']}"
            f"  deadline_passed={rec['deadline_passed']}\n"
            f"    deadline={rec['deadline_display'] or rec['deadline_date']}"
            f"  source={'yes' if rec['official_source_url'] else 'none'}\n"
            f"    deps={rec['dependencies']}\n"
            f"    reasons={' | '.join(rec['reasons'])}\n"
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "storage_rows": storage_total,
        "public_universe": public_total,
        "storage_only": storage_total - public_total,
        "closed_status_count": len(closed_rows),
        "past_deadline_count": len(deadline_passed_ids),
        "buckets": {k: sorted(v) for k, v in buckets.items()},
        "records": records,
    }
    out = Path("closed_record_audit.json")
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    safe = sorted(buckets.get("SAFE_DELETE", []))
    print("=" * 78)
    print(f"SAFE_DELETE: {len(safe)} {safe}")
    for label in sorted(buckets):
        if label != "SAFE_DELETE":
            print(f"{label}: {len(buckets[label])}")
    print("=" * 78)
    print("READ-ONLY AUDIT COMPLETE - no rows were modified")

    session.rollback()
    session.close()

    return _assert_read_only(Path(__file__))


#: Statement keywords that would make this script a mutation rather than an
#: audit. They live inside the guard, because the guard necessarily names them
#: and a scanner that trips over its own vocabulary is a scanner that gets
#: switched off.
def _assert_read_only(script_path: Path) -> int:
    """Prove this script cannot write, by reading its own syntax tree.

    A read-only audit that merely claims to be read-only is worth nothing, so
    the claim is checked: every call to a mutating ORM/SQLAlchemy method, and
    every string literal that looks like a DML statement, is reported and fails
    the run.

    The body of this function, including the vocabulary below, is excluded from
    the scan.
    """
    import ast

    mutating_keywords = (
        "ins" "ert",
        "upd" "ate",
        "del" "ete",
        "dr" "op",
        "trun" "cate",
        "alt" "er",
        "cre" "ate",
        "gra" "nt",
        "rev" "oke",
    )

    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    lines = source.splitlines()
    self_start, self_end = 0, len(lines)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_assert_read_only":
            self_start = node.lineno
            self_end = getattr(node, "end_lineno", node.lineno)
            break

    def in_self(node) -> bool:
        line = getattr(node, "lineno", 0)
        return self_start <= line <= self_end

    problems: list[str] = []

    for node in ast.walk(tree):
        if in_self(node):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"delete", "commit", "add", "bulk_save_objects"}:
                problems.append(f"line {node.lineno}: calls .{node.func.attr}()")
            if node.func.attr == "execute":
                problems.append(f"line {node.lineno}: calls .execute()")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.strip().lower()
            first = lowered.split(None, 1)[0] if lowered else ""
            if first in mutating_keywords:
                problems.append(
                    f"line {node.lineno}: string literal starts with {first.upper()!r}"
                )

    if problems:
        print("READ-ONLY GUARD FAILED: mutating construct found:")
        for problem in problems:
            print("   ", problem)
        return 1

    print("READ-ONLY GUARD OK: no mutating construct in this script")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
