"""
Configuration management for Purge Preflight Gates.

All configuration is loaded from environment variables with clear
validation and no silent defaults for production-critical values.

Each gate requires only the credentials and configuration it actually needs:
- Gate 1 (Atomicity): TEST_DATABASE_URL only (disposable test DB)
- Gate 2 (Identity): SCHOLARZONE_DATABASE_URL_RO + identity vars
- Gate 3 (Dependencies): SCHOLARZONE_DATABASE_URL_RO + identity vars
- Gate 4 (Backup): SCHOLARZONE_DATABASE_URL_BACKUP + GPG vars + RESTORE_TEST_* vars
- Gate 5 (Classification): SCHOLARZONE_DATABASE_URL_RO + identity vars
- Gate 6 (Cycle Validation): SCHOLARZONE_DATABASE_URL_RO + identity vars
- Gate 7 (Git Safety): No database config needed
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Set


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
    readonly_url: str = ""
    # Backup role connection for Gate 4
    backup_url: str = ""
    # Expected production identity (MANDATORY for production-connected gates)
    expected_neon_project_id: str = ""
    expected_neon_branch_id: str = ""
    expected_neon_branch_name: str = ""
    expected_database_name: str = ""
    # Test database URL for Gate 1 (MUST be disposable)
    test_url: Optional[str] = None


@dataclass(frozen=True)
class GPGConfig:
    """GPG encryption configuration."""
    recipient: str = ""
    expected_fingerprint: str = ""  # Full 40-char fingerprint, pinned


@dataclass(frozen=True)
class RestoreTestConfig:
    """Restore test database configuration (Gate 4 only)."""
    host: str = ""
    port: int = 5432
    user: str = ""
    password: str = ""


@dataclass(frozen=True)
class PreflightConfig:
    """Complete preflight configuration."""
    database: DatabaseConfig
    gpg: GPGConfig
    restore_test: RestoreTestConfig
    gates: dict[str, GateConfig] = field(default_factory=dict)
    artifact_retention_days: int = 30

    # Gate-specific required environment variables
    GATE_REQUIREMENTS = {
        "gate1": {"TEST_DATABASE_URL"},
        "gate2": {"SCHOLARZONE_DATABASE_URL_RO", "EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID", "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME"},
        "gate3": {"SCHOLARZONE_DATABASE_URL_RO", "EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID", "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME"},
        "gate4": {"SCHOLARZONE_DATABASE_URL_BACKUP", "GPG_RECIPIENT", "GPG_EXPECTED_FINGERPRINT", "RESTORE_TEST_PGHOST", "RESTORE_TEST_PGPORT", "RESTORE_TEST_PGUSER", "RESTORE_TEST_PGPASSWORD"},
        "gate5": {"SCHOLARZONE_DATABASE_URL_RO", "EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID", "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME"},
        "gate6": {"SCHOLARZONE_DATABASE_URL_RO", "EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID", "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME"},
        "gate7": set(),  # No environment variables required
    }

    @classmethod
    def _validate_fingerprint(cls, fingerprint: str) -> str:
        """Validate GPG fingerprint format (40 hex chars)."""
        fingerprint = fingerprint.strip()
        if len(fingerprint) != 40 or not all(c in "0123456789ABCDEFabcdef" for c in fingerprint):
            raise ValueError(f"GPG_EXPECTED_FINGERPRINT must be 40 hex characters, got: {fingerprint}")
        return fingerprint.upper()

    @classmethod
    def _get_required_vars(cls, gates_to_run: Optional[Set[str]] = None) -> Set[str]:
        """Get required environment variables for specified gates."""
        if gates_to_run is None:
            # All gates - union of all requirements
            required = set()
            for gate_reqs in cls.GATE_REQUIREMENTS.values():
                required.update(gate_reqs)
            return required
        required = set()
        for gate in gates_to_run:
            if gate in cls.GATE_REQUIREMENTS:
                required.update(cls.GATE_REQUIREMENTS[gate])
        return required

    @classmethod
    def from_env(cls, gates_to_run: Optional[Set[str]] = None) -> "PreflightConfig":
        """Load configuration from environment variables for specified gates.

        Args:
            gates_to_run: Set of gate names to load config for (e.g., {"gate1", "gate2"}).
                          If None, loads config for all gates.

        Required environment variables per gate:
        - Gate 1: TEST_DATABASE_URL
        - Gates 2,3,5,6: SCHOLARZONE_DATABASE_URL_RO, EXPECTED_NEON_PROJECT_ID, EXPECTED_NEON_BRANCH_ID,
                         EXPECTED_NEON_BRANCH_NAME, EXPECTED_DATABASE_NAME
        - Gate 4: SCHOLARZONE_DATABASE_URL_BACKUP, GPG_RECIPIENT, GPG_EXPECTED_FINGERPRINT,
                  RESTORE_TEST_PGHOST, RESTORE_TEST_PGPORT, RESTORE_TEST_PGUSER, RESTORE_TEST_PGPASSWORD
        - Gate 7: (none)

        Raises:
            ValueError: If any required variable for the specified gates is missing or invalid.
        """
        required_vars = cls._get_required_vars(gates_to_run)
        
        missing = [k for k in required_vars if not os.getenv(k)]
        if missing:
            raise ValueError(f"Missing required environment variables for gates {sorted(gates_to_run) if gates_to_run else 'all'}: {', '.join(sorted(missing))}")

        # Build database config with only required fields populated
        db_config = DatabaseConfig(
            readonly_url=os.getenv("SCHOLARZONE_DATABASE_URL_RO", ""),
            backup_url=os.getenv("SCHOLARZONE_DATABASE_URL_BACKUP", ""),
            test_url=os.getenv("TEST_DATABASE_URL"),
            expected_neon_project_id=os.getenv("EXPECTED_NEON_PROJECT_ID", ""),
            expected_neon_branch_id=os.getenv("EXPECTED_NEON_BRANCH_ID", ""),
            expected_neon_branch_name=os.getenv("EXPECTED_NEON_BRANCH_NAME", ""),
            expected_database_name=os.getenv("EXPECTED_DATABASE_NAME", ""),
        )

        # Build GPG config (only if Gate 4 is running)
        gpg_config = GPGConfig()
        if gates_to_run is None or "gate4" in gates_to_run:
            fingerprint = cls._validate_fingerprint(os.getenv("GPG_EXPECTED_FINGERPRINT", ""))
            gpg_config = GPGConfig(
                recipient=os.getenv("GPG_RECIPIENT", ""),
                expected_fingerprint=fingerprint,
            )

        # Build restore test config (only if Gate 4 is running)
        restore_test = RestoreTestConfig()
        if gates_to_run is None or "gate4" in gates_to_run:
            restore_test = RestoreTestConfig(
                host=os.getenv("RESTORE_TEST_PGHOST", ""),
                port=int(os.getenv("RESTORE_TEST_PGPORT", "5432")),
                user=os.getenv("RESTORE_TEST_PGUSER", ""),
                password=os.getenv("RESTORE_TEST_PGPASSWORD", ""),
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
            restore_test=restore_test,
            gates=gates,
            artifact_retention_days=int(os.getenv("ARTIFACT_RETENTION_DAYS", "30")),
        )


def load_config(gates_to_run: Optional[Set[str]] = None) -> PreflightConfig:
    """Load and validate configuration from environment for specified gates.
    
    Args:
        gates_to_run: Set of gate names to load config for. If None, loads all gates.
    """
    return PreflightConfig.from_env(gates_to_run)