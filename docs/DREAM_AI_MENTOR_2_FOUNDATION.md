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
- Deterministic AI Mentor 1.0 regression protection.

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

- Fresh PostgreSQL 18 schema and repeated upgrade validated locally.
- PostgreSQL 16 was not validated in this environment (instance
  unavailable); compatibility is not claimed without evidence.
