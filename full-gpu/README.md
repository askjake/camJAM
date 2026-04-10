# 🧠 CamJAM Full-GPU - Advanced Adaptive ML Camera Monitor

**Version 2.2.0** - Intelligent Camera Monitoring with Adaptive Learning & Anomaly Video Capture

---

## 🚀 What's New in v2.2

### 📹 **Automatic Anomaly Video Capture**

The system now automatically records video clips when anomalies are detected:

- **5 seconds before** anomaly (pre-buffer)
- **5 seconds after** anomaly (post-buffer)  
- **10 second total** clips with context
- Automatic thumbnail generation
- Organized storage with descriptive filenames

Example filename: `anomaly_20260410_142350_MEDIUM_motion_fb1f5b02.mp4`

---

## ✨ Core Features

### 🎯 Adaptive Learning System
- **Learns normal patterns** from environment over time
- **Continuous learning** adapts to changing conditions
- **Persistent knowledge** saved to disk (every 100 frames)
- **1000-frame training** for initial baseline

### 🚨 Anomaly Detection
- **Multi-level severity**: LOW, MEDIUM, HIGH, CRITICAL
- **Automatic video recording** on anomalies
- **Object tracking** with confidence scores
- **Motion analysis** with velocity tracking
- **Face detection** for people identification

### 📹 Video Recording
- **Circular buffer** maintains last 5 seconds of frames
- **Automatic trigger** on anomaly detection
- **MP4 format** with hardware-accelerated encoding
- **Thumbnail preview** auto-generated
- **Thread-safe** recording system

### 🖥️ Web Interface
- **Live video feed** with annotations
- **Real-time statistics** dashboard
- **Anomaly history** with severity indicators
- **Learning progress** visualization
- **REST API** for integration

### ⚡ GPU Acceleration
- **CUDA support** for PyTorch inference
- **YOLOv8** object detection
- **Real-time processing** at 25-30 FPS
- **1280x720** high-resolution capture

---

## 📋 Requirements

### Hardware
- **GPU**: NVIDIA GPU with CUDA support (GTX 1060+ recommended)
- **RAM**: 4GB minimum (8GB recommended)
- **Webcam**: USB or built-in camera
- **Storage**: 10GB+ for clips and models

### Software
- Python 3.8+
- CUDA 11.0+
- OpenCV 4.5+
- PyTorch 2.0+ with CUDA
- Flask 2.0+

---

## 🔧 Installation

```bash
# Clone repository
git clone git@github.com:askjake/camJAM.git
cd camJAM/full-gpu

# Run setup script
bash scripts/setup.sh

# Start the system
bash scripts/start.sh
```

---

## 🎮 Usage

### Web Interface
Open browser to: **http://localhost:5000**

### API Endpoints

```bash
# System status
curl http://localhost:5000/api/status

# Get anomaly clip
curl http://localhost:5000/api/anomaly_clip/<clip_id> -o clip.mp4

# Get thumbnail
curl http://localhost:5000/api/anomaly_thumbnail/<clip_id> -o thumb.jpg

# Anomaly history
curl http://localhost:5000/api/anomalies
```

---

## 📂 Directory Structure

```
full-gpu/
├── app/
│   ├── app_adaptive.py        # Main application
│   ├── anomaly_recorder.py    # Video recording module
│   ├── knowledge/             # Learned patterns (auto-created)
│   ├── anomaly_clips/         # Recorded video clips (auto-created)
│   ├── snapshots/             # Manual snapshots (auto-created)
│   └── recordings/            # Manual recordings (auto-created)
├── scripts/
│   ├── setup.sh               # Installation script
│   ├── start.sh               # Start service
│   └── manage.sh              # Service management
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 📝 License
MIT License - See LICENSE file

---

## 👤 Author
**Jake** (@askjake) - [GitHub](https://github.com/askjake/camJAM)

**Built with ❤️ for intelligent home monitoring**
