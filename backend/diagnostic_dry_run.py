"""Explicit diagnostic: run known false-positive URLs through the actual validator.

This uses the EXACT same import path as run_dry_run_after.py to ensure
we are testing the same module instance that the 303 dry-run uses.
"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

# Reproduce exact imports used by run_dry_run_after.py
from app.services.image_validator import (
    ImageValidator,
    _detect_non_content_signals,
    _extract_url_parts,
    NON_CONTENT_REJECTION_THRESHOLD,
)
from app.services.image_discovery import ImageCandidate

TEST_URLS = [
    {
        "label": "#25 JASSO plazaheisei1032x477_3.png",
        "url": "https://www.jasso.go.jp/study/jwc/plazaheisei1032x477_3.png",
        "page": "https://www.jasso.go.jp/study/jwc/",
    },
    {
        "label": "#58 Brandeis wein.jpg",
        "url": "https://www.brandeis.edu/global/global1/images/wein.jpg",
        "page": "https://www.brandeis.edu/global/global1/",
    },
    {
        "label": "#240 JASSO plazaheisei1032x477_3.png (duplicate)",
        "url": "https://www.jasso.go.jp/study/jwc/plazaheisei1032x477_3.png",
        "page": "https://www.jasso.go.jp/study/jwc/",
    },
]

def main():
    print(f"Validator module: {ImageValidator.__module__}")
    print(f"Validator file: {sys.modules['app.services.image_validator'].__file__}")
    print(f"NON_CONTENT_REJECTION_THRESHOLD = {NON_CONTENT_REJECTION_THRESHOLD}")
    print("=" * 80)

    for item in TEST_URLS:
        print(f"\n--- {item['label']} ---")
        print(f"URL: {item['url']}")
        print(f"Page: {item['page']}")

        candidate = ImageCandidate(
            image_url=item["url"],
            page_url=item["page"],
            discovery_method="manual",
            alt_text=None,
            html_context=None,
        )

        # Inspect extracted parts
        path, filename, full_scan = _extract_url_parts(item["url"])
        print(f"  path     = {path}")
        print(f"  filename = {filename}")
        print(f"  full_scan= {full_scan}")

        # Run non-content detection standalone
        raw_signals = _detect_non_content_signals(candidate, width=None, height=None)
        print(f"  raw signals ({len(raw_signals)}):")
        total = 0.0
        for s in raw_signals:
            print(f"    - {s.label} (weight={s.weight}, source={s.source})")
            total += s.weight
        print(f"  raw total weight = {total}")

        # Run full validator
        validator = ImageValidator(seen_images={}, timeout=30.0)
        result = validator.validate_candidate(candidate)
        print(f"  is_reachable    = {result.is_reachable}")
        print(f"  http_status     = {result.http_status}")
        print(f"  content_type    = {result.content_type}")
        print(f"  is_valid_image  = {result.is_valid_image}")
        print(f"  width/height    = {result.width} / {result.height}")
        print(f"  non_content_signals ({len(result.non_content_signals)}):")
        for s in result.non_content_signals:
            print(f"    - {s.label} (weight={s.weight}, source={s.source})")
        print(f"  non_content_total_weight = {result.non_content_total_weight}")
        print(f"  status          = {result.status.value}")
        print(f"  confidence      = {result.confidence}")
        print(f"  rejection_reasons = {result.rejection_reasons}")
        print(f"  relevance_score = {result.relevance_score}")
        print("=" * 80)

if __name__ == "__main__":
    main()
