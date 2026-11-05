#!/usr/bin/env python3
"""
Summary Generator CLI Wrapper

Thin wrapper that initializes configuration and invokes the core gate module.
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.purge_preflight.summary import main

if __name__ == "__main__":
    # Pass command line arguments to the core module
    artifacts_dir = sys.argv[1] if len(sys.argv) > 1 else "artifacts"
    commit_sha = sys.argv[2] if len(sys.argv) > 2 else ""
    raise SystemExit(main(artifacts_dir, commit_sha))