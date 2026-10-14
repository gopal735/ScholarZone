"""Diagnostic script: analyze rejection breakdown from optimized_dry_run_results.json."""

import json
from collections import Counter
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "optimized_dry_run_results.json"


def classify_failure(candidate: dict) -> str:
    if not candidate.get("is_valid_image"):
        return "retrieval"
    if not candidate.get("is_official_domain"):
        return "classification"
    if candidate.get("is_generic_image") or candidate.get("is_ui_asset"):
        return "quality"
    if candidate.get("status") == "rejected":
        return "relevance"
    return "classification"


def main():
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    summary = {
        "total_candidates": 0,
        "accepted": 0,
        "human_review": 0,
        "rejected": 0,
        "by_confidence": Counter(),
        "by_image_kind": Counter(),
        "by_failure_type": Counter(),
        "top_rejection_reasons": Counter(),
    }

    for entry in entries:
        sid = entry["scholarship_id"]
        title = entry["title"]
        print(f"\n{'='*80}")
        print(f"ID {sid}: {title}")
        print(f"Official Source: {entry['official_source_url']}")
        print(f"Classification: {entry['classification']}")
        print(f"Best candidate URL: {entry.get('best_candidate_url')}")
        print(f"Best candidate method: {entry.get('best_candidate_method')}")
        print(f"Status: {entry['status']}")
        print(f"Confidence: {entry['confidence']}")
        print(f"Image kind: {entry.get('image_kind')}")
        print(f"Rejection reasons: {entry.get('rejection_reasons', [])}")

        candidates = entry.get("all_candidates", [])
        if not candidates:
            print("  No candidates")
            continue

        # Use the first candidate as the "best" (they are sorted by priority)
        best = candidates[0]
        summary["total_candidates"] += len(candidates)
        summary["by_confidence"][best.get("confidence", "LOW")] += 1
        summary["by_image_kind"][best.get("image_kind") or "None"] += 1

        if best.get("status") == "approved":
            summary["accepted"] += 1
        elif best.get("status") == "human_review":
            summary["human_review"] += 1
        else:
            summary["rejected"] += 1

        failure_type = classify_failure(best)
        summary["by_failure_type"][failure_type] += 1

        for reason in best.get("rejection_reasons", []):
            summary["top_rejection_reasons"][reason] += 1

        print(f"\n  --- Detailed Breakdown ---")
        print(f"  Discovery tier/method: {best.get('discovery_method')} (fallback_level={best.get('fallback_level')})")
        print(f"  Source page: {best.get('page_url')}")
        img_domain = best.get("image_domain") or "N/A"
        print(f"  Image domain: {img_domain}")
        print(f"  Image URL: {best['image_url']}")
        print(f"  HTTP status: {best.get('http_status')}")
        print(f"  Content type: {best.get('content_type')}")
        dims = f"{best.get('width')}x{best.get('height')}" if best.get('width') and best.get('height') else "N/A"
        print(f"  Dimensions: {dims}")
        print(f"  Validator flags:")
        print(f"    is_valid_image: {best.get('is_valid_image')}")
        print(f"    is_official_domain: {best.get('is_official_domain')}")
        print(f"    is_generic_image: {best.get('is_generic_image')}")
        print(f"    is_ui_asset: {best.get('is_ui_asset')}")
        print(f"    relevance_score: {best.get('relevance_score')}")
        print(f"    confidence: {best.get('confidence')}")
        print(f"    status: {best.get('status')}")
        print(f"    image_kind: {best.get('image_kind')}")
        print(f"    rejection_reasons: {best.get('rejection_reasons', [])}")
        print(f"    failure_type: {failure_type}")

    print(f"\n{'='*80}")
    print("AGGREGATE SUMMARY (first candidate per scholarship)")
    print(f"Total scholarships: {len(entries)}")
    print(f"Total candidates: {summary['total_candidates']}")
    print(f"Accepted: {summary['accepted']}")
    print(f"Human Review: {summary['human_review']}")
    print(f"Rejected: {summary['rejected']}")
    print(f"By confidence: {dict(summary['by_confidence'])}")
    print(f"By image kind: {dict(summary['by_image_kind'])}")
    print(f"By failure type: {dict(summary['by_failure_type'])}")
    print(f"Top rejection reasons:")
    for reason, count in summary["top_rejection_reasons"].most_common(20):
        print(f"  {count}x {reason}")


if __name__ == "__main__":
    main()
