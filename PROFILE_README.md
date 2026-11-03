# Hi, I'm Gopal 👋

**Independent Software Developer** — Building proprietary products with a focus on data integrity, deterministic systems, and zero-paid architectures.

---

## 🎓 Featured Project: ScholarZone

**[gopal735/ScholarZone](https://github.com/gopal735/ScholarZone)** — Global Scholarship Discovery Platform

> **Copyright © 2026 Gopal. All Rights Reserved. Proprietary — not open source.**

| Aspect | Details |
|--------|---------|
| **Role** | Developer — architecture, backend, frontend, infrastructure, data pipeline |
| **Purpose** | Help students worldwide discover 770 public scholarship records with official source provenance |
| **Live Demo** | https://scholarzone-fwzj.vercel.app |
| **Architecture** | Static-first public catalogue (zero-paid), API-backed match engine |

### Tech Stack (Real, Verified)

**Frontend:** React 19, React Router 7, Vite 8, Vitest, Motion, Three.js  
**Backend:** FastAPI 0.141, SQLAlchemy 2.0, PostgreSQL (Neon), Pydantic 2, Uvicorn  
**Infrastructure:** GitHub Pages (frontend), GitHub Actions (CI/CD + cron), SnapDeploy (API), Resend (email)  
**Data:** Reproducible snapshot pipeline (770 records), deterministic match engine (7 dimensions, no ML)

### Key Technical Achievements

- **Static-First Architecture** — Public catalogue serves 770 public scholarship records from a version-controlled JSON snapshot on GitHub Pages; zero database, zero API calls for browsing
- **Deterministic Match Engine** — Arithmetic-only fit scoring (Academic 25%, Field 20%, Funding 20%, Requirements 15%, Language 10%, Preference 5%, Timing 5%); same inputs → byte-identical output; no clock, randomness, or network in scoring path
- **Eligibility Gate** — Three-verdict hard gate (`ELIGIBLE` / `NEEDS_VERIFICATION` / `INELIGIBLE`) runs before any scoring; structural separation prevents fit-score influence
- **Zero-Paid Guard** — CI workflow scans for 80+ paid-only dependencies, database strings in frontend, API keys in frontend code
- **Reproducible Data Pipeline** — CI regenerates snapshot from canonical `verified_scholarships.py` on every backend change; validates structure, counts, exclusions
- **Build Provenance** — Embedded git SHA in deployed artefacts; `/health` endpoint verifies deployment identity
- **Production Purge Preflight** — 7-gate safety protocol for automated expired-cycle deletion (atomicity, identity, dependencies, backup, evidence, cycle model, git safety); **preflight work with production validation pending**

### Local Test Results (Not Remote CI)

- **264** frontend tests passing (Vitest, local)
- **117** backend matching engine tests passing (pytest, local)
- **118** backend visibility + matching API tests passing (pytest, local)
- **0** paid dependencies in public browse path
- **~2.1 MB** snapshot, **~153 KB** gzipped JS bundle

---

## 🔧 What I Focus On

- **Data Integrity** — Every number has a source; every source has a URL; every URL has a verification date
- **Deterministic Systems** — Same inputs produce same outputs; no hidden state, no opaque models
- **Zero-Paid Architecture** — Genuine free tiers only; no surprise bills; static-first by default
- **Proprietary Quality** — Production-grade code, comprehensive tests, documented architecture, security-first CI

---

## 📫 Contact

- **GitHub:** [@gopal735](https://github.com/gopal735)
- **ScholarZone:** [gopal735/ScholarZone](https://github.com/gopal735/ScholarZone) | [Live Demo](https://scholarzone-fwzj.vercel.app)

---

*This profile README is maintained as part of the ScholarZone portfolio presentation. The ScholarZone repository is published for code review and demonstration purposes under GitHub Terms of Service. It is proprietary software — no open-source license is granted.*