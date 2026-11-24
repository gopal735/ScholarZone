# Dream AI Mentor 2.0 Foundation

## Status

This branch provides a focused foundation PR. It is not a complete,
production-ready multi-agent AI system.

## Implemented

- AI Gateway interfaces, provider capability metadata, routing policy,
  structured-output validation hooks, retry, timeout, cancellation,
  health reporting, and error normalization. `DisabledProvider` is the
  default provider. `RecordingProvider` is test-only and cannot be
  selected in production configuration.
- Bounded orchestrator primitives: task states and explicit valid
  transitions, ownership checks, deny-by-default tool registry,
  permission enforcement, budgets, cancellation, and cooperative
  planning limits. Arbitrary synchronous Python plan functions cannot
  be forcibly interrupted; duration and size limits are checked
  cooperatively.
- Persisted Study Planner (study_plans, study_plan_tasks) with owner
  filtering, soft delete, task ordering, and unique task-position
  constraints.
- Study Planner REST API with authentication, owner filtering, bounded
  task collections, and optimistic version checks (HTTP 409 on stale
  writes when a version is supplied).
- Study Planner frontend with loading, empty, error, and unauthenticated
  states.
- Runtime Study Planner schema readiness guard: every `/study-plans`
  endpoint verifies the required tables and columns before executing
  planner queries. Missing or invalid schema returns a controlled HTTP
  503 with a generic message. General database liveness (`/health`)
  remains separate from feature readiness, so public scholarship APIs
  continue to work when only the planner schema is unavailable.
- Deterministic AI Mentor 1.0 regression protection.

## Study Planner API

Endpoints (all require authentication):

- GET /study-plans
- POST /study-plans
- GET /study-plans/{plan_id}
- PATCH /study-plans/{plan_id}
- DELETE /study-plans/{plan_id}
- POST /study-plans/{plan_id}/tasks
- PATCH /study-plans/tasks/{task_id}
- DELETE /study-plans/tasks/{task_id}

Contracts:

- Plan updates require `version`; stale versions return HTTP 409.
- Task updates require `version`; stale versions return HTTP 409.
- Successful updates increment `version` and return the new version.
- Delete is soft (`status = "deleted"`) and increments the plan version.
- Deleted plans are hidden from list/get and cannot be patched back.
- Each plan/task belongs to one user; cross-user access returns 404.
- A plan holds at most 100 tasks.

## Schema Readiness

Required tables:

- study_plans
- study_plan_tasks

Required columns:

- study_plans: id, user_id, title, status, version
- study_plan_tasks: id, plan_id, title, status, version,
  related_scholarship_id

Runtime behavior:

- Missing tables return HTTP 503.
- Missing required columns return HTTP 503.
- Database inspection errors return HTTP 503.
- No SQL or schema details are exposed.
- Valid schema permits normal authenticated usage.
- Readiness is checked per request against the database in use, so it
  recovers when the schema becomes valid without a restart.
- Public scholarship endpoints are not gated by planner readiness.

## Production Migration

- Canonical DDL lives in `backend/app/supervisor_ddl.py`
  (`NEW_TABLE_DDL`, `NEW_TABLE_INDEXES`, `REQUIRED_NEW_TABLES`).
- `backend/migrate_schema.py` consumes the canonical DDL.
- Production startup does not run `create_all()` or automatic DDL for
  the Study Planner; the manual GitHub Actions workflow
  (`student-dashboard-migration.yml`) remains canonical.
- Migration defaults to dry-run (`apply=false`); apply requires explicit
  authorization.
- The application does not claim the planner schema is deployed merely
  because the code is deployed.

## AI Gateway

- Policy timeout defaults are honored when no explicit timeout is
  supplied.
- An explicit `timeout_seconds` overrides the policy timeout.
- Provider adapters receive the resolved timeout.
- `DisabledProvider` is the default; `RecordingProvider` is test-only.

## Orchestrator

- Bounded behavior with cooperative limits.
- Cancellation is cooperative, not forcible.

## Product Scope

- Foundation PR, not a complete production multi-agent AI system.
- No external LLM adapter claims.
- No RAG/vector database claims.
- No streaming execution claims.
- No persistent conversational memory claims.

## Not Implemented

- Real external LLM provider adapters.
- Gateway-to-orchestrator connected execution.
- User-facing AI agent execution endpoint.
- New RAG integration or external vector database.
- Persistent conversational memory.
- Application Copilot.
- Supervisor chat.
- Streaming response UI.

## PostgreSQL Validation

- Fresh PostgreSQL 18 schema and repeated upgrade validated locally
  during this remediation.
- PostgreSQL 16 instance was available but crashed on client connections
  in this environment; PG16 compatibility is not claimed from this run.
  CI PG16/PG18 checks remain the authoritative validation.
