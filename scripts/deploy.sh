#!/bin/bash
# One-command deployment for the whole stack locally
set -e

echo "🚀 Bootstrapping LogIQ Production Environment..."

# 1. Build and start containers
cd infra/docker
docker compose -f docker-compose.yml up -d --build

# 2. Wait for Postgres
echo "⏳ Waiting for PostgreSQL..."
sleep 10

# 3. Apply Migrations
echo "📦 Running Database Migrations..."
docker compose exec api alembic upgrade head

echo "✅ Deployment Complete. API running on http://localhost:8000"
echo "📊 Grafana available on http://localhost:3000 (admin/admin)"