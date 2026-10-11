"""Split the closed-record audit inventory into per-agent research chunks."""
import json
from pathlib import Path

AUDIT = Path(r"C:/Users/GopaL/AppData/Local/Temp/kilo/phase1-audit")
CHUNKS = AUDIT / "backend/research_output/publish/chunks"
CHUNKS.mkdir(parents=True, exist_ok=True)

audit = json.loads((AUDIT / "backend/research_output/publish/intake_audit_2026-10-11.json").read_text(encoding="utf-8"))
closed = audit["closed_records"]

# 12 agents, ~13 records each.
N = 12
chunks = [closed[i::N] for i in range(N)]
for index, chunk in enumerate(chunks, start=1):
    payload = {
        "_agent": f"agent-{index:02d}",
        "_task": "Verify each record's intake status against its official awarding-body page.",
        "_rules": [
            "Fetch the official page(s) listed in official_urls and official_source_url.",
            "Classify each record into exactly one bucket: upcoming/current intake; recurring/next intake expected; temporarily closed/awaiting announcement; genuinely discontinued; uncertain.",
            "Record for each record: the exact evidence URL(s) fetched, the exact wording on the page that establishes the status, the next deadline or window if published, what you verified, and a confidence 0-1.",
            "If every official URL fails or the page does not state the status, classify 'uncertain' and record the reason. Never guess a deadline, value, or status.",
        ],
        "records": chunk,
    }
    path = CHUNKS / f"agent_{index:02d}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path, len(chunk))
