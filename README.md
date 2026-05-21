# LogIQ Platform

**LogIQ** is a production-grade enterprise SaaS platform designed to solve the most painful problem in Site Reliability Engineering (SRE): alert fatigue and incident downtime. It provides authenticated incident management, AI-assisted root cause triage, high-throughput log ingestion, semantic search, and real-time observability.

This is not a toy project—LogIQ is built with resiliency, security, and scalability as core tenets, leveraging an industry-standard technology stack.

## Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), Alembic
- **Frontend**: Node.js 22, Next.js 15, React 19, TailwindCSS, Zustand, TanStack Query
- **Data & Streaming**: PostgreSQL 16 (with pgvector), Apache Kafka, Redis
- **Observability**: OpenTelemetry, Prometheus, Grafana, Loki, Tempo
- **AI Triage**: LangChain/LLMs with RAG for institutional memory (OpenAI/Anthropic)
- **Infrastructure**: Docker Compose, Kubernetes, Helm, Terraform

## Key Features

1. **Automated Incident Triage (AI Agents)**: A multi-agent system (Planner, Executor, Verifier) automatically analyzes incoming error streams, correlates them with historical incidents using vector embeddings, and provides actionable root cause hypotheses before an engineer even starts debugging.
2. **Real-Time Observability**: Ingests high-throughput logs via Kafka and streams them instantly to the Next.js frontend command center via WebSockets.
3. **Production-Grade Resiliency**: End-to-end distributed tracing via OpenTelemetry, robust Prometheus metrics, and centralized logging with Loki.
4. **Enterprise Security**: Redis-backed distributed rate limiting, secondary JWT key rotation, strict password enforcement, account lockout policies, SQL injection payload sanitization, and body size limits.

## Quickstart (Local Development)

The local development environment is fully containerized. A single command provisions the entire stack (Postgres, Kafka, Redis, Backend, Frontend, and the Observability suite).

```powershell
docker compose up --build
```

### Services
Once the containers are running and healthy, the following services are available:

- **Frontend Dashboard**: http://localhost:3000 (Default Admin: `admin@logiq.local` / `SuperSecret123!`)
- **Backend API**: http://localhost:8080
- **OpenAPI Docs**: http://localhost:8080/api/docs
- **Grafana (Dashboards)**: http://localhost:3001
- **Prometheus**: http://localhost:9090

> **Note**: For local development, missing `.env` variables use safe defaults or randomly generated strings. In production (`ENVIRONMENT=production`), the system enforces strict validation and will refuse to start without explicit, secure credentials.

## Deployment & Operations

For production deployments, LogIQ is designed to run on Kubernetes (e.g., AWS EKS, GCP GKE) using Helm.

1. Build and push images to your container registry.
2. Provision cloud infrastructure using the provided Terraform blueprints (`infra/terraform/`).
3. Deploy the application via Helm (`infra/helm/logiq/`), ensuring strong random values are provided for all Kubernetes secrets.
4. See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive into the system's components, data flows, and security model.

## Documentation Overview

- [ARCHITECTURE.md](ARCHITECTURE.md): System architecture, data flow diagrams, and agent details.
- [CHANGES.md](CHANGES.md): Changelog of major milestones and critical security fixes.
- `docs/`: Additional operations, security, and API notes.
