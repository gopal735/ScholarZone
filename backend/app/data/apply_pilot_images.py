"""DEPRECATED: Apply pilot scholarship images to the database.

This script used hand-authored image URLs that have been proven unreliable
(see dry-run pilot results). It has been DEPRECATED.

The evidence-driven pipeline in app/services/image_discovery.py and
app/services/image_validator.py now handles automatic discovery and
validation of official scholarship images.

Use app/data/dry_run_pilot.py for read-only validation before any database writes.
DO NOT run this script — it will refuse to execute.
"""

import sys


def apply_pilot_images() -> int:
    """Refuse to apply deprecated hand-authored image data."""
    raise RuntimeError(
        "apply_pilot_images is DEPRECATED. The pilot image URLs have been "
        "proven unreliable (404/403 errors, generic banners, no licensing). "
        "Use the evidence-driven pipeline in app/services/image_discovery.py "
        "and app/data/dry_run_pilot.py instead."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = apply_pilot_images()
    print(f"Updated {count} scholarships with pilot images")
    sys.exit(0)
