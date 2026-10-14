import json

with open("dry_run_after_report.json", encoding="utf-8") as f:
    data = json.load(f)

for r in data["approved_details"]:
    print(f"\n=== Scholarship #{r['scholarship_id']}: {r['scholarship_title']}")
    print(f"Image: {r['image_url']}")
    for c in r["all_candidates_summary"]:
        if c["image_url"] == r["image_url"]:
            print(f"  Status: {c['status']}, Score: {c['relevance_score']}")
            ncs = c.get("non_content_signals", [])
            if ncs:
                print(f"  Non-content signals (total weight: {c.get('non_content_total_weight', 0)}):")
                for s in ncs:
                    print(f"    - {s['label']} (weight={s['weight']}, source={s['source']})")
            else:
                print(f"  Non-content signals: NONE")
