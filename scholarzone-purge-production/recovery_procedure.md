# Recovery Procedure for Production Scholarship Purge

## Overview
This document describes the complete recovery procedure if the production scholarship purge needs to be rolled back.

## Recovery Options (Priority Order)

### Option 1: Neon PITR (Fastest - < 5 minutes)
**Preferred method** - Uses Neon's built-in Point-in-Time Recovery.

**Prerequisites:**
- Neon Console access
- Project: `scholarzone-production`
- Branch: `main`
- PITR enabled with 7-day retention

**Procedure:**
1. Go to https://console.neon.tech
2. Select project: `scholarzone-production`
3. Navigate to Branches → `main`
4. Click **"Point-in-Time Recovery"**
5. Select timestamp: **Immediately before purge execution** (note timestamp before running purge)
5. Click **"Restore"** → Creates new branch (e.g., `main-pre-purge-20261103`)
6. Wait for branch creation (< 5 minutes)
6. Get new connection string from new branch
6. Update `SCHOLARZONE_DATABASE_URL` in Vercel/Netlify environment variables
7. Redeploy Vercel/Netlify to pick up new connection string
7. Verify: `SELECT COUNT(*) FROM scholarships;` → Should return **770**

**Estimated RTO:** < 5 minutes
**Risk:** Near-zero data loss (continuous replication)

---

### Option 2: Encrypted pg_dump Restore (Medium - < 15 minutes)
**Fallback method** - Uses encrypted pg_dump backup created by Gate 4.

**Prerequisites:**
- Encrypted backup file: `backup_production_pre_purge_YYYYMMDD_HHMMSS.dump.gpg`
- SHA256 checksum verified
- GPG private key available in secure key service
- New Neon branch created for restore target

**Procedure:**
1. Create new Neon branch for restore (e.g., `restore-pre-purge-20261103`)
2. Get connection string for new branch
3. Decrypt backup:
   ```bash
   gpg --decrypt --output backup.dump backup_production_pre_purge_*.dump.gpg
   ```
2. Verify checksum:
   ```bash
   sha256sum -c backup.dump.sha256
   ```
3. Restore to new branch:
   ```bash
   pg_restore --dbname="<new-branch-connection-string>" \
     --no-owner --no-privileges \
     backup.dump
   ```
4. Verify restore:
   ```bash
   psql "<new-connection-string>" -c "SELECT COUNT(*) FROM scholarships;"
   # Should return 770
   ```
5. Update `SCHOLARZONE_DATABASE_URL` to new branch connection string
6. Redeploy Vercel/Netlify
6. Verify application functionality

**Estimated RTO:** < 15 minutes
**Risk:** Near-zero data loss

---

### Option 3: pg_dump Restore to Existing Database (Slower - < 30 minutes)
**Last resort** - If new branch creation not possible.

**Procedure:**
1. Create new PostgreSQL database (local or cloud)
2. Decrypt and restore backup (same as Option 2)
3. Verify data integrity
4. Export clean data
4. Import into production (requires downtime)

**Estimated RTO:** < 30 minutes
**Risk:** Potential downtime during import

---

## Verification Steps (All Methods)

After any recovery:
1. `SELECT COUNT(*) FROM scholarships;` → **Must return 770**
2. `SELECT COUNT(*) FROM scholarships WHERE id IN (34 target IDs);` → **Must return 34**
3. Verify all 34 target IDs present with correct titles/statuses
4. Verify application functionality at production URL
4. Check sitemap and snapshot regeneration
4. Verify no orphaned foreign key references

---

## Verification Checklist

| Step | Command | Expected Result |
|------|---------|-----------------|
| 1 | `SELECT COUNT(*) FROM scholarships;` | 770 |
| 2 | `SELECT COUNT(*) FROM scholarships WHERE id IN (34 IDs);` | 34 |
| 3 | `SELECT status FROM scholarships WHERE id = 2;` | 'closed' |
| 4 | Frontend loads `/scholarships` | 736 visible |
| 3 | Frontend loads `/scholarships/2` | Shows closed status |
| 4 | Sitemap.xml has 751 URLs | 751 (736 + home + countries) |

---

## Rollback Decision Matrix

| Scenario | Recovery Method | RTO |
|----------|-----------------|-----|
| Accidental purge execution | Neon PITR | < 5 min |
| Purge + partial data corruption | pg_dump restore | < 15 min |
| Full database corruption | Full restore + DNS failover | < 30 min |
| Purge + application errors | Neon PITR + redeploy | < 10 min |

---

## Contacts
- **Neon Support:** support@neon.tech
- **Vercel Support:** Vercel dashboard
- **Netlify Support:** Netlify dashboard
- **Internal DBA:** [Internal contact]

---

## Post-Recovery Actions
1. Update all environment variables to restored database
2. Redeploy all services (Vercel, Netlify, backend)
3. Run smoke tests
4. Notify stakeholders
5. Document incident in postmortem
6. Review purge procedure for improvements