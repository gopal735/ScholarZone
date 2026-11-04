#!/usr/bin/env python3
"""
Gate 2 CLI Wrapper: Production Identity Verification

Thin wrapper that initializes configuration and invokes the core gate module.
"""

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.services.purge_preflight.gate2_identity import main

if __name__ == "__main__":
    raise SystemExit(main())