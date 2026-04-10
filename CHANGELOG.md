# Changelog - CamJAM

## [v2.2.1] - 2026-04-10

### ⚡ PERFORMANCE: Fast Startup & Service Management

Optimized startup time and added professional service management.

#### Features Added
- **Fast Startup Script**: App ready in ~3 seconds (vs 10+ seconds before)
- **Systemd Service**: Production-ready service management
- **Lazy-load YOLO**: Model loads in background thread (non-blocking)
- **Async CUDA**: Non-blocking GPU initialization
- **Service Commands**: Start/stop/restart with systemctl
- **Auto-restart**: Service auto-restarts on failure
- **Centralized Logs**: Unified logging in logs/ directory

#### Files Added
- `scripts/fast_start.sh` - Optimized startup script
- `scripts/camjam.service` - Systemd service configuration
- `docs/DEPLOYMENT.md` - Complete deployment guide
- `logs/` directory - Centralized logging

#### Performance Improvements
- Startup time: 10s → 3s (70% faster)
- YOLO loading: Non-blocking background thread
- Environment optimization: CUDA_LAUNCH_BLOCKING=0
- Thread optimization: OMP_NUM_THREADS=4

#### Deployment Changes
- Repository structure: Changed to symlink structure
- GitHub-first: Pull from GitHub for updates
- Service management: Systemd user service
- Log management: Separate app and error logs

## [v2.2.0] - 2026-04-10
### 🎥 NEW FEATURE: Automatic Anomaly Video Capture

Added comprehensive video recording system that automatically captures video clips when anomalies are detected.

#### Features Added
- **Pre-buffer Recording**: Captures 5 seconds before anomaly (circular buffer)
- **Post-buffer Recording**: Continues recording 5 seconds after anomaly detection
- **Automatic Clip Generation**: Creates MP4 video files on HIGH/MEDIUM severity anomalies
- **Thumbnail Generation**: Auto-generates preview thumbnails (320x180) from middle frame
- **Structured Filenames**: `anomaly_{timestamp}_{severity}_{type}_{clip_id}.mp4`
- **New Module**: `anomaly_recorder.py` - Thread-safe recording handler
- **API Endpoints**: 
  - `/api/anomaly_clip/<clip_id>` - Download video clips
  - `/api/anomaly_thumbnail/<clip_id>` - Fetch thumbnails
- **Storage**: Clips saved to `anomaly_clips/` directory

#### Technical Details
- Circular frame buffer (150 frames @ 30fps = 5 seconds)
- Thread-safe recording with locks to prevent concurrent writes
- VideoWriter with mp4v codec
- 1280x720 resolution at 30 FPS
- Automatic thumbnail generation at 320x180

#### Files Changed
- `app/app_adaptive.py` - Integrated anomaly recorder
- `app/anomaly_recorder.py` - New recording module (added)
- `README.md` - Updated documentation

#### Verified Working
- ✅ Service running on montjac@10.79.85.35
- ✅ 6+ anomaly clips successfully captured and saved
- ✅ Thumbnails auto-generated
- ✅ Frame buffering operational
- ✅ API endpoints functional

---

## [v2.1.0] - Previous Release

### Bug Fixes
- Fixed camera variable scope issues
- Improved V4L2 timeout handling
- Enhanced error logging

