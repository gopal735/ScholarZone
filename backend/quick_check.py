import json

with open("dry_run_after_report.json", encoding="utf-8") as f:
    data = json.load(f)

approved = [r for r in data["approved_details"]]
print(f"Approved: {len(approved)}")
for r in approved:
    print(f"  #{r['scholarship_id']}: {r['scholarship_title']}")
    print(f"    Image: {r['image_url']}")
