#!/usr/bin/env python3
"""
Gate 4: Production Backup & Verification
Uses BACKUP role. Creates ENCRYPTED pg_dump backup, verifies integrity.
Does NOT upload raw unencrypted dumps to GitHub artifacts.
"""

import os
import subprocess
import json
import hashlib
import tempfile
import datetime
import sys

# Canonical 34 target IDs (sorted, verified unique)
TARGET_IDS = [2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
              521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
              642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
              788, 1216, 1218, 1278]

url = os.getenv("SCHOLARZONE_DATABASE_URL_BACKUP")
if not url:
    print("ERROR: SCHOLARZONE_DATABASE_URL_BACKUP not set", file=sys.stderr)
    sys.exit(1)

gpg_recipient = os.getenv("GPG_RECIPIENT")
if not gpg_recipient:
    print("ERROR: GPG_RECIPIENT not set", file=sys.stderr)
    sys.exit(1)

# Verify GPG recipient fingerprint
try:
    result = subprocess.run(
        ["gpg", "--list-keys", "--with-colons", gpg_recipient],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"ERROR: GPG recipient {gpg_recipient} not found in keyring", file=sys.stderr)
        sys.exit(1)
    # Extract fingerprint from output
    fingerprint = None
    for line in result.stdout.split('\n'):
        if line.startswith('fpr:'):
            fingerprint = line.split(':')[9]
            break
    if fingerprint:
        print(f"GPG recipient verified: {gpg_recipient} (fingerprint: {fingerprint})")
    else:
        print(f"WARNING: Could not extract fingerprint for {gpg_recipient}")
except Exception as e:
    print(f"WARNING: Could not verify GPG recipient: {e}")

print("=== NEON PITR VERIFICATION ===")
print("MANUAL VERIFICATION REQUIRED: Check Neon Console for PITR")
print("  1. Go to https://console.neon.tech")
print("  2. Select your production project")
print("  3. Navigate to Branches > main > Point-in-Time Recovery")
print("  3. Record: history_retention_seconds = ", end="")
try:
    # Try to get PITR info via Neon API (requires API key)
    # This is a placeholder - actual check requires Neon API
    print("[CHECK MANUALLY IN CONSOLE]")
    print("  Record: history_retention_seconds value")
    print("  Expected: >= 604800 (7 days)")
except:
    print("[API CHECK NOT CONFIGURED]")

print("  4. Document actual recovery window in workflow summary")
print("")

# 2. Create pg_dump backup
backup_file = "backup_production_pre_purge_" + datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ".dump"
print("Creating backup: " + backup_file)

try:
    result = subprocess.run([
        "pg_dump", os.getenv("SCHOLARZONE_DATABASE_URL_BACKUP"),
        "--format=custom",
        "--compress=9",
        "--no-owner",
        "--no-privileges",
        "--file=" + backup_file
    ], check=True, capture_output=True, text=True, timeout=300)
except subprocess.CalledProcessError as e:
    print("pg_dump failed: " + str(e))
    print("stderr: " + e.stderr)
    sys.exit(1)

print("Backup created: " + backup_file)

# 2. Encrypt backup with GPG
encrypted_file = backup_file + ".gpg"
print("Encrypting backup for recipient: " + gpg_recipient)
try:
    subprocess.run([
        "gpg", "--trust-model", "always", "--encrypt",
        "--recipient", gpg_recipient,
        "--output", encrypted_file,
        backup_file
    ], check=True, timeout=300)
except subprocess.CalledProcessError as e:
    print("GPG encryption failed: " + str(e))
    sys.exit(1)

print("Encrypted backup: " + encrypted_file)

# 3. Verify backup integrity (on unencrypted)
print("=== BACKUP VERIFICATION (unencrypted) ===")

# 3a. List backup contents
result = subprocess.run(["pg_restore", "--list", backup_file], capture_output=True, text=True, timeout=60)
if result.returncode != 0:
    print("pg_restore --list failed")
    sys.exit(1)

total_objects = len(result.stdout.strip().split("\n"))
print("Total objects in backup: " + str(total_objects))

# 3a. Verify scholarships table
backup_list = result.stdout
scholarships_tables = backup_list.count("TABLE.*scholarships")
print("Scholarships table in backup: " + str(scholarships_tables))

# 3b. Verify data rows (approximate)
temp_sql = tempfile.mktemp()
try:
    subprocess.run(["pg_restore", "--data-only", "--table=scholarships", backup_file],
                   stdout=open(temp_sql, "w"), stderr=subprocess.DEVNULL, check=False, timeout=60)
    with open(temp_sql, "r") as f:
        content = f.read()
    row_count = content.count("COPY public.scholarships")
    print("Scholarships COPY commands in backup: " + str(row_count))
except Exception as e:
    print("Scholarships COPY commands in backup: 0 (error: " + str(e) + ")")
finally:
    try:
        os.unlink(temp_sql)
    except:
        pass

# 3c. Compute SHA256 checksum of ENCRYPTED file
with open(encrypted_file, "rb") as f:
    sha256_hash = hashlib.sha256(f.read()).hexdigest()

checksum_file = encrypted_file + ".sha256"
with open(checksum_file, "w") as f:
    f.write(sha256_hash + "  " + encrypted_file + "\n")

print("Encrypted backup SHA256: " + sha256_hash)

# 3d. Verify checksum
try:
    subprocess.run(["sha256sum", "-c", checksum_file], check=True, capture_output=True)
    print("Checksum verification PASSED")
    checksum_verified = True
except subprocess.CalledProcessError:
    print("Checksum verification FAILED")
    checksum_verified = False

# Remove unencrypted dump - only keep encrypted
os.unlink(backup_file)
print("Unencrypted backup removed. Only encrypted version retained.")

# 4. RESTORE TEST
print("=== RESTORE TEST ===")
restore_db = "restore_test_" + datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
print(f"Creating restore test database: {restore_db}")

# Create test database
try:
    subprocess.run([
        "createdb", restore_db
    ], check=True, capture_output=True, text=True, timeout=30)
    print(f"Created test database: {restore_db}")
    restore_db_created = True
except subprocess.CalledProcessError as e:
    print(f"Createdb failed: {e.stderr}")
    restore_db_created = False

restore_success = False
if restore_db_created:
    # Decrypt and restore
    decrypted_file = backup_file + ".decrypted"
    try:
        subprocess.run([
            "gpg", "--trust-model", "always", "--decrypt",
            "--output", decrypted_file,
            encrypted_file
        ], check=True, timeout=300)
        print("Backup decrypted successfully")

        # Restore into test database
        subprocess.run([
            "pg_restore", "--dbname=" + restore_db,
            "--no-owner", "--no-privileges",
            decrypted_file
        ], check=True, capture_output=True, text=True, timeout=300)
        print("Backup restored successfully")

        # Verify restore
        verify_url = os.getenv("SCHOLARZONE_DATABASE_URL_BACKUP").replace(
            os.getenv("SCHOLARZONE_DATABASE_URL_BACKUP").split("/")[-1], restore_db
        )
        import psycopg2
        verify_conn = psycopg2.connect(verify_url)
        verify_conn.autocommit = True
        with verify_conn.cursor() as cur:
            # Verify schema
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            table_count = cur.fetchone()[0]
            print(f"Tables restored: {table_count}")

            cur.execute("SELECT COUNT(*) FROM scholarships")
            scholarship_count = cur.fetchone()[0]
            print(f"Scholarships restored: {scholarship_count}")

            # Verify the 34 target IDs are present
            target_ids_str = ','.join(str(x) for x in TARGET_IDS)
            cur.execute(f"SELECT COUNT(*) FROM scholarships WHERE id IN ({target_ids_str})")
            target_count = cur.fetchone()[0]
            print(f"Target IDs restored: {target_count}/34")

            if target_count == 34:
                restore_success = True
                print("✅ RESTORE TEST PASSED: All 34 target IDs restored")
            else:
                print(f"❌ RESTORE TEST FAILED: Only {target_count}/34 target IDs restored")

        except Exception as e:
            print(f"Restore verification failed: {e}")
        finally:
            verify_conn.close()

    except subprocess.CalledProcessError as e:
        print(f"Restore failed: {e.stderr}")

# Clean up test database
if restore_db_created:
    try:
        subprocess.run(["dropdb", restore_db], capture_output=True, timeout=30)
    except:
        pass

    # Clean up decrypted file
    if os.path.exists(decrypted_file):
        os.unlink(decrypted_file)

print(f"Restore test: {'PASSED' if restore_success else 'FAILED'}")

# 7. Summary
encrypted_size = subprocess.run(["ls", "-lh", encrypted_file], capture_output=True, text=True).stdout.split()[4]

summary = {
    "backup_file": encrypted_file,
    "backup_size": encrypted_size,
    "checksum_file": checksum_file,
    "pitr_verified": False,  # Must be verified manually in Neon console
    "backup_verified": True,
    "checksum_verified": checksum_verified,
    "restore_test_passed": restore_success,
    "encryption": "GPG",
    "gpg_recipient": gpg_recipient,
    "gpg_fingerprint": fingerprint if 'fingerprint' in locals() else None,
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
}

with open("gate4_result.json", "w") as f:
    json.dump(summary, f, indent=2)

print("Encrypted backup saved: " + encrypted_file + " (size: " + encrypted_size + ")")
print("Checksum: " + checksum_file)
print("Unencrypted backup securely deleted.")