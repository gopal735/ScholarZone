"""Test the exact JASSO URLs from the latest dry-run."""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("SCHOLARZONE_DATABASE_URL", "sqlite:///scholarzone.db")
os.environ.setdefault("SCHOLARZONE_ENVIRONMENT", "test")

from app.services.image_validator import (
    ImageValidator,
    _detect_non_content_signals,
    _extract_url_parts,
    NON_CONTENT_REJECTION_THRESHOLD,
)
from app.services.image_discovery import ImageCandidate

TEST_URLS = [
    {
        "label": "#25 JASSO alumninetwork (latest dry-run URL)",
        "url": "https://www.jasso.go.jp/en/ryugaku/topicsbig/__icsFiles/afieldfile/2022/05/06/alumninetwork1032x477new_2.png",
        "page": "https://www.jasso.go.jp/en/ryugaku/",
    },
]

def main():
    for item in TEST_URLS:
        print(f"\n--- {item['label']} ---")
        print(f"URL: {item['url']}")

        candidate = ImageCandidate(
            image_url=item["url"],
            page_url=item["page"],
            discovery_method="manual",
            alt_text=None,
            html_context=None,
        )

        path, filename, full_scan = _extract_url_parts(item["url"])
        print(f"  filename = {filename}")
        print(f"  full_scan= {full_scan}")

        raw_signals = _detect_non_content_signals(candidate, width=None, height=None)
        print(f"  raw signals ({len(raw_signals)}):")
        total = 0.0
        for s in raw_signals:
            print(f"    - {s.label} (weight={s.weight}, source={s.source})")
            total += s.weight
        print(f"  raw total weight = {total}")

        validator = ImageValidator(seen_images={}, timeout=30.0)
        result = validator.validate_candidate(candidate)
        print(f"  status          = {result.status.value}")
        print(f"  confidence      = {result.confidence}")
        print(f"  non_content_total_weight = {result.non_content_total_weight}")
        print(f"  rejection_reasons = {result.rejection_reasons}")
        print(f"  relevance_score = {result.relevance_score}")

if __name__ == "__main__":
    main()
