# 🚀 CamJAM v2.2.1 - Fast Deployment Guide

## Quick Start (< 1 minute)

### Option 1: Fast Start Script (Recommended)

```bash
cd ~/camera-monitor-advanced
bash scripts/fast_start.sh
```

### Option 2: Systemd Service (Production)

```bash
# Copy service file
cp scripts/camjam.service ~/.config/systemd/user/

# Reload and enable
systemctl --user daemon-reload
systemctl --user enable camjam.service
systemctl --user start camjam.service

# Check status
systemctl --user status camjam.service
```

### Option 3: Manual Start

```bash
cd ~/camera-monitor-advanced
source venv/bin/activate
python3 app/app_adaptive.py
```

---

## Performance Optimizations

### Fast Startup Features
- **Lazy-load YOLO**: Model loads in background thread
- **Async CUDA**: Non-blocking GPU initialization
- **Pre-check deps**: Fails fast if dependencies missing
- **Optimized threads**: OMP_NUM_THREADS=4

### Expected Startup Times
- **Script launch**: < 1 second
- **Flask ready**: 2-3 seconds
- **YOLO loaded**: 3-5 seconds (background)
- **Total**: App responsive in ~3 seconds

---

## Service Management

### Systemd Commands

```bash
# Start service
systemctl --user start camjam.service

# Stop service
systemctl --user stop camjam.service

# Restart service
systemctl --user restart camjam.service

# View status
systemctl --user status camjam.service

# View logs (live)
journalctl --user -u camjam.service -f

# View recent logs
journalctl --user -u camjam.service -n 100
```

### Fast Start Script

```bash
# Start
bash scripts/fast_start.sh

# Check if running
ps aux | grep app_adaptive

# View logs
tail -f logs/app.log

# Stop
pkill -f app_adaptive.py
```

---

## Troubleshooting

### App Won't Start

**Check dependencies:**
```bash
source venv/bin/activate
python3 -c "import torch, cv2, flask"
```

**Check CUDA:**
```bash
python3 -c "import torch; print(torch.cuda.is_available())"
nvidia-smi
```

**Check camera:**
```bash
v4l2-ctl --list-devices
ls -l /dev/video*
```

### Slow Startup

If startup takes > 10 seconds:

1. **Check YOLO download**: First run downloads model
   ```bash
   ls -lh yolov8n.pt  # Should be ~6MB
   ```

2. **Check GPU initialization**: 
   ```bash
   # View startup logs
   tail -f logs/app.log
   ```

3. **Disable CUDA** (CPU fallback):
   ```bash
   export CUDA_VISIBLE_DEVICES=""
   bash scripts/fast_start.sh
   ```

### Service Won't Start

```bash
# Check service file
cat ~/.config/systemd/user/camjam.service

# Reload daemon
systemctl --user daemon-reload

# Check paths
ls -l ~/camera-monitor-advanced/venv/bin/python3
ls -l ~/camera-monitor-advanced/app/app_adaptive.py

# View detailed status
systemctl --user status camjam.service -l
```

---

## Monitoring

### Health Check

```bash
# API status
curl http://localhost:5000/api/status | jq

# Quick check
curl -I http://localhost:5000/
```

### Performance Metrics

```bash
# CPU/Memory usage
ps aux | grep app_adaptive

# GPU usage
nvidia-smi -l 1

# FPS and learning progress
watch -n 1 'curl -s http://localhost:5000/api/status | jq ".fps, .frames_learned, .confidence"'
```

### Logs

```bash
# Application logs
tail -f logs/app.log

# Error logs (if using systemd)
tail -f logs/error.log

# Systemd journal
journalctl --user -u camjam.service -f
```

---

## Configuration

### Environment Variables

```bash
# Fast startup (default)
export CUDA_LAUNCH_BLOCKING=0
export OMP_NUM_THREADS=4
export PYTHONUNBUFFERED=1

# Debug mode (slower but more detailed)
export CUDA_LAUNCH_BLOCKING=1
export PYTHONUNBUFFERED=1
export FLASK_ENV=development
```

### App Configuration

Edit `app/app_adaptive.py`:

```python
# Learning
LEARNING_FRAMES_THRESHOLD = 1000
CONTINUOUS_LEARNING = True
SAVE_INTERVAL = 100

# Detection
ANOMALY_THRESHOLD = 0.35
CONFIDENCE_THRESHOLD = 0.80

# Recording
ANOMALY_BUFFER_SECONDS = 5
ANOMALY_RECORD_AFTER_SECONDS = 5
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check disk space for clips
- Review anomaly logs

**Weekly:**
- Rotate old clips (> 7 days)
- Update GitHub backup

**Monthly:**
- Update dependencies
- Review learning models

### Cleanup Commands

```bash
# Remove old clips (> 7 days)
find app/anomaly_clips/ -name "*.mp4" -mtime +7 -delete

# Clear logs (> 30 days)
find logs/ -name "*.log" -mtime +30 -delete

# Backup knowledge
tar -czf knowledge_backup_$(date +%Y%m%d).tar.gz app/knowledge/
```

---

## Updates

### Pull Latest from GitHub

```bash
cd ~/camJAM
git pull origin main

# Restart service
systemctl --user restart camjam.service
```

### Manual Update

```bash
# Backup current
cp app/app_adaptive.py app/app_adaptive.py.backup

# Copy new version
# ... update files ...

# Restart
bash scripts/fast_start.sh
```

---

## Support

- **GitHub**: https://github.com/askjake/camJAM
- **Issues**: https://github.com/askjake/camJAM/issues
- **Docs**: See `/docs` directory
