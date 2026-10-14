"""Run the local API against a chosen SQLite file.

Used for browser verification of the repaired detail pages without deploying
anything. The database is the rehearsal database the maintenance stage already
repaired, so what the browser shows is the real post-repair state.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = (HERE / "_repair_rehearsal.sqlite3").resolve()

os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"] = "false"
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"] = "false"
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_OFFICIAL_SOURCE"] = "false"
os.environ["SCHOLARZONE_LOG_LEVEL"] = "WARNING"

sys.path.insert(0, str(HERE.parent / "backend"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(sys.argv[1]) if len(sys.argv) > 1 else 8010,
        log_level="warning",
    )