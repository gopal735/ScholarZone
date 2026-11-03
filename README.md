# ScholarZone

**Global Scholarship Discovery Platform** — An independently developed proprietary software project by Gopal (GitHub: [gopal735](https://github.com/gopal735)).

> **Copyright © 2026 Gopal (GitHub: gopal735). All Rights Reserved.**  
> This is proprietary software. No open-source license is granted. See [COPYRIGHT.md](COPYRIGHT.md) for full terms.

---

## 🎯 Project Purpose

ScholarZone is a global scholarship discovery platform that helps students find official-source-informed scholarship opportunities worldwide. Built with a **static-first architecture**, the public catalogue operates entirely without a live database or API connection — serving **770 public scholarship records** from a version-controlled JSON snapshot deployed to Vercel.

### Key Differentiators

| Aspect | Approach |
|--------|----------|
| **Architecture** | Static-first: public browsing does not require a live database or API connection |
| **Data Integrity** | Reproducible CI pipeline regenerates snapshot from canonical sources |
| **Verification** | Records link to official source URLs; `last_verified_at` tracked where available |
| **Cost Model** | Zero-paid dependencies for public browsing (Vercel + GitHub Actions) |
| **Match Engine** | Deterministic, arithmetic-only fit scoring — no ML, no LLMs |

---

## ✨ Implemented Features

### Public Catalogue (Static-First, Zero Database)
- **Scholarship Directory** — Filter by country, degree, funding, deadline month, status; full-text search; sortable; paginated (12/page)
- **Scholarship Detail Pages** — Rich editorial layout with hero image, quick facts, funding breakdown, eligibility, requirements, documents, English requirements, application method, official sources, verification record
- **Country Explorer** — Browse scholarships by country (65 countries)
- **Compare** — Side-by-side comparison of up to 4 scholarships (localStorage)
- **Saved Scholarships** — Personal bookmarking (localStorage)
- **Sitemap & SEO** — Auto-generated `sitemap.xml` (770 URLs), JSON-LD structured data, canonical URLs, meta tags

### Match Engine (API-Backed, Deterministic)
- **POST `/api/scholarships/match`** — Scores a student profile against all scholarships
- **Eligibility Gate** — Three verdicts: `ELIGIBLE` / `NEEDS_VERIFICATION` / `INELIGIBLE` (hard gate, runs before scoring)
- **Fit Scoring** — 7 weighted dimensions (Academic 25%, Field 20%, Funding 20%, Requirements 15%, Language 10%, Preference 5%, Timing 5%)
- **Coverage & Sensitivity** — Reports measurable coverage % and mathematical sensitivity range
- **Confidence Score** — Record trust (data completeness 35%, provenance 25%, requirement explicitness 25%, freshness 15%)
- **Readiness Score** — Application actionability (eligibility certainty 30%, requirement completeness 20%, language 15%, application 15%, deadline 20%)
- **Profile Strength** — Student input completeness (academic 25%, study goal 25%, language 20%, funding 20%, identity 10%)
- **Deterministic** — Same inputs → byte-identical output; no clock, randomness, or network in scoring path
- **Free-Text Parser** — Optional deterministic NLP for profile input (curated table lookup, no LLM)

### Student Dashboard (Authenticated)
- **Applications Workspace** — Track applications through stages (Draft → Submitted → Under Review → Decision)
- **Saved Scholarships** — Persisted via API
- **Match History** — Re-run previous profiles

### Supervisor Discovery (Research Feature)
- **Professor/Researcher Directory** — Academic contacts with official source provenance and evidence tracking
- **Official Source Verification** — PDF extraction, page discovery, evidence tracking
- **Verification Pipeline** — Multi-stage review with confidence scoring

### Admin & Maintenance
- **Image Review** — Approve/reject scholarship images with provenance
- **Automated Maintenance** — GitHub Actions cron for verification, snapshot regeneration
- **Expired-Cycle Purge** — 7-gate preflight workflow (manual dispatch; production validation pending)
- **Build Provenance** — Embedded git SHA in deployed artefacts for deployment verification

---

## 🏗 Technology Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2.8 | UI framework |
| React Router | 7.18.2 | Client-side routing |
| Vite | 8.2.0 | Build tool & dev server |
| Vitest | 5.0.3 | Unit/integration testing |
| ESLint | 10.8.0 | Linting |
| Motion | 13.5.1 | Animations |
| Three.js | 0.160.0 | 3D hero background |

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.141.1 | API framework |
| SQLAlchemy | 2.0.x | ORM |
| PostgreSQL (Neon) | — | Primary database |
| Pydantic | 2.13.4 | Validation & serialization |
| Uvicorn | 0.52.1 | ASGI server |
| pytest | — | Testing |

### Infrastructure & CI/CD
| Service | Purpose |
|---------|---------|
| **Vercel** | Frontend hosting (static, automatic deployments) |
| **GitHub Actions** | CI/CD, scheduled maintenance, snapshot generation |
| **SnapDeploy** | Backend API hosting (container, sleeps after 30min idle) |
| **Neon PostgreSQL** | Database (0.5 GB free, 190 compute hrs/mo) |
| **Resend** | Email verification (3,000/mo free) |
| **Cloudflare Pages** | Evaluated alternative for frontend (configured, not active) |

### Data Pipeline
- **Canonical Source**: `backend/app/data/verified_scholarships.py` (ingestion records with official_source_url)
- **Snapshot Generation**: `backend/scripts/build_public_snapshot.py` → `frontend/public/scholarships-snapshot.json`
- **CI Workflow**: `.github/workflows/catalogue-snapshot.yml` (triggers on backend changes, validates, commits snapshot)
- **Zero-Paid Guard**: `.github/workflows/zero-paid-guard.yml` (scans for paid-only dependencies, secrets in frontend)

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          VERCEL                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  frontend/dist (static build)                           │   │
│  │  ├── index.html                                         │   │
│  │  ├── assets/ (JS, CSS, immutable cache)                 │   │
│  │  ├── scholarships-snapshot.json  ← 770 records, 2.1 MB  │   │
│  │  └── sitemap.xml                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Static-First Service (staticScholarshipService.js)     │   │
│  │  • fetchScholarshipsFromSnapshot()  — filter, sort, page │   │
│  │  • fetchScholarshipStatsFromSnapshot()                   │   │
│  │  • fetchScholarshipByIdFromSnapshot()                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│   GITHUB ACTIONS        │   │   SNAPDEPLOY (API)      │
│   (CI/CD + CRON)        │   │   FastAPI + PostgreSQL  │
│                         │   │                         │
│ • catalogue-snapshot.yml│   │ • POST /scholarships/   │
│ • zero-paid-guard.yml   │   │   match                 │
│ • verification-cron.yml │   │ • /dashboard/*          │
│                         │   │ • /applications/*       │
│                         │   │ • /mentor/*             │
│                         │   │ • /admin/*              │
└─────────────────────────┘   └─────────────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NEON POSTGRESQL                            │
│  • scholarships (770 public + research tables)                  │
│  • supervisors, supervisor_reviews, supervisor_candidates       │
│  • professors, applications, users, sessions                    │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingestion** → `verified_scholarships.py` (manual curation with official_source_url)
2. **Seed** → `scripts/seed_real_scholarships.py` → Neon PostgreSQL
3. **Snapshot** → `scripts/build_public_snapshot.py` → `scholarships-snapshot.json` (CI)
4. **Deploy** → Vercel serves snapshot + static build
5. **Browse** → Frontend reads snapshot directly (no API call)
6. **Match** → API queries Neon, runs pure engine, returns scored results

---

## 🔒 Zero-Paid Architecture (Public Browsing)

The public catalogue requires **zero paid services**:

| Component | Provider | Cost |
|-----------|----------|------|
| Frontend Hosting | Vercel | Free (static, personal hobby tier) |
| CI/CD | GitHub Actions | Free (unlimited public) |
| Snapshot Storage | Git repo (LFS not needed) | Free |
| CDN | Vercel edge | Free |
| SSL/TLS | Automatic | Free |

**Backend API** (match, dashboard, admin) uses paid-tier services but is **not required for public browsing**:
- Neon PostgreSQL: 0.5 GB / 190 compute hrs free tier
- SnapDeploy: 1 container free, sleeps after 30 min
- Resend: 3,000 emails/mo free

See [ZERO_PAID_ARCHITECTURE_REPORT.md](ZERO_PAID_ARCHITECTURE_REPORT.md) and [ZERO_PAID_LIMITS.md](ZERO_PAID_LIMITS.md) for full analysis.

---

## 📚 API Documentation

### Public Endpoints (No Auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scholarships` | GET | Paginated list (query: search, country, degree, funding, deadline_month, status, sort, page, limit) |
| `/api/scholarships/stats` | GET | Headline figures (total, countries, fully_funded, verified) |
| `/api/scholarships/{id}` | GET | Single scholarship detail |
| `/api/scholarships/match` | POST | Match engine — score profile against catalogue |
| `/api/scholarships/match/profile-options` | GET | Curated form options (countries, degrees, fields, etc.) |
| `/api/scholarships/match/parse-profile` | POST | Deterministic free-text profile parser |
| `/api/countries` | GET | List countries with scholarship counts |
| `/api/countries/{code}` | GET | Scholarships for a country |

### Authenticated Endpoints (Session Cookie)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register |
| `/api/auth/login` | POST | Login |
| `/api/auth/me` | GET | Current user |
| `/api/dashboard/*` | * | Student dashboard |
| `/api/applications/*` | * | Application workspace |
| `/api/mentor/*` | * | Mentor chat |
| `/api/admin/*` | * | Admin review |

### Internal Endpoints (Cron/Workers)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/internal/verify/trigger` | POST | Trigger verification worker |
| `/internal/purge/trigger` | POST | Trigger expired cycle purge |

---

## 🚀 Setup & Development

### Prerequisites
- Node.js 20+
- Python 3.11+
- PostgreSQL (local or Neon)

### Frontend
```bash
cd frontend
npm install
npm run dev          # Dev server at localhost:5173
npm run build        # Production build to dist/
npm run test         # Vitest
npm run lint         # ESLint
```

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Configure DATABASE_URL, etc.
python -m app.main         # Runs at localhost:8000
pytest                     # Run tests
```

### Environment Variables

**Frontend** (`.env` or Vite config):
```env
VITE_API_BASE_URL=/api                    # Dev proxy
VITE_API_BASE_URL=https://api.example.com # Production
VITE_STATIC_CATALOGUE=true                # Enable static-first mode
VITE_CANONICAL_ORIGIN=https://scholarzone.example.com
```

**Backend** (`.env`):
```env
DATABASE_URL=postgresql://user:pass@host/db
ENVIRONMENT=development|production|test
ALLOWED_ORIGINS=https://scholarzone.example.com,http://localhost:5173
RESEND_API_KEY=re_...
SECRET_KEY=...
```

---

## 🧪 Tests & CI

### Test Suites

| Suite | Location | Tests (Local) | Coverage |
|-------|----------|---------------|----------|
| Frontend Unit | `frontend/src/**/*.test.{js,jsx}` | 264 | Components, hooks, services, utils |
| Frontend Contracts | `frontend/src/*.test.js` | 30 | Sitemap, SEO, middleware |
| Backend Matching Engine | `backend/tests/test_matching_engine.py` | 117 | Fit arithmetic, eligibility, determinism |
| Backend Visibility + Matching API | `backend/tests/test_public_*.py, test_matching_api.py` | 118 | HTTP contract, CORS, visibility |

### CI Workflows (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR | Lint, test, build (frontend + backend) |
| `catalogue-snapshot.yml` | Push to master (backend/) | Regenerate & validate snapshot |
| `zero-paid-guard.yml` | Push/PR | Scan for paid deps, secrets in frontend |
| `verification-cron.yml` | Schedule (daily) | Run verification worker |
| `production-purge-preflight.yml` | Manual dispatch | Safe expired-cycle purge (7 gates; preflight, production validation pending) |
| `frontend.yml` | Push/PR (frontend/) | Frontend-specific checks |
| `deploy.yml` | Push to master | Deploy to Vercel + SnapDeploy |

> **Note**: Test counts above reflect local verification. Remote GitHub Actions status should be checked via the Actions tab for the latest run results.

### Run Locally
```bash
# Frontend
cd frontend && npm run test && npm run lint && npm run build

# Backend
cd backend && pytest -v
```

---

## 📸 Screenshots

> *Screenshots to be added. Current deployment: https://scholarzone-fwzj.vercel.app*

| View | Description |
|------|-------------|
| Home Page | Hero with 3D graduation cap, featured scholarships, live stats |
| Scholarships Directory | Filterable, sortable, paginated grid (12/page) |
| Scholarship Detail | Editorial layout: hero, quick facts, funding, eligibility, verification |
| Match Engine | Profile form → ranked results with fit bands, confidence, readiness |
| Student Dashboard | Applications workspace, saved scholarships, match history |
| Supervisor Discovery | Searchable academic directory with verification status |

---

## 🗺 Roadmap

### Near Term (v1.1)
- [ ] Dark mode toggle (theme context exists, UI pending)
- [ ] Offline-first Service Worker for static catalogue
- [ ] Advanced search: multi-select filters, save search
- [ ] Email alerts for new scholarships matching profile

### Medium Term (v1.2)
- [ ] University programme pages (reverse lookup: scholarships for programme X)
- [ ] Deadline calendar view (monthly grid)
- [ ] Export comparison to PDF/CSV
- [ ] Multi-language UI (i18n framework)

### Long Term (v2.0)
- [ ] AI-assisted profile completion (local, deterministic — no external LLM calls)
- [ ] Collaborative application workspace (shared drafts, mentor review)
- [ ] Mobile app (React Native, same static snapshot)
- [ ] Institutional partnership dashboard

---

## 📄 Documentation

| Document | Description |
|----------|-------------|
| [COPYRIGHT.md](COPYRIGHT.md) | Ownership & proprietary notice |
| [ZERO_PAID_ARCHITECTURE_REPORT.md](ZERO_PAID_ARCHITECTURE_REPORT.md) | Static-first architecture & provider limits |
| [ZERO_PAID_LIMITS.md](ZERO_PAID_LIMITS.md) | Provider free-tier limits table |
| [CLOUDFLARE_PAGES_EVALUATION.md](CLOUDFLARE_PAGES_EVALUATION.md) | Cloudflare Pages config & analysis |
| [backend/docs/scholarzone-match-engine.md](backend/docs/scholarzone-match-engine.md) | Match engine specification (696 lines) |
| [backend/docs/SCHOLARSHIP_INGESTION.md](backend/docs/SCHOLARSHIP_INGESTION.md) | Data ingestion process |
| [docs/operations/purge/](docs/operations/purge/) | Production purge preflight gates (7 gates) |
| [FINAL_COMPLETION_REPORT.md](FINAL_COMPLETION_REPORT.md) | Final gate status & verification |

---

## 👤 Author

**Gopal** — Independent Software Developer  
GitHub: [@gopal735](https://github.com/gopal735)  
Repository: [gopal735/ScholarZone](https://github.com/gopal735/ScholarZone)

---

## ⚖️ License & Ownership

**This is proprietary software. No open-source license is granted.**

- **Copyright © 2026 Gopal (GitHub: gopal735). All Rights Reserved.**
- See [COPYRIGHT.md](COPYRIGHT.md) for full terms.
- Third-party dependencies retain their original licenses (see `frontend/package.json`, `backend/requirements.txt`).
- Scholarship data aggregated from public official sources; no copyright claimed over factual data.

> Published on GitHub for portfolio demonstration and code review under GitHub Terms of Service. Publication does not constitute a license grant.