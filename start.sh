#!/usr/bin/env bash
# LectureAI — start both backend and frontend dev servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "Starting LectureAI backend on http://localhost:8000 ..."
.venv/bin/uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting LectureAI frontend on http://localhost:3000 ..."
python3 -m http.server 3000 --directory frontend &
FRONTEND_PID=$!

echo ""
echo "LectureAI is running:"
echo "  Frontend → http://localhost:3000"
echo "  Backend  → http://localhost:8000"
echo "  API docs → http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait for either process to exit; kill both on Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
