#!/usr/bin/env python3
"""Verify presence of required production environment variable NAMES (not values)."""

import os
import sys

REQUIRED_VARS = [
    "SCHOLARZONE_DATABASE_URL",
]

PRODUCTION_REQUIRED_VARS = [
    "SCHOLARZONE_DATABASE_URL",
    "SCHOLARZONE_VERIFICATION_SECRET",
    "SCHOLARZONE_ADMIN_SECRET",
    "SCHOLARZONE_ENVIRONMENT",
    "RESEND_API_KEY",
    "NOTIFICATION_EMAIL",
]

OPTIONAL_VARS = [
    "SCHOLARZONE_ALLOWED_ORIGINS",
    "SCHOLARZONE_VERIFICATION_SECRET",
    "SCHOLARZONE_ADMIN_SECRET",
    "RESEND_API_KEY",
    "NOTIFICATION_EMAIL",
]


def redact_url(url: str) -> str:
    if not url:
        return "not set"
    if url.startswith("postgresql://") or url.startswith("postgresql+"):
        return "postgresql://***"
    if url.startswith("sqlite"):
        return "sqlite:///:memory:" if ":memory:" in url else "sqlite:///***"
    return "***"


def main() -> int:
    env = os.environ.get("SCHOLARZONE_ENVIRONMENT", "").strip().lower()
    is_production = env == "production"

    if is_production:
        required = PRODUCTION_REQUIRED_VARS
        context = "PRODUCTION"
    else:
        required = []
        context = os.environ.get("SCHOLARZONE_ENVIRONMENT", "development/unknown")

    missing = []

    print(f"=== Context: {context} ===")
    print("=== Required Variables ===")
    for var in required:
        if os.environ.get(var):
            print(f"[SET] {var}")
        else:
            print(f"[MISSING] {var}")
            missing.append(var)

    if not is_production:
        db_url = os.environ.get("SCHOLARZONE_DATABASE_URL")
        if db_url:
            print(f"[SET] SCHOLARZONE_DATABASE_URL")
        else:
            print(f"[OPTIONAL] SCHOLARZONE_DATABASE_URL (will default to SQLite)")

    print("\n=== Optional Variables ===")
    for var in OPTIONAL_VARS:
        if os.environ.get(var):
            print(f"[SET] {var}")
        else:
            print(f"[MISSING] {var}")

    db_url = os.environ.get("SCHOLARZONE_DATABASE_URL", "")
    if db_url:
        driver = db_url.split("://")[0] if "://" in db_url else "unknown"
        print(f"\nDatabase driver: {driver}")
        print(f"Database URL: {redact_url(db_url)}")
    else:
        print("\nDatabase URL: not set (will use default SQLite in non-production)")

    if env == "production" and db_url.startswith("sqlite"):
        print(
            "[FAIL] Production environment requires PostgreSQL, not SQLite"
        )
        missing.append("DATABASE_URL_DRIVER")

    if missing:
        print(f"\nMissing required variables: {', '.join(missing)}")
        return 1

    print(f"\nENV CONFIG: PASS ({context})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
