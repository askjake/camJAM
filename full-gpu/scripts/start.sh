#!/bin/bash

cd ~/camera-monitor-advanced
source venv/bin/activate

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                          ║"
echo "║      🧠 ADAPTIVE ML CAMERA MONITOR - STARTING 🧠                        ║"
echo "║                                                                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Access at: http://10.79.85.35:5000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 app_adaptive.py
