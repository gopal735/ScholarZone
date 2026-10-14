import os
import secrets

# Generate a new strong secret
new_secret = secrets.token_hex(32)
print(f"Generated new verification secret (length={len(new_secret)})")
print(f"Secret prefix: {new_secret[:8]}***{new_secret[-8:]}")

# Read current .env
env_path = "C:\\Users\\GopaL\\Desktop\\Projects folder\\ScholarZone\\backend\\.env"
with open(env_path, "r") as f:
    content = f.read()

# Update the secret
lines = content.split("\n")
updated = False
for i, line in enumerate(lines):
    if line.startswith("SCHOLARZONE_VERIFICATION_SECRET="):
        lines[i] = f"SCHOLARZONE_VERIFICATION_SECRET={new_secret}"
        updated = True
        break

if not updated:
    lines.append(f"SCHOLARZONE_VERIFICATION_SECRET={new_secret}")

new_content = "\n".join(lines)
with open(env_path, "w") as f:
    f.write(new_content)

print(f"\nUpdated .env with new secret")
print(f"Verify the file was written:")

with open(env_path, "r") as f:
    for line in f:
        if "SECRET" in line:
            key = line.split("=")[0]
            val = line.split("=", 1)[1].strip()
            print(f"  {key}={val[:8]}***{val[-8:]}")

# Save the new secret for later use
with open("production_secret.txt", "w") as f:
    f.write(new_secret)
print(f"\nNew secret saved to production_secret.txt")
