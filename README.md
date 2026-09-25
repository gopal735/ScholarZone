# ScholarZone

Verified Scholarships. Trusted Information. Better Decisions.

An open-source platform helping students worldwide discover verified scholarships and make informed higher education choices.

## Table of Contents

- [Overview](#overview)
- [Why ScholarZone](#why-scholarzone)
- [Core Features](#core-features)
- [Trust & Verification Model](#trust--verification-model)
- [Image Verification Pipeline](#image-verification-pipeline)
- [Automation & Scheduled Verification](#automation--scheduled-verification)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [API Overview](#api-overview)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [Testing & CI](#testing--ci)
- [Deployment](#deployment)
- [Security](#security)
- [Project Status](#project-status)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

ScholarZone centralizes verified higher-education opportunities into a clean, searchable platform prioritized strictly by primary official sources. Students spend weeks navigating scattered, outdated websites, facing unverified claims, missed deadlines, and broken application links. ScholarZone removes that friction by surfacing only opportunities whose details have been checked against official sources and maintained on a regular schedule.

The platform is split into two services:

- A **React + Vite single-page application** (frontend) for browsing, filtering, comparing, and saving scholarships.
- A **FastAPI backend** (backend) exposing a REST API, an autonomous verification engine, scholarship discovery, and an admin review dashboard.

Production deployment:

- **Frontend:** GitHub Pages via `.github/workflows/frontend.yml`.
- **Backend:** SnapDeploy containers (production). A `backend/render.yaml` file exists as an alternative deployment configuration but Render is not the active production platform.

---

## Why ScholarZone

- **Source-first prioritization:** Opportunities are ranked by primary official sources, not third-party aggregators.
- **Field-level verification:** Individual fields are verified against official pages rather than trusting listings wholesale.
- **Immutable audit trail:** Every verified field change is recorded with old/new values, source URL, confidence, and timestamp.
- **Human-in-the-loop review:** Conflicts and low-confidence findings are routed to an append-only review workflow instead of being silently applied.
- **Automated maintenance:** Scheduled verification rounds keep listings fresh without manual intervention.
- **Official image intelligence:** Same-domain image discovery and layered validation reduce broken, placeholder, or irrelevant imagery.

---

## Core Features

| Feature | Description | Status |
| :--- | :--- | :---: |
| Scholarship Discovery | Browse a searchable, paginated directory of verified opportunities | Available |
| Filtering & Sorting | Filter by country, degree, funding, deadline month, and listing status; sort by recommended, recently added, deadline, funding, and name | Available |
| Scholarship Details | Structured view with benefits, eligibility, requirements, documents, application timeline, and official source links | Available |
| Verification System | Field-level verification with active / needs_review / inactive status, last-verified tracking, and next-due scheduling | Available |
| Human Review Workflow | Conflict detection (identity, low confidence, third-party sources) routes uncertain fields to append-only review records with approve/reject flow | Available |
| Verification Audit Trail | Immutable `ScholarshipVerificationHistory` records every field change with old/new values, source URL, confidence, and timestamp | Available |
| Official Image Discovery | Crawls official scholarship source pages (max depth 2) to discover same-domain image candidates with context-aware extraction | Available |
| Image Validation | Layered non-content detection (banners, placeholders, logos, social icons, OG thumbnails), dimension/ratio checks, duplicate detection, and official-domain verification | Available |
| Image Persistence | Authenticated `POST /internal/images/verify` persists HIGH-confidence approved images with idempotent audit history | Available |
| Image Fallback | Frontend `ScholarshipImage` component renders retry logic, broken-image placeholders, and source-type indicators | Available |
| Saved Scholarships | Device-local shortlist with save/unsave actions | Available |
| Side-by-Side Comparison | Compare up to 4 scholarships on country, degree, funding, and deadline | Available |
| Country Explorer | Browse opportunities by destination with live scholarship counts and editorial destination cards | Available |
| Admin Dashboard | Control center for verification queue, metric cards, search/filter, and verify/flag actions | Available |
| Authentication | Login and registration pages with `ProtectedRoute` component (defined; route gating not yet applied to admin) | Available |

---

## Trust & Verification Model

ScholarZone treats verification as a field-level operation rather than a binary "trusted" flag. Each scholarship field is evaluated independently against its official source, and the outcome determines whether the change is applied directly or routed to human review.

### Verification Flow

1. **Trigger:** GitHub Actions cron (every 12 hours at minute 7) calls the authenticated `POST /internal/verify/trigger` endpoint.
2. **Auth:** The request must include the `X-Verification-Secret` header matching the production `SCHOLARZONE_VERIFICATION_SECRET`.
3. **Rate Limit:** Minimum 60-second interval between triggers; concurrent or rapid requests receive `429 Too Many Requests`.
4. **Engine:** `SchedulerEngine` starts a bounded `ThreadPoolExecutor` (max 4 workers), processes due retries, submits a batch of scholarships, waits for completion, then shuts down.
5. **Per-Scholarship:** For each candidate, the pipeline fetches the official source, extracts structured data, diffs against current records, collects evidence, and applies confidence-based safety gates.
6. **Auto-Update vs. Review:**
   - **Auto-update:** Safe, high-confidence changes are applied directly and written to `ScholarshipVerificationHistory`.
   - **Human review:** Identity conflicts, low-confidence findings, and third-party sources are routed to `ScholarshipReview` records for manual approval or rejection.

### Confidence Levels

| Level | Meaning |
| :--- | :--- |
| HIGH | Field matches official source; safe to auto-apply |
| MEDIUM | Partial match; recorded but flagged for review |
| LOW | Weak or conflicting evidence; routed to human review |
| HUMAN_REVIEW | Requires manual decision before any change |

### Audit Trail

Every field change is recorded in `ScholarshipVerificationHistory` with:

- Old and new values
- Source URL used for verification
- Confidence level
- Timestamp

This append-only history supports full provenance tracing and post-hoc auditing of every applied change.

### Source Health

Each approved source is tracked in `SourceHealth` with success/failure counts and last-verification timestamps. Sources that consistently fail verification are flagged and deprioritized in discovery.

---

## Image Verification Pipeline

Not every scholarship listing carries an official image. ScholarZone discovers and validates images only when they exist, and never fabricates imagery to fill gaps.

### Discovery

- Crawls official scholarship source pages (max depth 2).
- Discovers same-domain image candidates with context-aware extraction.
- Records candidates in `DiscoveryCandidate` for review.

### Validation Layers

- **Non-content rejection:** Detects banners, placeholders, logos, social icons, and Open Graph thumbnails.
- **Dimension checks:** Enforces `MIN_IMAGE_DIMENSION=200` and `MIN_COVER=500`.
- **Aspect ratio:** Validates images within 0.2 to 5.0 ratio.
- **Duplicate detection:** Rejects near-duplicate images.
- **Official-domain verification:** Confirms the image originates from the scholarship's official domain.

### Confidence & Persistence

Images are assigned one of `HIGH`, `MEDIUM`, `LOW`, or `HUMAN_REVIEW` confidence levels. Only `HIGH`-confidence images are persisted via the authenticated `POST /internal/images/verify` endpoint, with idempotent audit history recorded in `ContentFingerprintRecord`.

The `NON_CONTENT_REJECTION_THRESHOLD=1.5` governs the non-content scoring gate.

### Frontend Fallback

The `ScholarshipImage` component renders retry logic, broken-image placeholders, and source-type indicators so listings remain usable even when no valid image is available.

---

## Automation & Scheduled Verification

Verification runs on a fixed schedule rather than on-demand only.

### Cron Schedule

- **Schedule:** `7 */12 * * *` (every 12 hours at minute 7; runs at approximately 00:07 and 12:07 UTC).
- **Workflow:** `.github/workflows/verification-cron.yml`.
- **Concurrency:** Grouped under `verification-trigger` with `cancel-in-progress: true` to prevent overlapping rounds.

### Workflow Phases

1. **Validate configuration:** Confirms `SCHOLARZONE_API_URL` and `SCHOLARZONE_VERIFICATION_SECRET` are set.
2. **Wake container and trigger verification:** Polls `/health` with an exponential backoff schedule (10s, 20s, 30s, 45s, 60s, 90s, 120s, 120s; total budget 495s) until the container is ready, then triggers `POST /internal/verify/trigger`. A success flag (`TRIGGERED=1`) is set on HTTP 202 or 429 responses so the job exits cleanly even when verification is already in progress.
3. **Trigger country-level discovery:** Runs only when the verification trigger succeeds (`if: success()`), calling `POST /internal/discover/trigger`.

### Trigger Endpoint Behavior

- **HTTP 202:** Verification round accepted and running.
- **HTTP 429:** Rate-limited; verification already in progress or too recent.
- **HTTP 401/403:** Authentication failure; the workflow exits with an error.
- **HTTP 503:** Service unavailable (typically cold-start or database not ready); the workflow retries.

### Discovery

Country-level discovery runs after each verification round and:

- Discovers new scholarship candidates by country.
- Records candidates in `DiscoveryCandidate` for review.
- Applies lifecycle transitions (active / needs_review / inactive) via `lifecycle_manager`.
- Performs next-cycle discovery for closed scholarships.

### APScheduler

A legacy APScheduler instance exists in `scheduler_v2.py` but is intentionally **not started in production**. Verification is triggered exclusively by the cloud cron job via `/internal/verify/trigger`, preventing duplicate scheduler execution.

---

## Architecture

```mermaid
graph LR
    A[GitHub Actions Cron<br/>every 12h] --> B[/internal/verify/trigger]
    B --> C{SchedulerEngine}
    C --> D[ThreadPoolExecutor<br/>max 4 workers]
    D --> E[Per-Scholarship<br/>Verification Pipeline]
    E --> F[Official Source<br/>HTTP Fetch]
    E --> G{Confidence Gate}
    G -->|HIGH| H[Auto-Apply + Audit]
    G -->|LOW| I[Human Review]
    H --> J[(PostgreSQL<br/>ScholarshipVerificationHistory)]
    I --> K[(ScholarshipReview)]
    B2[Discovery Trigger] --> L[Country Discovery]
    L --> M[(DiscoveryCandidate)]
    L --> N[(SourceHealth)]

    Frontend[React SPA<br/>GitHub Pages] --> API[FastAPI Backend<br/>SnapDeploy]
    API --> J
    API --> K
    API --> M
    API --> N
```

### Backend Services

- **Verification engine:** `scheduler_v2.py` — `SchedulerEngine` with `ThreadPoolExecutor`, `max_workers=4`, `batch_size=100`, `poll_interval=300s`, rate limit 60s minimum interval.
- **Image discovery:** `image_discovery.py` — same-domain crawling with context-aware extraction.
- **Image validation:** `image_validator.py` — layered non-content rejection, dimension/ratio checks, duplicate detection.
- **Scholarship image verifier:** `scholarship_image_verifier.py` — image verification endpoint and persistence.
- **Verification history:** `scholarship_history.py` — append-only audit trail.
- **Review workflow:** `scholarship_review.py` — human review with approve/reject flow.
- **Source health:** `source_health_service.py` — source tracking and deprioritization.
- **Telemetry:** `telemetry.py` — operational event recording.
- **Email service:** `email_service.py` — Resend integration for notifications.
- **Discovery pipeline:** `discovery_pipeline.py` — country-level discovery orchestration.
- **Lifecycle manager:** `lifecycle_manager.py` — scholarship state transitions.

### Data Model (13 SQLAlchemy Models)

| Model | Purpose |
| :--- | :--- |
| Scholarship | Core scholarship record |
| ScholarshipVerificationHistory | Immutable field-change audit trail |
| ScholarshipReview | Human review records |
| ScholarshipFetchAttempt | Fetch attempt logging |
| ApprovedSource | Approved source registry |
| SourceHealth | Source success/failure tracking |
| KnowledgeNode | Knowledge graph nodes |
| KnowledgeEdge | Knowledge graph edges |
| ScholarshipSnapshot | Point-in-time scholarship snapshots |
| DiscoveryCandidate | Unreviewed discovery candidates |
| ImageReview | Image review records |
| ScholarshipRestoreRecord | Restore operation history |
| ContentFingerprintRecord | Image fingerprint audit |

---

## Technology Stack

### Frontend

| Technology | Version | Purpose |
| :--- | :--- | :--- |
| React | 19.2.8 | UI component library |
| react-router-dom | 7.18.2 | Client-side routing |
| Vite | 8.2.0 | Build tool and dev server |
| motion | 13.1.1 | Animation library |
| ESLint | 10.8.0 | Linting |

### Backend

| Technology | Version | Purpose |
| :--- | :--- | :--- |
| Python | 3.11 | Runtime |
| FastAPI | 0.141.1 | REST API framework |
| Uvicorn | 0.52.1 | ASGI server |
| SQLAlchemy | 2.0 | ORM |
| psycopg | v3 | PostgreSQL driver |
| Pydantic | 2.13.4 | Data validation |
| HTTPX | >=0.27 | HTTP client for source fetching |
| APScheduler | latest | Job scheduling (legacy, not started in production) |
| Pillow | latest | Image processing |
| beautifulsoup4 | latest | HTML parsing |
| pytest | latest | Testing |
| python-dotenv | latest | Environment variable loading |
| Resend | latest | Email delivery |

### Infrastructure

| Component | Technology |
| :--- | :--- |
| Database (production) | PostgreSQL (Neon) |
| Database (dev/test) | SQLite |
| Frontend hosting | GitHub Pages |
| Backend hosting | SnapDeploy containers |
| CI/CD | GitHub Actions |
| Container runtime | Docker (single-stage `python:3.11-slim`) |

---

## Repository Structure

```
ScholarZone/
├── frontend/                  # React + Vite SPA
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   ├── pages/             # Route-level pages
│   │   ├── hooks/             # Custom React hooks
│   │   ├── lib/               # Utilities and API client
│   │   └── styles/            # Global styles
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── eslint.config.js
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── core/
│   │   │   └── config.py      # Environment configuration
│   │   ├── database.py        # Database initialization
│   │   ├── models.py          # 13 SQLAlchemy models
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── routers/           # API route handlers
│   │   │   ├── scholarships.py
│   │   │   ├── verification.py
│   │   │   ├── discovery.py
│   │   │   ├── admin_dashboard.py
│   │   │   └── admin_image_review.py
│   │   ├── scheduler_v2.py    # Verification engine
│   │   ├── seed.py            # Database seeding
│   │   └── services/          # Business logic
│   ├── tests/                 # 58 test files, 2,302 test functions
│   ├── Dockerfile             # Single-stage container build
│   ├── render.yaml            # Alternative deployment config
│   ├── requirements.txt       # Backend dependencies
│   ├── app/requirements.txt   # App-specific dependencies
│   ├── start.sh               # Container startup script
│   └── gh_token.txt           # GitHub token (secret; not committed in production)
├── docs/                      # Documentation (currently empty)
├── .github/
│   ├── workflows/
│   │   ├── ci.yml             # Backend tests, frontend lint, schema compat
│   │   ├── frontend.yml       # GitHub Pages deployment
│   │   ├── deploy.yml         # SnapDeploy production verification
│   │   └── verification-cron.yml  # Scheduled verification trigger
├── data/
│   └── verified_scholarships.py  # Seed data (DAAD, ICCR, curated)
└── README.md
```

---

## API Overview

The backend exposes a FastAPI application titled **ScholarZone API** (version 1.0.0).

- **Swagger/OpenAPI docs:** Available at `/docs` in non-production environments only. Disabled in production.
- **ReDoc:** Always disabled (`redoc_url=None`).
- **Base URL (production):** `https://scholarzone-api-2ee2d.containers.snapdeploy.app`

### Routers

| Router | Prefix | Purpose |
| :--- | :--- | :--- |
| Scholarships | `/scholarships` | Public scholarship browsing, filtering, comparison, and details |
| Internal | `/internal` | Verification trigger and image verification |
| Admin Images | `/admin/images` | Image review and approval |
| Discovery | `/internal/discover` | Country-level discovery trigger and candidate management |
| Admin Dashboard | `/admin` | Verification queue and review management |

### Key Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/` | Welcome message |
| GET | `/health` | Health check (200 OK, 503 if database not ready) |
| POST | `/internal/verify/trigger` | Trigger a verification round (authenticated) |
| POST | `/internal/discover/trigger` | Trigger country-level discovery (authenticated) |
| POST | `/internal/images/verify` | Persist verified images (authenticated) |
| GET | `/scholarships` | List scholarships with filtering and pagination |
| GET | `/scholarships/{id}` | Get scholarship details |
| GET | `/admin/queue` | Get verification review queue |

All internal endpoints require the `X-Verification-Secret` header matching the configured `SCHOLARZONE_VERIFICATION_SECRET`.

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL (or SQLite for local development)

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Copy and edit environment file
cp .env.example .env

# Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`, with Swagger docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

### Seeding

In non-production environments, the database is seeded automatically on startup from `data/verified_scholarships.py` (DAAD, ICCR, and curated entries). In production, seeding is skipped; the database is populated via migration.

---

## Environment Variables

### Backend (`.env`)

| Variable | Required | Description |
| :--- | :---: | :--- |
| `DATABASE_URL` | Yes | Database connection URL (PostgreSQL in production, SQLite in dev/test) |
| `ENVIRONMENT` | Yes | `development`, `test`, or `production` |
| `SCHOLARZONE_VERIFICATION_SECRET` | Yes (production) | Shared secret for verification trigger endpoints |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS allowlist |
| `VERIFICATION_SECRET` | Yes | Alias used by verification router |
| `MIN_IMAGE_DIMENSION` | No | Minimum image dimension in pixels (default 200) |
| `MIN_COVER` | No | Minimum cover image dimension (default 500) |
| `NON_CONTENT_REJECTION_THRESHOLD` | No | Non-content scoring threshold (default 1.5) |
| `RESEND_API_KEY` | No | Resend API key for email delivery |

**Production guard:** `config.py` rejects `sqlite` URLs when `ENVIRONMENT=production`, enforcing PostgreSQL in production deployments.

### Frontend

| Variable | Description |
| :--- | :--- |
| `VITE_API_URL` | Backend API base URL |

---

## Testing & CI

### Test Suite

- **58 test files** in `backend/tests/`
- **2,302 test functions**
- Latest full run: **2,222 passed, 1 failed, 39 warnings** in 554.79s

The suite covers the verification engine, image validation, discovery pipeline, lifecycle management, source health, schema compatibility, and API endpoints. One test currently fails; the failure is tracked and does not block the verification pipeline.

### CI Workflow (`.github/workflows/ci.yml`)

- Backend tests with pytest
- Frontend lint with ESLint
- Schema compatibility checks
- Smoke tests against the running application

### Manual Verification

`workflow_dispatch` runs of the verification trigger have completed successfully, confirming the trigger endpoint accepts requests and the verification round runs end-to-end.

---

## Deployment

### Frontend (GitHub Pages)

- **Workflow:** `.github/workflows/frontend.yml`
- **Output:** Built with `vite build` and deployed to GitHub Pages.
- **Access:** Served from the repository's GitHub Pages URL.

### Backend (SnapDeploy)

- **Platform:** SnapDeploy containers.
- **Production URL:** `https://scholarzone-api-2ee2d.containers.snapdeploy.app`
- **Workflow:** `.github/workflows/deploy.yml` verifies the production deployment after pushes.
- **Container:** Single-stage Docker build using `python:3.11-slim`, with a HEALTHCHECK every 30 seconds.
- **Alternative config:** `backend/render.yaml` exists as an alternative deployment configuration but Render is not the active production platform.

### Scheduled Verification

- **Workflow:** `.github/workflows/verification-cron.yml`
- **Schedule:** `7 */12 * * *` (every 12 hours at minute 7)
- **Behavior:** Wakes the SnapDeploy container, triggers verification, then triggers country-level discovery.

### Database

- **Production:** PostgreSQL (Neon).
- **Development/Testing:** SQLite.
- **Migration:** Production databases are populated via migration, not seeding.

---

## Security

- **Authentication:** Internal endpoints require the `X-Verification-Secret` header matching `SCHOLARZONE_VERIFICATION_SECRET`.
- **Rate limiting:** Verification triggers are rate-limited to a 60-second minimum interval, returning `429` for rapid or concurrent requests.
- **CORS:** Restricted to configured `ALLOWED_ORIGINS`; only `GET` methods and specific headers are permitted.
- **Input validation:** Pydantic schemas enforce request shapes; validation failures return `422` with a generic message.
- **Error handling:** Unhandled exceptions return a generic `500` response; details are logged server-side only.
- **Secrets:** No secrets are stored in the repository. `gh_token.txt` is present locally for operational scripts and must not be committed in production.
- **Production guard:** `config.py` rejects SQLite database URLs in production, enforcing PostgreSQL.

---

## Project Status

### Implemented

- Scholarship browsing, filtering, sorting, and details
- Country explorer with live counts
- Side-by-side comparison (up to 4 scholarships)
- Device-local saved scholarships
- Field-level verification engine
- Append-only verification audit trail
- Human review workflow with approve/reject
- Same-domain image discovery (max depth 2)
- Layered image validation with confidence levels
- Source health tracking
- Country-level discovery pipeline
- Lifecycle management
- Admin dashboard and image review interface
- Authentication pages (route gating partially applied)
- Scheduled verification via GitHub Actions cron
- Resend email integration
- Telemetry event recording

### Production

- Frontend deployed to GitHub Pages
- Backend deployed to SnapDeploy containers
- PostgreSQL (Neon) database
- Scheduled verification running on a 12-hour cycle

### Verification Proven

- CI pipeline passes on the current commit
- Manual `workflow_dispatch` verification runs complete successfully
- Native GitHub deployment verification passes

### Pending / In Progress

- One test currently failing (tracked, does not block the pipeline)
- Admin route gating not yet applied to all admin pages
- Scheduled runtime verification of the fixed cron workflow is pending the next scheduled run

### Not Yet Implemented

- Full multi-language localization
- Payment/integration with scholarship application portals
- Mobile native applications

---

## Roadmap

### Near Term

- Resolve the remaining failing test
- Apply route gating to all admin pages
- Validate scheduled verification runtime after the fixed cron workflow fires
- Populate `docs/` with design, API, and architecture documentation

### Medium Term

- Expand country-level discovery coverage
- Improve image confidence precision with additional validation signals
- Add knowledge graph exploration UI
- Enhance source health dashboards

### Long Term

- Multi-language scholarship listings
- Integration with official application portals
- Mobile applications (React Native)
- Advanced recommendation engine

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository and create a feature branch.
2. Run the local development setup (see [Local Development](#local-development)).
3. Make changes following existing code conventions.
4. Run the test suite: `pytest` in `backend/`.
5. Run frontend lint: `npm run lint` in `frontend/`.
6. Open a pull request describing the change.

**Commit guidelines:**

- Use conventional commit messages (e.g., `feat:`, `fix:`, `docs:`).
- Do not commit secrets, tokens, or credentials.
- Ensure CI passes before requesting review.

---

## License

This project is licensed under the terms of the repository LICENSE file. The LICENSE file is currently empty; a license should be added before public distribution.

---