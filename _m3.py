import pathlib, re, subprocess
f = pathlib.Path(r"C:\Users\GopaL\AppData\Local\Temp\sz_regress_wt\backend\app\jobs\scholarzone_maintenance.py")
orig = f.read_text(encoding="utf-8")

start = orig.index("def do_purge(")
end = orig.index("\n    def ", start + 10)
region = orig[start:end]
new_region, n = re.subn(
    r"from app\.services\.image_discovery_orchestrator import \((?:.|\n)*?\)",
    "from app.services.image_discovery_orchestrator import LOGO_IDENTITY_KINDS",
    region,
)
print(f"  substitutions in do_purge: {n}")
assert n == 1, "mutation did not apply - refusing to report"
mutated = orig[:start] + new_region + orig[end:]
assert "ACCEPTED_IMAGE_KINDS," not in new_region
f.write_text(mutated, encoding="utf-8")
print("  mutation verified applied")
