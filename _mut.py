import pathlib, subprocess, sys, re
f = pathlib.Path(r"C:\Users\GopaL\AppData\Local\Temp\sz_regress_wt\backend\app\jobs\scholarzone_maintenance.py")
backup = f.read_bytes()
orig = backup.decode("utf-8")

# locate do_stats and the orchestrator import inside it
m = re.search(r"(def do_stats\(\).*?)(from app\.services\.image_discovery_orchestrator import )([A-Z_, ]+)", orig, re.S)
if not m:
    print("  could not locate do_stats import -> aborting"); sys.exit(1)
print(f"  do_stats currently imports: {m.group(3).strip()!r}")

# reintroduce the original defect: stats imports only ACCEPTED_IMAGE_KINDS
broken = orig[:m.start(3)] + "ACCEPTED_IMAGE_KINDS" + orig[m.end(3):]
f.write_bytes(broken.encode("utf-8"))
check = f.read_text(encoding="utf-8")
print(f"  mutation applied: {'import ACCEPTED_IMAGE_KINDS' in check}")
sys.exit(0)
