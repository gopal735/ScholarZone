"""Post-merge verification of the supervisor enrichment."""

from __future__ import annotations

import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "..", "backend", "scholarzone.db")

con = sqlite3.connect(DB)
cur = con.cursor()

def q(sql: str, args=()):
    cur.execute(sql, args)
    return cur.fetchall()

print("== counts ==")
for t in ("professor_profiles", "scholarship_professor_links", "supervisor_source_evidence",
          "scholarship_supervisor_coverage", "scholarships"):
    print(f"{t}: {q(f'SELECT COUNT(*) FROM {t}')[0][0]}")

print("\n== coverage status ==")
for row in q("SELECT status, COUNT(*) FROM scholarship_supervisor_coverage GROUP BY status ORDER BY 2 DESC"):
    print(row)

print("\n== emails ==")
print("with email:", q("SELECT COUNT(*) FROM professor_profiles WHERE official_email IS NOT NULL")[0][0])
print("verified:", q("SELECT COUNT(*) FROM professor_profiles WHERE official_email_verified=1")[0][0])

print("\n== link verification ==")
for row in q("SELECT verification_status, COUNT(*) FROM scholarship_professor_links GROUP BY verification_status"):
    print(row)

print("\n== scholarships never examined (no coverage row) ==")
print(q("""SELECT COUNT(*) FROM scholarships s
          LEFT JOIN scholarship_supervisor_coverage c ON c.scholarship_id = s.id
          WHERE c.id IS NULL""")[0][0])

print("\n== verified scholarships with public supervisors ==")
print(q("""SELECT COUNT(DISTINCT s.id) FROM scholarships s
          JOIN scholarship_professor_links l ON l.scholarship_id = s.id
          WHERE l.verification_status='verified'""")[0][0])

print("\n== institutional-domain email check ==")
baddomains = q("SELECT id, official_email FROM professor_profiles WHERE official_email IS NOT NULL AND official_profile_url IS NOT NULL")
mismatch = 0
for pid, email, profile_url in q("SELECT id, official_email, official_profile_url FROM professor_profiles WHERE official_email IS NOT NULL"):
    dom = profile_url.split("/")[2].lower().replace("www.", "")
    em = email.split("@")[1].lower()
    if not (em == dom or em.endswith("." + dom)):
        mismatch += 1
print("email/profile host mismatches:", mismatch)

print("\n== sample ==")
for row in q("""SELECT s.id, s.title, p.canonical_name, p.title, p.institution_name, p.official_email,
                       l.verification_status, c.status
                FROM scholarships s
                JOIN scholarship_professor_links l ON l.scholarship_id = s.id
                JOIN professor_profiles p ON p.id = l.professor_id
                JOIN scholarship_supervisor_coverage c ON c.scholarship_id = s.id
                ORDER BY s.id LIMIT 10"""):
    print(row)
con.close()
