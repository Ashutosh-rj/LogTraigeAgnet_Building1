param(
  [Parameter(Mandatory = $true)][string]$JwtSecret,
  [Parameter(Mandatory = $true)][string]$DatabaseUrl,
  [Parameter(Mandatory = $true)][string]$SyncDatabaseUrl,
  [Parameter(Mandatory = $true)][string]$PostgresUser,
  [Parameter(Mandatory = $true)][string]$PostgresPassword
)

$ErrorActionPreference = "Stop"

kubectl apply -f "$PSScriptRoot\..\infra\kubernetes\base\namespace.yaml"
kubectl -n logiq create secret generic logiq-secrets `
  --from-literal=JWT_SECRET="$JwtSecret" `
  --from-literal=DATABASE_URL="$DatabaseUrl" `
  --from-literal=SYNC_DATABASE_URL="$SyncDatabaseUrl" `
  --from-literal=POSTGRES_USER="$PostgresUser" `
  --from-literal=POSTGRES_PASSWORD="$PostgresPassword" `
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k "$PSScriptRoot\..\infra\kubernetes\base"
kubectl -n logiq rollout status deployment/backend
kubectl -n logiq rollout status deployment/frontend

