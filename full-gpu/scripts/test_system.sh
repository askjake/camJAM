#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                          ║"
echo "║          🧪 ADAPTIVE ML CAMERA MONITOR - SYSTEM TEST 🧪                 ║"
echo "║                                                                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

cd ~/camera-monitor-advanced

echo "1️⃣  Testing Python environment..."
source venv/bin/activate
python3 --version
echo ""

echo "2️⃣  Testing PyTorch CUDA..."
python3 << 'PYEOF'
import torch
print(f"   PyTorch: {torch.__version__}")
print(f"   CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   CUDA Device: {torch.cuda.get_device_name(0)}")
    print(f"   CUDA Version: {torch.version.cuda}")
PYEOF
echo ""

echo "3️⃣  Testing webcam access..."
python3 << 'PYEOF'
import cv2
cap = cv2.VideoCapture(0)
if cap.isOpened():
    ret, frame = cap.read()
    if ret:
        print(f"   ✅ Webcam working: {frame.shape}")
    else:
        print("   ❌ Failed to read frame")
    cap.release()
else:
    print("   ❌ Failed to open webcam")
PYEOF
echo ""

echo "4️⃣  Testing YOLO..."
python3 << 'PYEOF'
try:
    from ultralytics import YOLO
    model = YOLO('yolov8n.pt')
    print("   ✅ YOLO loaded successfully")
except Exception as e:
    print(f"   ❌ YOLO error: {e}")
PYEOF
echo ""

echo "5️⃣  Testing OpenCV face detection..."
python3 << 'PYEOF'
import cv2
try:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    print("   ✅ Face detection loaded")
except Exception as e:
    print(f"   ❌ Face detection error: {e}")
PYEOF
echo ""

echo "6️⃣  Checking directories..."
for dir in snapshots recordings models knowledge; do
    if [ -d "$dir" ]; then
        echo "   ✅ $dir/ exists"
    else
        echo "   ❌ $dir/ missing"
        mkdir -p "$dir"
    fi
done
echo ""

echo "7️⃣  Testing Flask imports..."
python3 << 'PYEOF'
try:
    from flask import Flask
    import numpy as np
    import cv2
    print("   ✅ All Flask dependencies available")
except Exception as e:
    print(f"   ❌ Import error: {e}")
PYEOF
echo ""

echo "8️⃣  Checking GPU memory..."
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used --format=csv,noheader
echo ""

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║                         ✅ SYSTEM TEST COMPLETE                          ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Ready to start with: ./start.sh"
echo ""
