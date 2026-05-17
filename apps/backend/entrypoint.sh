#!/bin/sh

set -e

echo "Running database migrations..."

until alembic upgrade head; do
  echo "Migration failed. Retrying in 5 seconds..."
  sleep 5
done

echo "Starting FastAPI server..."

exec uvicorn app.main:app --host 0.0.0.0 --port 8080