# 🧠 Adaptive ML Camera Monitor

**Advanced GPU-Accelerated Intelligent Surveillance System**

## Quick Start

```bash
cd ~/camera-monitor-advanced
./start.sh
```

Access at: **http://10.79.85.35:5000**

---

## Features

✅ **Deep Learning Anomaly Detection** - Autoencoder learns normal patterns  
✅ **GPU-Accelerated (RTX 3090)** - 25-30 FPS at 1280x720  
✅ **Adaptive Learning** - 1,000 frame learning threshold  
✅ **YOLOv8 Object Detection** - Identifies objects and learns their patterns  
✅ **Face Detection** - Tracks people in scene  
✅ **Motion Analysis** - Learns typical movement patterns  
✅ **Smart Alerting** - 3 severity levels, multiple anomaly types  
✅ **Persistent Knowledge** - Saves learned patterns to disk  
✅ **Web Interface** - Real-time dashboard with analytics  

---

## System Requirements

- **GPU**: NVIDIA GPU with CUDA support (RTX 3090 recommended)
- **RAM**: 4GB+ (125GB available)
- **Webcam**: USB camera (Logitech Pro 9000 detected)
- **Python**: 3.10+ 
- **OS**: Ubuntu 22.04 or compatible

---

## Learning Phases

### Phase 1: INITIAL (0-1000 frames, ~33 seconds)
- 🔄 Yellow badge "LEARNING"
- Building baseline of normal patterns
- No anomaly detection yet
- Confidence: 0-80%

### Phase 2: TRAINED (1000+ frames, 80%+ confidence)
- ✅ Green badge "TRAINED"
- Active anomaly detection
- Alerts on unusual patterns
- Confidence: 80-100%

### Phase 3: CONTINUOUS (Optional)
- 🔁 Cyan badge "CONTINUOUS LEARNING"
- Adapts to gradual changes
- Maintains high accuracy

---

## Anomaly Types

### 1. Scene Anomalies
- Unusual lighting or background changes
- New objects in scene
- Camera repositioning

### 2. Object Anomalies  
- Unknown object types
- Objects at wrong time of day
- Objects in unusual locations

### 3. Motion Anomalies
- Unusual activity intensity
- Movement in unexpected areas

---

## Controls

| Button | Function |
|--------|----------|
| 📸 Snapshot | Capture current frame |
| 💾 Save Knowledge | Manually save learned patterns |
| 🔄 Reset Learning | Start learning from scratch |

---

## API Endpoints

```
GET  /                     - Web UI
GET  /video_feed           - MJPEG stream
GET  /snapshot             - Capture frame
GET  /api/status           - System status
GET  /api/anomalies        - Recent alerts
POST /api/save_knowledge   - Save patterns
POST /api/reset_learning   - Reset system
GET  /api/health           - Health check
```

---

## Configuration

Edit `app_adaptive.py`:

```python
LEARNING_FRAMES_THRESHOLD = 1000   # Frames before trained mode
CONTINUOUS_LEARNING = True         # Enable continuous adaptation
ANOMALY_THRESHOLD = 0.35           # Scene anomaly sensitivity
CONFIDENCE_THRESHOLD = 0.80        # Required confidence to activate
SAVE_INTERVAL = 100                # Auto-save frequency
```

---

## Troubleshooting

### Camera not detected
```bash
ls -la /dev/video*
sudo usermod -a -G video montjac
```

### CUDA not available
```bash
python3 -c "import torch; print(torch.cuda.is_available())"
nvidia-smi
```

### View logs
```bash
tail -f ~/camera-monitor-advanced/adaptive_ml.log
grep "ANOMALY" ~/camera-monitor-advanced/adaptive_ml.log
```

---

## Performance

**Expected (RTX 3090):**
- FPS: 25-30
- GPU: 15-30%
- VRAM: 2-3GB
- Latency: <100ms

---

## Files

```
camera-monitor-advanced/
├── app_adaptive.py       ⭐ Main application
├── start.sh              🚀 Launcher
├── DEPLOYMENT_REPORT.md  📝 Full documentation
├── README.md             📖 This file
├── venv/                 Python environment
├── snapshots/            Captured images
├── knowledge/            Learned patterns
└── models/               Trained models
```

---

## Support

For detailed documentation, see: `DEPLOYMENT_REPORT.md`

**Web Interface:** http://10.79.85.35:5000  
**Health Check:** http://10.79.85.35:5000/api/health  
**Logs:** `~/camera-monitor-advanced/adaptive_ml.log`

---

**Deployed:** 2026-04-10  
**Version:** 2.0  
**System:** montjac@10.79.85.35 (Dual RTX 3090)
