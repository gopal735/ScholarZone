"""Configuration for the intelligent verification scheduler."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerConfig:
    max_workers: int = 4
    max_attempts_per_job: int = 5
    poll_interval_seconds: int = 300
    batch_size: int = 100
    shutdown_timeout_seconds: float = 30.0
    source_rate_limit_seconds: float = 1.0
    max_concurrent_per_source: int = 1

    staleness_weight: int = 3
    deadline_urgency_weight: int = 5
    change_frequency_weight: int = 2
    source_reliability_weight: int = 1
    retry_pending_weight: int = 4
    review_pending_weight: int = 3
    impact_weight: int = 2

    staleness_max_days: int = 365
    deadline_urgency_window_days: int = 60
    change_frequency_window_days: int = 180
    change_frequency_max_count: int = 10
