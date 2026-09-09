#!/usr/bin/env bash
# ==============================================================================
# Smart Attendance System - All-in-One Startup Script
# Starts the FastAPI backend (if not running in Docker), opens Dashboard in browser,
# and launches Vision tracking with webcam access.
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

BACKEND_PID=""

cleanup() {
    echo -e "\n[Shutdown] Stopping local processes..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "======================================================"
echo "    Smart Attendance System - Startup Launcher"
echo "======================================================"

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
VENV_UVICORN="$PROJECT_ROOT/.venv/bin/uvicorn"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[ERROR] Virtual environment not found at .venv. Please create it first."
    exit 1
fi

# 1. Check if backend is already online (e.g. running in Docker or another terminal)
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo "[1/3] Backend server is already running on http://localhost:8000 (Docker or background service)!"
else
    echo "[1/3] Launching FastAPI backend server on http://localhost:8000..."
    "$VENV_UVICORN" app.main:app --app-dir backend --port 8000 > /dev/null 2>&1 &
    BACKEND_PID=$!

    # 2. Wait for Backend to be healthy
    echo "[2/3] Waiting for backend to respond at http://localhost:8000/health..."
    MAX_RETRIES=20
    COUNT=0
    READY=0
    while [ $COUNT -lt $MAX_RETRIES ]; do
        if curl -s http://localhost:8000/health | grep -q "ok"; then
            READY=1
            break
        fi
        sleep 0.5
        COUNT=$((COUNT + 1))
    done

    if [ $READY -eq 0 ]; then
        echo "[ERROR] Backend server failed to start within timeout."
        exit 1
    fi
    echo "[OK] Backend server is online!"
fi

# Open browser to Dashboard automatically on macOS
if command -v open > /dev/null; then
    echo "     Opening Dashboard in browser..."
    open "http://localhost:8000/dashboard"
fi

# 3. Launch Vision Service with webcam in foreground (Standby mode until instructor starts class on dashboard)
echo "[3/3] Launching Vision Service (Webcam & Tracking in Standby mode)..."
echo "     (Press 'q' in the video window or Ctrl+C in terminal to stop)"
echo "------------------------------------------------------"

"$VENV_PYTHON" vision/main.py --source 0 --group "Group A" --backend-url "http://localhost:8000" "$@"
