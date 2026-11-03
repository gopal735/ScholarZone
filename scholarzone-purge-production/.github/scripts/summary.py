#!/usr/bin/env python3
"""
Summary script - generates final preflight report
"""

import os
import json
import subprocess
import sys
import datetime

print("=== PRODUCTION PURGE PREFLIGHT GATES SUMMARY ===")
print("")
print("Workflow: " + os.getenv("GITHUB_WORKFLOW", "unknown"))
print("Run: " + os.getenv("GITHUB_RUN_ID", "unknown"))
print("Trigger: " + os.getenv("GITHUB_EVENT_INPUTS_GATE", "unknown"))
print("Date: " + datetime.datetime.utcnow().isoformat() + "Z")
print("")

# Gate 2
if os.path.exists("artifacts/gate2_result.json"):
    print("=== GATE 2: PRODUCTION IDENTITY ===")
    with open("artifacts/gate2_result.json") as f:
        print(json.dumps(json.load(f), indent=2))
    print("")
else:
    print("=== GATE 2: SKIPPED ===")
    print("")

# Gate 3
if os.path.exists("artifacts/gate3_result.json"):
    print("=== GATE 3: DEPENDENCIES ===")
    with open("artifacts/gate3_result.json") as f:
        print(json.dumps(json.load(f), indent=2))
    print("")
else:
    print("=== GATE 3: SKIPPED ===")
    print("")

# Gate 4
if os.path.exists("artifacts/gate4_result.json"):
    print("=== GATE 4: BACKUP ===")
    with open("artifacts/gate4_result.json") as f:
        print(json.dumps(json.load(f), indent=2))
    print("")
else:
    print("=== GATE 4: SKIPPED ===")
    print("")

# Overall status
print("=== OVERALL STATUS ===")
if (os.path.exists("artifacts/gate2_result.json") and
    os.path.exists("artifacts/gate3_result.json") and
    os.path.exists("artifacts/gate4_result.json")):

    with open("artifacts/gate2_result.json") as f:
        gate2 = json.load(f)
    with open("artifacts/gate3_result.json") as f:
        gate3 = json.load(f)
    with open("artifacts/gate4_result.json") as f:
        gate4 = json.load(f)

    gate2_pass = gate2.get("all_present", False)
    gate3_pass = gate3.get("safe_to_delete", False)
    gate4_pass = gate4.get("backup_verified", False) and gate4.get("checksum_verified", False)

    print("Gate 2 (Identity): " + str(gate2_pass))
    print("Gate 3 (Dependencies): " + str(gate3_pass))
    print("Gate 4 (Backup): " + str(gate4_pass))

    if gate2_pass and gate3_pass and gate4_pass:
        print("")
        print("ALL GATES PASSED - Ready for production deletion approval")
    else:
        print("")
        print("SOME GATES FAILED - Review individual results")
else:
    print("Some gates were skipped")