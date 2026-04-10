#!/bin/bash

ACTION="${1:-status}"
PORT=5000

show_menu() {
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                          ║"
    echo "║          📹 ADAPTIVE ML CAMERA MONITOR - MANAGEMENT 📹                  ║"
    echo "║                                                                          ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|health|test|clean}"
    echo ""
    echo "Commands:"
    echo "  start      - Start the camera monitor"
    echo "  stop       - Stop the camera monitor"
    echo "  restart    - Restart the camera monitor"
    echo "  status     - Show running status"
    echo "  logs       - View live logs"
    echo "  health     - Check system health"
    echo "  test       - Run system tests"
    echo "  clean      - Clean up old snapshots/recordings"
    echo ""
}

start_service() {
    echo "🚀 Starting Adaptive ML Camera Monitor..."
    
    # Check if already running
    if pgrep -f "app_adaptive.py" > /dev/null; then
        echo "⚠️  Service already running (PID: $(pgrep -f 'app_adaptive.py'))"
        echo "   Use '$0 stop' first to stop it"
        exit 1
    fi
    
    cd ~/camera-monitor-advanced
    source venv/bin/activate
    
    nohup python3 app_adaptive.py > output.log 2>&1 &
    PID=$!
    
    sleep 3
    
    if pgrep -f "app_adaptive.py" > /dev/null; then
        echo "✅ Service started successfully (PID: $(pgrep -f 'app_adaptive.py'))"
        echo "   Access at: http://10.79.85.35:$PORT"
        echo "   Logs: tail -f ~/camera-monitor-advanced/adaptive_ml.log"
    else
        echo "❌ Failed to start service"
        echo "   Check logs: cat ~/camera-monitor-advanced/output.log"
        exit 1
    fi
}

stop_service() {
    echo "🛑 Stopping Adaptive ML Camera Monitor..."
    
    PIDS=$(pgrep -f "app_adaptive.py")
    
    if [ -z "$PIDS" ]; then
        echo "   Service not running"
        exit 0
    fi
    
    for PID in $PIDS; do
        kill $PID 2>/dev/null
        echo "   Stopped process $PID"
    done
    
    sleep 2
    
    # Force kill if still running
    PIDS=$(pgrep -f "app_adaptive.py")
    if [ ! -z "$PIDS" ]; then
        for PID in $PIDS; do
            kill -9 $PID 2>/dev/null
            echo "   Force killed process $PID"
        done
    fi
    
    echo "✅ Service stopped"
}

restart_service() {
    stop_service
    sleep 2
    start_service
}

show_status() {
    echo "📊 Service Status:"
    echo ""
    
    PIDS=$(pgrep -f "app_adaptive.py")
    
    if [ -z "$PIDS" ]; then
        echo "   Status: ❌ NOT RUNNING"
        echo ""
        echo "   Start with: $0 start"
    else
        echo "   Status: ✅ RUNNING"
        for PID in $PIDS; do
            echo "   PID: $PID"
            ps -p $PID -o pid,etime,pmem,pcpu,cmd --no-headers
        done
        echo ""
        echo "   Web UI: http://10.79.85.35:$PORT"
        echo "   Health: curl http://10.79.85.35:$PORT/api/health"
    fi
    echo ""
    
    echo "📁 Storage:"
    cd ~/camera-monitor-advanced
    echo "   Snapshots: $(find snapshots/ -type f 2>/dev/null | wc -l) files ($(du -sh snapshots/ 2>/dev/null | cut -f1))"
    echo "   Recordings: $(find recordings/ -type f 2>/dev/null | wc -l) files ($(du -sh recordings/ 2>/dev/null | cut -f1))"
    echo "   Models: $(find models/ -type f 2>/dev/null | wc -l) files ($(du -sh models/ 2>/dev/null | cut -f1))"
    echo "   Knowledge: $(find knowledge/ -type f 2>/dev/null | wc -l) files ($(du -sh knowledge/ 2>/dev/null | cut -f1))"
    echo ""
}

show_logs() {
    echo "📜 Live Logs (Ctrl+C to exit):"
    echo ""
    tail -f ~/camera-monitor-advanced/adaptive_ml.log
}

check_health() {
    echo "🏥 System Health Check:"
    echo ""
    
    # Check if service is running
    if ! pgrep -f "app_adaptive.py" > /dev/null; then
        echo "   ❌ Service: NOT RUNNING"
        exit 1
    else
        echo "   ✅ Service: RUNNING (PID: $(pgrep -f 'app_adaptive.py'))"
    fi
    
    # Check GPU
    if nvidia-smi &>/dev/null; then
        echo "   ✅ GPU: Available"
        nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader | head -1
    else
        echo "   ⚠️  GPU: Not detected"
    fi
    
    # Check webcam
    if [ -c /dev/video0 ]; then
        echo "   ✅ Webcam: /dev/video0 exists"
    else
        echo "   ❌ Webcam: Not found"
    fi
    
    # Check port
    if netstat -tuln 2>/dev/null | grep -q ":$PORT " || ss -tuln 2>/dev/null | grep -q ":$PORT "; then
        echo "   ✅ Port $PORT: Listening"
    else
        echo "   ⚠️  Port $PORT: Not listening"
    fi
    
    # Check API
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/health 2>/dev/null | grep -q "200"; then
        echo "   ✅ API: Healthy"
        
        # Get API status
        STATUS=$(curl -s http://localhost:$PORT/api/status 2>/dev/null)
        if [ ! -z "$STATUS" ]; then
            echo ""
            echo "   📊 Current Stats:"
            echo "$STATUS" | python3 -m json.tool 2>/dev/null | grep -E '(mode|confidence|fps|objects|faces)' | sed 's/^/     /'
        fi
    else
        echo "   ❌ API: Not responding"
    fi
    
    echo ""
}

run_tests() {
    cd ~/camera-monitor-advanced
    ./test_system.sh
}

clean_storage() {
    echo "🧹 Cleaning old files..."
    echo ""
    
    cd ~/camera-monitor-advanced
    
    # Clean snapshots older than 7 days
    SNAP_COUNT=$(find snapshots/ -type f -mtime +7 2>/dev/null | wc -l)
    if [ $SNAP_COUNT -gt 0 ]; then
        find snapshots/ -type f -mtime +7 -delete 2>/dev/null
        echo "   Deleted $SNAP_COUNT old snapshots (>7 days)"
    else
        echo "   No old snapshots to delete"
    fi
    
    # Clean recordings older than 7 days
    REC_COUNT=$(find recordings/ -type f -mtime +7 2>/dev/null | wc -l)
    if [ $REC_COUNT -gt 0 ]; then
        find recordings/ -type f -mtime +7 -delete 2>/dev/null
        echo "   Deleted $REC_COUNT old recordings (>7 days)"
    else
        echo "   No old recordings to delete"
    fi
    
    # Clean logs older than 30 days
    if [ -f adaptive_ml.log ]; then
        SIZE_BEFORE=$(du -h adaptive_ml.log | cut -f1)
        tail -n 10000 adaptive_ml.log > adaptive_ml.log.tmp && mv adaptive_ml.log.tmp adaptive_ml.log
        SIZE_AFTER=$(du -h adaptive_ml.log | cut -f1)
        echo "   Trimmed log file: $SIZE_BEFORE → $SIZE_AFTER"
    fi
    
    echo ""
    echo "✅ Cleanup complete"
}

case $ACTION in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    health)
        check_health
        ;;
    test)
        run_tests
        ;;
    clean)
        clean_storage
        ;;
    *)
        show_menu
        exit 1
        ;;
esac
