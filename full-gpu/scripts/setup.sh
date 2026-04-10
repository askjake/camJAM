#!/bin/bash
echo "=========================================================================="
echo "           ADVANCED CAMERA MONITOR SETUP"
echo "=========================================================================="

cd ~/camera-monitor-advanced

echo ""
echo "Checking Python environment..."
python3 --version

echo ""
echo "Checking GPU..."
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

echo ""
echo "Checking webcam..."
ls -la /dev/video* 2>/dev/null || echo "No webcam found"

echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install flask opencv-python numpy

echo ""
echo "Installing PyTorch with CUDA support..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

echo ""
echo "Installing AI frameworks..."
pip install ultralytics mediapipe

echo ""
echo "Testing PyTorch CUDA..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'CUDA Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

echo ""
echo "Setup complete!"
echo ""
echo "To start:"
echo "  cd ~/camera-monitor-advanced"
echo "  source venv/bin/activate"
echo "  python3 app.py"
echo ""
echo "Access at: http://10.79.85.35:5000"
