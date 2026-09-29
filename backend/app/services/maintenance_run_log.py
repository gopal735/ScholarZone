"""Persistent record of what each maintenance run actually did.

A scheduled job that only writes to stdout is not observable once the run
finishes: GitHub keeps build logs for weeks, then discards them, and there is
no answer to "when did enrichment last reach a new record?" or "has the nightly
run been quietly failing for a week?".

This writes one row per run into PostgreSQL. It is intentionally the smallest
thing that answers those questions - no framework, no external monitoring
service, no extra compute beyond a single INSERT and a single UPDATE.
"""

from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from ..models import MaintenanceRun

logger = logging.getLogger(__name__)

WORKER_VERSION = "maintenance/1.0"

STATUS_RUNNING = "running"
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

# A detail blob is JSON, so it must be JSON-serialisable. Stage reports carry
# per-record failure lists that can be long, so the payload is truncated to
# keep one run from writing a multi-megabyte row to the free database.
_MAX_LIST_ITEMS = 5
_MAX_ERROR_CHARS = 500


def _scrub(value: object, depth: int = 0) -> object:
    """Make a stage detail JSON-safe and small.

    Truncating matters for the free tier as much as for readability: the run
    table is written on every scheduled execution and an unbounded failure list
    would bloat the database for no diagnostic gain, since the full list is
    still in the workflow log.
    """
    if depth > 4:
        return "..."
    if isinstance(value, dict):
        return {str(k): _scrub(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        head = [_scrub(v, depth + 1) for v in list(value)[:_MAX_LIST_ITEMS]]
        if len(value) > _MAX_LIST_ITEMS:
            head.append(f"... {len(value) - _MAX_LIST_ITEMS} more")
        return head
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            # Defence in depth: this worker never puts a connection string in a
            # count, but the run table is permanent and a future stage that
            # reports a config error should not be able to persist a password
            # into the database where it outlives the log retention window.
            value = redact(value)
            if len(value) > _MAX_ERROR_CHARS:
                return value[:_MAX_ERROR_CHARS] + "..."
        return value
    return str(value)


@dataclass
class MaintenanceRunRecorder:
    """Collects a run's outcome and writes it once, at the end."""

    session_factory: sessionmaker[Session]
    run_id: str = field(default_factory=lambda: uuid4().hex[:16])
    worker: str = field(default_factory=lambda: f"{WORKER_VERSION}+{socket.gethostname()[:24]}")
    dry_run: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stages: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def record_stage(self, name: str, ok: bool, detail: dict, runtime_s: float, error: str | None) -> None:
        self.stages.append(
            {
                "name": name,
                "ok": ok,
                "runtime_s": round(runtime_s, 3),
                "detail": _scrub(detail or {}),
                "error": (error or None),
            }
        )
        if error:
            self.errors.append(f"{name}: {error}")

    def record_counts(self, values: dict) -> None:
        self.counts.update({k: v for k, v in values.items() if v is not None})

    def open(self) -> None:
        """Insert the run row up front so a hard crash still leaves a trace."""
        session = self.session_factory()
        try:
            session.add(
                MaintenanceRun(
                    run_id=self.run_id,
                    started_at=self.started_at,
                    worker=self.worker,
                    status=STATUS_RUNNING,
                    stages=[],
                    counts={},
                    dry_run=self.dry_run,
                )
            )
            session.commit()
        except Exception:  # noqa: BLE001 - observability must never mask the run
            logger.warning("could not open maintenance run record", exc_info=True)
            session.rollback()
        finally:
            session.close()

    def finish(self, status: str) -> None:
        finished = datetime.now(timezone.utc)
        duration_ms = (finished - self.started_at).total_seconds() * 1000.0
        session = self.session_factory()
        try:
            run = (
                session.query(MaintenanceRun)
                .filter(MaintenanceRun.run_id == self.run_id)
                .one_or_none()
            )
            if run is None:
                run = MaintenanceRun(run_id=self.run_id, started_at=self.started_at)
                session.add(run)
            run.finished_at = finished
            run.status = status
            run.stages = _scrub(self.stages)  # type: ignore[assignment]
            run.counts = _scrub(self.counts)  # type: ignore[assignment]
            summary = "\n".join(self.errors)
            run.error_summary = summary[:2000] if summary else None
            run.dry_run = self.dry_run
            run.duration_ms = duration_ms
            session.commit()
        except Exception:  # noqa: BLE001
            logger.warning("could not finalize maintenance run record", exc_info=True)
            session.rollback()
        finally:
            session.close()

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "worker": self.worker,
            "dry_run": self.dry_run,
            "stages": len(self.stages),
            "failed": sum(1 for s in self.stages if not s["ok"]),
        }


def recent_runs(session_factory: sessionmaker[Session], limit: int = 10) -> list[dict]:
    """Most recent runs, newest first. Used by the operational smoke checks."""
    session = session_factory()
    try:
        rows = (
            session.query(MaintenanceRun)
            .order_by(MaintenanceRun.started_at.desc())
            .limit(max(1, limit))
            .all()
        )
        return [
            {
                "run_id": r.run_id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "status": r.status,
                "dry_run": r.dry_run,
                "duration_ms": r.duration_ms,
                "stages": r.stages,
                "counts": r.counts,
                "error_summary": r.error_summary,
            }
            for r in rows
        ]
    finally:
        session.close()


def redact(value: str | None) -> str | None:
    """Last-resort guard for anything that reaches a log line.

    Connection strings are the only realistic secret this worker touches, and
    they are never printed intentionally. This exists so that if a future edit
    ever interpolates one, the credential part is gone before it is written.
    """
    if not value or "://" not in value:
        return value
    scheme, _, rest = value.partition("://")
    if "@" not in rest:
        return value
    _, _, host = rest.rpartition("@")
    return f"{scheme}://***:***@{host}"


def _unused_env_guard() -> None:  # pragma: no cover - documentation only
    """The worker reads no secrets; this exists to document that for reviewers.

    ``SCHOLARZONE_VERIFICATION_SECRET`` and ``SCHOLARZONE_ADMIN_SECRET`` are
    consumed exclusively by HTTP header guards in ``app/routers``. The worker
    imports no router and makes no HTTP call to the API, so the workflow does
    not pass them and this process never sees them.
    """
    for leaked in ("SCHOLARZONE_VERIFICATION_SECRET", "SCHOLARZONE_ADMIN_SECRET"):
        if os.getenv(leaked):  # pragma: no cover
            logger.info("%s is set but unused by this worker", leaked)
