import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

COVERAGE_STATUSES = {
    "verified_supervisors", "no_verified_supervisor_found", "not_applicable",
    "needs_verification", "source_blocked", "source_requires_rendering", "search_pending",
}
RELATIONSHIP_TYPES = {
    "potential_supervisor", "program_faculty", "research_group", "program_relevant_faculty",
}
SOURCE_TYPES = {
    "official_university_profile", "official_department_page", "official_research_group",
    "official_programme_page", "official_institution_domain", "secondary_aggregator",
}

total_results = 0
files = sorted(glob.glob(os.path.join(OUT, "batch_*.json")))
stats = {
    "verified_supervisors": 0,
    "no_verified_supervisor_found": 0,
    "not_applicable": 0,
    "source_requires_rendering": 0,
    "source_blocked": 0,
    "needs_verification": 0,
    "search_pending": 0,
}
professors = 0
emails = 0
problems = []
sids = []

for path in files:
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        problems.append(f"{name}: INVALID JSON ({exc})")
        continue
    if not isinstance(data, list):
        problems.append(f"{name}: not a JSON array")
        continue
    for obj in data:
        total_results += 1
        sid = obj.get("scholarship_id")
        outcome = obj.get("outcome")
        if not isinstance(sid, int):
            problems.append(f"{name}: entry without int scholarship_id")
            continue
        sids.append(sid)
        if outcome not in COVERAGE_STATUSES:
            problems.append(f"{name}: scholarship {sid} bad outcome '{outcome}'")
            continue
        stats[outcome] += 1
        profs = obj.get("professors") or []
        if outcome == "verified_supervisors" and not profs:
            problems.append(f"{name}: scholarship {sid} verified but no professors")
        if outcome != "verified_supervisors" and profs:
            problems.append(f"{name}: scholarship {sid} outcome {outcome} with professors")
        for p in profs:
            professors += 1
            if not p.get("canonical_name"):
                problems.append(f"{name}: scholarship {sid} professor without name")
            if not p.get("official_profile_url", "").startswith("http"):
                problems.append(f"{name}: scholarship {sid} professor without profile URL")
            if p.get("relationship_type") not in RELATIONSHIP_TYPES:
                problems.append(f"{name}: scholarship {sid} bad relationship_type")
            if p.get("evidence_source_type") not in SOURCE_TYPES:
                problems.append(f"{name}: scholarship {sid} bad evidence_source_type")
            if not p.get("evidence_source_url", "").startswith("http"):
                problems.append(f"{name}: scholarship {sid} professor without evidence URL")
            em = p.get("official_email")
            if em:
                emails += 1
                if "@" not in em:
                    problems.append(f"{name}: scholarship {sid} malformed email {em!r}")

dupes = len(sids) - len(set(sids))
print(json.dumps({
    "files": len(files),
    "result_objects": total_results,
    "unique_scholarships": len(set(sids)),
    "duplicate_scholarship_entries": dupes,
    "professors_found": professors,
    "professors_with_email": emails,
    "outcomes": stats,
    "problems": len(problems),
}, indent=1))
for p in problems[:50]:
    print("[PROBLEM]", p)
if len(problems) > 50:
    print(f"... and {len(problems) - 50} more")
