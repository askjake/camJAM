# 🎥 CamJAM - Adaptive ML Camera Monitoring

Intelligent camera monitoring with adaptive learning and anomaly detection

## Features
- Adaptive Learning - Learns normal environment patterns
- Anomaly Detection - Alerts on unusual activity
- Object Recognition - YOLO/TFLite detection
- Face Detection - Identifies people
- Motion Analysis - Tracks movement patterns
- Web Dashboard - Real-time monitoring
- REST API - Easy integration

## Two Versions

**Lite (Raspberry Pi)**: Low-power edge deployment
- TFLite CPU inference
- 640x480 @ 10-15 FPS
- 300-frame learning
- ~$100 hardware

**Full (GPU)**: High-accuracy workstation  
- PyTorch CUDA inference
- 1280x720 @ 25-30 FPS
- 1000-frame learning
- Persistent knowledge

## Quick Start

### Lite Version
```bash
git clone git@github.com:askjake/camJAM.git
cd camJAM/lite-pi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app/app.py
```

### Full Version
```bash
git clone git@github.com:askjake/camJAM.git
cd camJAM/full-gpu
bash scripts/setup.sh
./scripts/start.sh
```

Access: http://localhost:5000

## Documentation
- Full version: See `full-gpu/docs/`
- Deployment guide, comparison report, troubleshooting

## License
MIT License - see LICENSE file

## Author
Jake (@askjake)
