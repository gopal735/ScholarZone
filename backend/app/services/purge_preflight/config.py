"""
Configuration management for Purge Preflight Gates.

All configuration is loaded from environment variables with clear
validation and no silent defaults for production-critical values.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class GateConfig:
    """Configuration for a single gate execution."""
    enabled: bool = True
    timeout_seconds: int = 300
    require_evidence: bool = True


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection configuration."""
    # Read-only connection for Gates 2, 3, 5, 6
    readonly_url: str
    # Backup role connection for Gate 4
    backup_url: str
    # Expected production identity (MANDATORY - no defaults)
    expected_neon_project_id: str
    expected_neon_branch_id: str
    expected_neon_branch_name: str
    expected_database_name: str
    # Test database URL for Gate 1 (MUST be disposable)
    test_url: Optional[str] = None


@dataclass(frozen=True)
class GPGConfig:
    """GPG encryption configuration."""
    recipient: str
    expected_fingerprint: str  # Full 40-char fingerprint, pinned


@dataclass(frozen=True)
class PreflightConfig:
    """Complete preflight configuration."""
    database: DatabaseConfig
    gpg: GPGConfig
    gates: dict[str, GateConfig] = field(default_factory=dict)
    artifact_retention_days: int = 30

    @classmethod
    def from_env(cls) -> "PreflightConfig":
        """Load configuration from environment variables.

        Required environment variables:
        - SCHOLARZONE_DATABASE_URL_RO: Read-only production connection
        - SCHOLARZONE_DATABASE_URL_BACKUP: Backup role production connection
        - TEST_DATABASE_URL: Disposable test database (Gate 1 only)
        - EXPECTED_NEON_PROJECT_ID: Expected Neon project UUID
        - EXPECTED_NEON_BRANCH_ID: Expected Neon branch UUID
        - EXPECTED_NEON_BRANCH_NAME: Expected Neon branch name (e.g., "main")
        - EXPECTED_DATABASE_NAME: Expected database name
        - GPG_RECIPIENT: GPG key ID or email
        - GPG_EXPECTED_FINGERPRINT: Full 40-char GPG fingerprint

        Raises:
            ValueError: If any required variable is missing or invalid.
        """
        required = {
            "SCHOLARZONE_DATABASE_URL_RO": "Read-only database URL",
            "SCHOLARZONE_DATABASE_URL_BACKUP": "Backup role database URL",
            "EXPECTED_NEON_PROJECT_ID": "Expected Neon project ID",
            "EXPECTED_NEON_BRANCH_ID": "Expected Neon branch ID",
            "EXPECTED_NEON_BRANCH_NAME": "Expected Neon branch name",
            "EXPECTED_DATABASE_NAME": "Expected database name",
            "GPG_RECIPIENT": "GPG recipient",
            "GPG_EXPECTED_FINGERPRINT": "Expected GPG fingerprint",
        }

        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        # Validate fingerprint format (40 hex chars)
        fingerprint = os.getenv("GPG_EXPECTED_FINGERPRINT", "").strip()
        if len(fingerprint) != 40 or not all(c in "0123456789ABCDEFabcdef" for c in fingerprint):
            raise ValueError(f"GPG_EXPECTED_FINGERPRINT must be 40 hex characters, got: {fingerprint}")

        # Test database is optional (only for Gate 1)
        test_url = os.getenv("TEST_DATABASE_URL")

        db_config = DatabaseConfig(
            readonly_url=os.getenv("SCHOLARZONE_DATABASE_URL_RO"),
            backup_url=os.getenv("SCHOLARZONE_DATABASE_URL_BACKUP"),
            test_url=test_url,
            expected_neon_project_id=os.getenv("EXPECTED_NEON_PROJECT_ID"),
            expected_neon_branch_id=os.getenv("EXPECTED_NEON_BRANCH_ID"),
            expected_neon_branch_name=os.getenv("EXPECTED_NEON_BRANCH_NAME"),
            expected_database_name=os.getenv("EXPECTED_DATABASE_NAME"),
        )

        gpg_config = GPGConfig(
            recipient=os.getenv("GPG_RECIPIENT"),
            expected_fingerprint=fingerprint.upper(),
        )

        # Gate configs with defaults
        gates = {
            "gate1": GateConfig(enabled=True, timeout_seconds=120),
            "gate2": GateConfig(enabled=True, timeout_seconds=60),
            "gate3": GateConfig(enabled=True, timeout_seconds=60),
            "gate4": GateConfig(enabled=True, timeout_seconds=600),
            "gate5": GateConfig(enabled=True, timeout_seconds=60),
            "gate6": GateConfig(enabled=True, timeout_seconds=60),
            "gate7": GateConfig(enabled=True, timeout_seconds=60),
        }

        return cls(
            database=db_config,
            gpg=gpg_config,
            gates=gates,
            artifact_retention_days=int(os.getenv("ARTIFACT_RETENTION_DAYS", "30")),
        )


def load_config() -> PreflightConfig:
    """Load and validate configuration from environment."""
    return PreflightConfig.from_env()