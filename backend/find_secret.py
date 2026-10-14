import os

# Check ALL files in the backend directory that could contain env vars
backend_dir = "C:\\Users\\GopaL\\Desktop\\Projects folder\\ScholarZone\\backend"
for root, dirs, files in os.walk(backend_dir):
    # Skip hidden directories and venv
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", ".venv", "venv")]
    for f in files:
        if f.endswith(".env") or f == ".env" or f.startswith("env") or "env" in f.lower() and f.endswith((".txt", ".cfg", ".ini", ".json")):
            fpath = os.path.join(root, f)
            print(f"=== {fpath} ===")
            with open(fpath, "r") as fh:
                for line in fh:
                    if "SECRET" in line.upper():
                        key = line.split("=")[0].strip()
                        val = line.split("=", 1)[1].strip()
                        print(f"  {key}={val}")
            print()

# Also check the root directory
root_dir = "C:\\Users\\GopaL\\Desktop\\Projects folder\\ScholarZone"
for root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")]
    for f in files:
        if f.startswith(".env") or (f.startswith("env") and f.endswith(".txt")):
            fpath = os.path.join(root, f)
            if fpath.endswith("backend\\.env"):
                continue  # Already checked
            print(f"=== {fpath} ===")
            with open(fpath, "r") as fh:
                content = fh.read()
                if "SCHOLARZONE_VERIFICATION_SECRET" in content:
                    for line in content.strip().split("\n"):
                        if "SECRET" in line.upper() and not line.strip().startswith("#"):
                            print(f"  {line}")
            print()
