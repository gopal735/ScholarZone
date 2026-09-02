"""Thread-safe priority queue with deduplication for verification jobs."""

import heapq
import threading
from dataclasses import dataclass

from .scheduler_priority import PriorityScore


@dataclass(frozen=True)
class QueuedJob:
    scholarship_id: int
    source_url: str | None
    priority: PriorityScore

    @property
    def key(self) -> tuple[int, str | None]:
        return (self.scholarship_id, self.source_url)


class VerificationQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[tuple, int, QueuedJob]] = []
        self._enqueued: set[tuple[int, str | None]] = set()
        self._running: set[tuple[int, str | None]] = set()
        self._lock = threading.Lock()
        self._counter = 0

    def enqueue(self, job: QueuedJob) -> bool:
        with self._lock:
            if job.key in self._enqueued or job.key in self._running:
                return False
            self._counter += 1
            heapq.heappush(self._heap, (job.priority.to_sort_key(), self._counter, job))
            self._enqueued.add(job.key)
            return True

    def dequeue(self) -> QueuedJob | None:
        with self._lock:
            if not self._heap:
                return None
            _, _, job = heapq.heappop(self._heap)
            self._enqueued.discard(job.key)
            self._running.add(job.key)
            return job

    def mark_completed(self, job: QueuedJob) -> None:
        with self._lock:
            self._running.discard(job.key)

    def mark_failed(self, job: QueuedJob) -> None:
        with self._lock:
            self._running.discard(job.key)

    def is_enqueued(self, scholarship_id: int, source_url: str | None) -> bool:
        with self._lock:
            return (scholarship_id, source_url) in self._enqueued

    def is_running(self, scholarship_id: int, source_url: str | None) -> bool:
        with self._lock:
            return (scholarship_id, source_url) in self._running

    def is_active(self, scholarship_id: int, source_url: str | None) -> bool:
        with self._lock:
            key = (scholarship_id, source_url)
            return key in self._enqueued or key in self._running

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._heap)

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    def clear(self) -> list[QueuedJob]:
        with self._lock:
            jobs = [item[2] for item in self._heap]
            self._heap.clear()
            self._enqueued.clear()
            return jobs
