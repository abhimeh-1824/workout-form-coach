#!/bin/bash
set -e

echo "=========================================================="
echo " Starting Workout Form Coach Unified Backend Service"
echo " (FastAPI API Server + Background Queue Worker)"
echo "=========================================================="

# 1. Apply database migrations if DATABASE_URL is configured
if [ -n "$DATABASE_URL" ]; then
    echo "===> Running database migrations via Alembic..."
    alembic upgrade head || {
        echo "WARNING: Alembic migration encountered an error. The database may still be initializing or unreachable."
    }
else
    echo "===> DATABASE_URL not set; skipping Alembic migrations."
fi

# 2. Launch FastAPI with Embedded Background Queue Worker
PORT="${PORT:-8000}"
echo "===> Launching FastAPI Uvicorn server on 0.0.0.0:$PORT (Queue Worker embedded in lifespan)..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
