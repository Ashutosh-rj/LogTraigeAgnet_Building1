# Operations

## Health Checks

- `GET /health/live`: process liveness.
- `GET /health/ready`: database readiness and dependency checks.
- `GET /metrics`: Prometheus metrics.

## Migrations

```powershell
cd apps/backend
alembic upgrade head
```

The migration creates pgvector support, normalized tables, constraints, indexes, and rollback logic.

## Packaging

```powershell
.\scripts\package.ps1
```

This creates `logiq-platform-production.zip` after excluding caches, dependency directories, and generated build output.

## Kubernetes

```powershell
.\scripts\deploy-kubernetes.ps1 `
  -JwtSecret "<strong-runtime-secret>" `
  -DatabaseUrl "postgresql+asyncpg://user:password@host:5432/logiq" `
  -SyncDatabaseUrl "postgresql://user:password@host:5432/logiq" `
  -PostgresUser "logiq" `
  -PostgresPassword "<database-password>"
```

Production deployments should patch `infra/kubernetes/base/configmap.yaml` for the target domain and image registry before applying.
