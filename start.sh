#!/bin/bash

# Catch Ctrl+C to stop both Backend and Frontend
trap 'echo "🛑 Shutting down the entire system..."; kill $BACKEND_PID; fuser -k 3000/tcp || true; exit' SIGINT SIGTERM

echo "🚀 Step 1: Starting Database (PostgreSQL)..."
docker compose up postgres -d

# Wait for 2 seconds to ensure PostgreSQL has started completely (especially for the first run)
echo "⏳ Waiting 2s for Database to stabilize..."
sleep 2

echo "🔄 Step 2: Running Database Migration (Alembic)..."
source .IotAgent_venv/bin/activate
alembic upgrade head

echo "⚙️ Step 3: Starting Backend Web (FastAPI) with DEBUG logs..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug &
BACKEND_PID=$!

echo "🌐 Step 4: Starting Frontend Web (Next.js)..."
# Load nvm if necessary to ensure using node 20
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 20

cd frontend || exit
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅===============================================✅"
echo "🌟 SYSTEM IS READY!"
echo "👉 Access Web Chat: http://localhost:3000"
echo "👉 Backend API: http://localhost:8000"
echo "👉 Press [Ctrl + C] to stop the entire system."
echo "✅===============================================✅"
echo ""

# Keep the script running to maintain processes
wait $BACKEND_PID $FRONTEND_PID
