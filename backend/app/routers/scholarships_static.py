"""Static snapshot endpoint for free-first architecture.

Serves the version-controlled JSON snapshot when the database is unavailable.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter(prefix="/scholarships", tags=["scholarships-static"])

# Path to the version-controlled snapshot - resolve relative to this file
# This file is at: backend/app/routers/scholarships_static.py
# Project root is: backend/../../..
# Snapshot is at: frontend/public/scholarships-snapshot.json
ROUTER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(ROUTER_DIR)))
SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "frontend", "public", "scholarships-snapshot.json")


@router.get("/snapshot")
async def get_scholarship_snapshot():
    """Serve the full static scholarship snapshot.
    
    This endpoint exists as a fallback when the database is unavailable.
    The snapshot is generated from the local SQLite database and committed
    to version control. It contains all public scholarships (canonical
    visibility predicate: excludes closed, archived, quarantined).
    """
    if not os.path.exists(SNAPSHOT_PATH):
        raise HTTPException(
            status_code=503,
            detail="Static snapshot not available. Run generate_snapshot.py to create it."
        )
    
    return FileResponse(
        SNAPSHOT_PATH,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
    )


@router.get("/snapshot/stats")
async def get_scholarship_snapshot_stats():
    """Serve only the stats from the static snapshot."""
    if not os.path.exists(SNAPSHOT_PATH):
        raise HTTPException(
            status_code=503,
            detail="Static snapshot not available. Run generate_snapshot.py to create it."
        )
    
    import json
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    
    return {
        "stats": snapshot.get("stats", {}),
        "source": "snapshot",
        "snapshot_meta": snapshot.get("meta", {}),
    }