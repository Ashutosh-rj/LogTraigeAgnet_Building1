# LogIQ Platform

LogIQ is a production-oriented incident intelligence SaaS platform. It provides authenticated incident management, AI-assisted triage, log ingestion, semantic search with pgvector, real-time WebSocket updates, Kafka-backed event processing, observability, and deployment assets for Docker Compose and Kubernetes.

## Local Development

```powershell
docker compose up --build
```

The default Compose profile starts PostgreSQL with pgvector, Kafka, the FastAPI backend, the Next.js frontend, Prometheus, Grafana, and Loki. Local development uses runtime-generated secrets unless values are injected; production mode refuses to start without explicit secrets.

## Services

- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- OpenAPI: http://localhost:8080/api/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## Production Deployment

1. Build and push backend/frontend images.
2. Create Kubernetes secrets with strong random values.
3. Apply `infra/kubernetes/base`.
4. Configure managed PostgreSQL with pgvector and Kafka for production.
5. Use `infra/terraform` as the cloud landing-zone blueprint.

## Repository Layout

```text
apps/
  backend/   FastAPI, SQLAlchemy, Alembic, Kafka, WebSockets, OpenTelemetry
  frontend/  Next.js 15, React 19, TailwindCSS, Zustand, TanStack Query
docs/        Architecture, security, operations, API notes
infra/       Docker, Kubernetes, Terraform, observability assets
scripts/     Validation and packaging helpers
tests/       End-to-end test specifications
```

