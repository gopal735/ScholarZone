"""
ScholarZone Production Purge Preflight Gates

This package provides the complete preflight verification system for
production scholarship purge operations.

Gates:
1. Atomicity and Rollback - Tests transaction behavior with disposable DB
2. Production Identity - Verifies exact Neon project/branch/database identity
3. Dependencies - Inspects all FK references to scholarships.id
4. Backup & Restore - Creates encrypted backup, verifies restore
5. Classification - Validates target ID categorization
6. Cycle Validation - Verifies application cycle expiration
7. Git Safety - Verifies worktree isolation and change scope

All modules are import-safe: no database connections, no subprocess calls,
no sys.exit() at import time.
"""

from .manifest import (
    CANONICAL_TARGET_IDS,
    TARGET_ID_SET,
    validate_manifest,
    TargetRecord,
    ClassificationCategory,
)

from .config import (
    PreflightConfig,
    load_config,
    GateConfig,
)

__all__ = [
    "CANONICAL_TARGET_IDS",
    "TARGET_ID_SET",
    "validate_manifest",
    "TargetRecord",
    "ClassificationCategory",
    "PreflightConfig",
    "load_config",
    "GateConfig",
]