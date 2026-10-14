# Drain the research wave into the database in one pass.

#   python research/drain.py wave1
#   python research/drain.py wave2

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
PY = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")
MERGER = {"wave1": "research/wave1/merge_wave.py", "wave2": "research/wave2/merge_wave2.py"}


def run(label, args, cwd=ROOT):
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True,
                            env={**os.environ, "SCHOLARZONE_ENVIRONMENT": "development"})
    out = (result.stdout or "") + (result.stderr or "")
    failed = result.returncode != 0 or "[FAILED]" in out or "FAILED STAGES" in out
    for line in out.splitlines():
        if any(k in line for k in ("applied ", "staged", "confirmations", "logo hosts", "problems",
                                   "rejected", "skipped", "would_add", "created", "updated",
                                   "attached", "records_still_without_logo", "confirmed",
                                   "logos_attached", "detail_blocks", "already_active", "error",
                                   "FAILED", "hidden")):
            print("   " + line.strip()[:170])
    if failed:
        # A stage that aborts on one record takes the whole batch with it, so this
        # must never pass silently between drains.
        print("   !!!! STEP FAILED — nothing from this step was applied")
        for line in out.splitlines()[-14:]:
            print("      " + line.strip()[:170])
    return 1 if failed else 0


def main():
    waves = sys.argv[1:] or ["wave1", "wave2", "wave3"]
    failed = 0
    for wave in waves:
        if wave == "wave3":
            run("merge wave3 logo overrides + apply", [PY, MERGER[wave], "--apply"])
            run("maintenance logos (pass 1)", [PY, "-m", "app.jobs.scholarzone_maintenance", "--stage", "logos"], BACKEND)
            run("maintenance logos (pass 2)", [PY, "-m", "app.jobs.scholarzone_maintenance", "--stage", "logos"], BACKEND)
            continue
        failed += run(f"merge {wave} + apply to backend/config", [PY, MERGER[wave], "--apply"])
        run("maintenance add", [PY, "-m", "app.jobs.scholarzone_maintenance", "--stage", "add"], BACKEND)
        run("maintenance reverify", [PY, "-m", "app.jobs.scholarzone_maintenance", "--stage", "reverify"], BACKEND)
        # Two passes on purpose: the first clears stored photos for hosts that have an
        # audited override, the second attaches the logo to the now-empty slot.
        run("maintenance logos (pass 1)", [PY, "-m", "app.jobs.scholarzone_maintenance", "--stage", "logos"], BACKEND)
        run("maintenance logos (pass 2)", [PY, "-m", "app.jobs.scholarzone_maintenance", "--stage", "logos"], BACKEND)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())