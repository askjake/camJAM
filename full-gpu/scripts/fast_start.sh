#!/bin/bash
# Fast Startup Script for CamJAM v2.2.0
# Optimized to minimize startup delays

set -e

BASE_DIR="$HOME/camera-monitor-advanced"
cd "$BASE_DIR"

echo "🚀 Starting CamJAM v2.2.0 (Fast Mode)..."

# Activate virtualenv
source venv/bin/activate

# Set optimizations
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4
export CUDA_LAUNCH_BLOCKING=0  # Async CUDA for faster startup

# Pre-check dependencies (fail fast if missing)
python3 -c "import torch, cv2, flask" 2>/dev/null || {
    echo "❌ Missing dependencies. Run: bash scripts/setup.sh"
    exit 1
}

# Start app in background with logging
echo "⚡ Launching application..."
nohup python3 app/app_adaptive.py > logs/app.log 2>&1 &
APP_PID=$!

echo "✅ App started with PID: $APP_PID"
echo "📊 Logs: tail -f $BASE_DIR/logs/app.log"
echo "🌐 URL: http://localhost:5000"

# Wait for app to be ready (max 10 seconds)
echo "⏳ Waiting for app to be ready..."
for i in {1..20}; do
    if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
        echo "✅ App is ready! (took ${i}s)"
        exit 0
    fi
    sleep 0.5
done

echo "⚠️  App started but health check timeout. Check logs."
exit 0
