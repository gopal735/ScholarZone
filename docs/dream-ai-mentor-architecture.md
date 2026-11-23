# Dream AI Mentor Architecture

## Overview
ScholarZone Dream AI Mentor is a grounded, deterministic-first scholarship
assistant built on top of the existing FastAPI + React architecture.

## Layers
- Conversation orchestration: `backend/app/services/mentor/service.py` (`ask`)
- Intent extraction: `backend/app/services/mentor/intents.py`
- Student profile: `StudentProfile` model + `/dashboard/profile` endpoints
- Catalogue discovery: `backend/app/services/mentor/discovery.py`
- Eligibility/matching: `backend/app/services/matching/`
- Evidence/provenance: `backend/app/services/mentor/evidence.py`
- Composition: `backend/app/services/mentor/compose.py`
- Context: `backend/app/services/mentor/context.py`
- Provider seam: `backend/app/services/mentor/provider.py`
- Supervisor integration: existing Supervisor APIs (PR #111 scope)

## Catalogue source of truth
Canonical `Scholarship` table with public visibility predicates.

## Profile lifecycle
- Stored in `student_profiles` (one per user).
- Validated through `MatchProfileRequest`.
- Deletable via `DELETE /dashboard/profile` (user-scoped).

## Privacy boundaries
- All private endpoints use `require_user`.
- Ownership enforced at query level.
- No cross-user leakage.
- No secrets in logs.

## Resource controls
- In-process rate limiter + in-flight caps for public discovery.
- Concurrency semaphore.

## Known limitations
- Full study planner, application copilot UI, and supervisor chat integration are partial.
- LLM provider disabled by default.
