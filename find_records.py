import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open(r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\research\wave4\wave4_final_mutation_manifest.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

for m in data:
    if m['scholarship_id'] in [412, 414, 600]:
        print(json.dumps(m, indent=2, ensure_ascii=False))
        print('---')