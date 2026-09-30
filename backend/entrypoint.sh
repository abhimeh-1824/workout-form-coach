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

# 2. Trap signals for graceful shutdown
cleanup() {
    echo ""
    echo "===> Received termination signal. Initiating graceful shutdown..."
    if [ -n "$WORKER_PID" ]; then
        echo "===> Stopping background worker (PID: $WORKER_PID)..."
        kill -TERM "$WORKER_PID" 2>/dev/null || true
    fi
    if [ -n "$SERVER_PID" ]; then
        echo "===> Stopping FastAPI Uvicorn server (PID: $SERVER_PID)..."
        kill -TERM "$SERVER_PID" 2>/dev/null || true
    fi
    wait "$SERVER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
    echo "===> All services terminated cleanly."
    exit 0
}

trap cleanup SIGTERM SIGINT

# 3. Start Background Video Processing Worker in background
echo "===> Launching background video processing worker..."
python -m app.worker.worker &
WORKER_PID=$!
echo "===> Background worker started with PID: $WORKER_PID"

# 4. Start FastAPI Uvicorn Server in background
PORT="${PORT:-8000}"
echo "===> Launching FastAPI Uvicorn server on 0.0.0.0:$PORT..."
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
SERVER_PID=$!
echo "===> FastAPI server started with PID: $SERVER_PID"

# 5. Monitor child processes; if either exits, initiate cleanup
wait -n "$SERVER_PID" "$WORKER_PID"
EXIT_CODE=$?
echo "===> A service exited with status code $EXIT_CODE. Shutting down container..."
cleanup
