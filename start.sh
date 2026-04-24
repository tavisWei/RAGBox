#!/bin/bash
set -e

echo "🚀 Starting RAG Platform..."

API_PORT=8000
VUE_PORT=3003

cd "$(dirname "$0")"

# Kill existing processes on target ports
echo "Cleaning up existing processes..."
lsof -i :$API_PORT | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true
lsof -i :$VUE_PORT | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 2

export PYTHONPATH=$(pwd):$PYTHONPATH

# Start backend
echo "Starting backend on port $API_PORT..."
nohup python api/main.py > backend.log 2>&1 &
API_PID=$!

# Wait for backend with 30s timeout
for i in $(seq 1 30); do
    sleep 1
    if curl -s --noproxy "*" http://localhost:$API_PORT/api/v1/health > /dev/null 2>&1; then
        echo "✅ Backend started (PID: $API_PID)"
        break
    fi
    if ! kill -0 $API_PID 2>/dev/null; then
        echo "❌ Backend failed to start"
        exit 1
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Backend startup timeout (30s)"
        kill $API_PID 2>/dev/null || true
        exit 1
    fi
done

# Start frontend
echo "Starting Vue frontend on port $VUE_PORT..."
cd web-vue
nohup npm run dev > ../frontend.log 2>&1 &
VUE_PID=$!

# Wait for frontend with 30s timeout
for i in $(seq 1 30); do
    sleep 1
    if curl -s --noproxy "*" -I http://localhost:$VUE_PORT > /dev/null 2>&1; then
        echo "✅ Frontend started (PID: $VUE_PID)"
        break
    fi
    if ! kill -0 $VUE_PID 2>/dev/null; then
        echo "❌ Frontend failed to start"
        kill $API_PID 2>/dev/null || true
        exit 1
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Frontend startup timeout (30s)"
        kill $API_PID 2>/dev/null || true
        kill $VUE_PID 2>/dev/null || true
        exit 1
    fi
done

echo ""
echo "==================================="
echo "✅ RAG Platform Started!"
echo ""
echo "🌐 Frontend: http://localhost:$VUE_PORT"
echo "🔌 Backend API: http://localhost:$API_PORT"
echo "📊 Health Check: http://localhost:$API_PORT/api/v1/health"
echo ""
echo "👤 Default Admin Account:"
echo "   Email: admin@example.com"
echo "   Password: admin"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop"

trap "echo 'Stopping...'; kill $API_PID $VUE_PID 2>/dev/null; exit 0" INT TERM
wait
