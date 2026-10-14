import json

with open("dry_run_after_report.json", encoding="utf-8") as f:
    data = json.load(f)

print("=== REMAINING APPROVED CANDIDATES ===")
for r in data["approved_details"]:
    print(f"\n--- Scholarship #{r['scholarship_id']}: {r['scholarship_title']} ---")
    print(f"Image: {r['image_url']}")
    print(f"Relevance: {r['relevance']}, Confidence: {r['confidence']}")
    print(f"Source: {r['source_resolution_type']}")
    for c in r["all_candidates_summary"]:
        if c["image_url"] == r["image_url"]:
            ncs = c.get("non_content_signals", [])
            weight = c.get("non_content_total_weight", 0)
            print(f"  Signals: total_weight={weight}")
            if ncs:
                for s in ncs:
                    print(f"    - {s['label']} (weight={s['weight']}, source={s['source']})")
            else:
                print(f"  No non-content signals detected")
            print(f"  Rejection reasons: {c.get('rejection_reasons', [])}")
            print(f"  Relevance score: {c['relevance_score']}")

# Also check human review
print("\n\n=== HUMAN REVIEW CANDIDATES ===")
for r in data["human_review_details"]:
    print(f"\n--- Scholarship #{r['scholarship_id']}: {r['scholarship_title']} ---")
    print(f"Image: {r['image_url']}")
    print(f"Relevance: {r['relevance']}, Confidence: {r['confidence']}")
    print(f"Rejection reasons: {r['rejection_reasons']}")
