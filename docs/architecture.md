# Architecture

LogIQ is organized as a modular monorepo with independent frontend and backend deployables.

## Backend

The backend follows service-layer clean architecture:

- `api`: FastAPI routers and request/response contracts.
- `core`: configuration, logging, security, rate limiting, telemetry.
- `db`: SQLAlchemy async engine, sessions, models, and migrations.
- `repositories`: persistence accessors with typed query methods.
- `services`: business capabilities such as auth, incident workflow, triage, notifications, vector search, audit, Kafka events, and WebSockets.

All writes pass through service methods that perform validation, audit logging, and event publication. API dependencies enforce JWT authentication and RBAC.

## Data Plane

PostgreSQL 16 stores normalized relational data. The `pgvector` extension stores deterministic embeddings for incidents, logs, and triage reports. Similarity search is exposed through the `/api/v1/search` endpoints.

## Event Plane

Kafka carries domain events for incidents, logs, triage reports, notifications, and audit entries. The backend publishes events after database commits and can run a consumer worker for asynchronous enrichment.

## Real-Time Plane

Authenticated WebSocket clients connect at `/api/v1/ws`. The connection manager tracks sessions, broadcasts incident and notification events, and records lifecycle events to the database.

## Observability

The backend emits structured JSON logs with request IDs, Prometheus metrics at `/metrics`, OpenTelemetry traces, and health endpoints. Docker Compose includes Prometheus, Grafana, and Loki with provisioned dashboards.

## Security

Authentication uses access JWTs plus refresh-token rotation. Passwords are hashed with bcrypt. RBAC is enforced at route boundaries. Runtime settings validate CORS, secrets, token TTLs, and production-only hardening rules.

