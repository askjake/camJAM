#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║       🧠 ADAPTIVE ML CAMERA MONITOR - INTELLIGENT LEARNING v2.2.1 🧠        ║
║                                                                              ║
║    NEW: Anomaly Video Capture + OPTIMIZED: Fast Startup (lazy-load YOLO)    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, Response, render_template_string, jsonify, request, send_file
import cv2
import threading
import time
import datetime
import os
import logging
import numpy as np
from collections import deque, Counter
import json
import pickle
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path

# Configuration
LEARNING_FRAMES_THRESHOLD = 1000
CONTINUOUS_LEARNING = True
ANOMALY_THRESHOLD = 0.35
CONFIDENCE_THRESHOLD = 0.80
SAVE_INTERVAL = 100

# Check GPU
CUDA_AVAILABLE = torch.cuda.is_available()
DEVICE = "cuda" if CUDA_AVAILABLE else "cpu"
GPU_NAME = torch.cuda.get_device_name(0) if CUDA_AVAILABLE else "CPU"
GPU_MEM = torch.cuda.get_device_properties(0).total_memory / 1e9 if CUDA_AVAILABLE else 0

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/camera-monitor-advanced/adaptive_ml.log")),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("adaptive-ml")

from anomaly_recorder import AnomalyRecorder
import uuid

app = Flask(__name__)

# Directories
BASE_DIR = Path.home() / "camera-monitor-advanced"
SNAP_DIR = BASE_DIR / "snapshots"
VIDEO_DIR = BASE_DIR / "recordings"
MODEL_DIR = BASE_DIR / "models"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
ANOMALY_CLIPS_DIR = BASE_DIR / "anomaly_clips"

for d in [SNAP_DIR, VIDEO_DIR, MODEL_DIR, KNOWLEDGE_DIR, ANOMALY_CLIPS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ==================== AUTOENCODER ====================
class ConvAutoencoder(nn.Module):
    def __init__(self):
        super(ConvAutoencoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(128, 64, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.ReLU(),
            nn.ConvTranspose2d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.ReLU(),
            nn.ConvTranspose2d(32, 3, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.Sigmoid(),
        )
    
    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


# ==================== KNOWLEDGE BASE ====================
class KnowledgeBase:
    def __init__(self):
        self.known_objects = Counter()
        self.known_object_locations = {}
        self.temporal_patterns = {}
        self.person_embeddings = []
        self.scene_histograms = deque(maxlen=1000)
        self.motion_patterns = deque(maxlen=1000)
        self.learning_start_time = time.time()
        self.total_frames_learned = 0
        self.confidence_score = 0.0
        
    def add_objects(self, objects, timestamp):
        hour = datetime.datetime.fromtimestamp(timestamp).hour
        if hour not in self.temporal_patterns:
            self.temporal_patterns[hour] = Counter()
        
        for obj in objects:
            label = obj['label']
            self.known_objects[label] += 1
            self.temporal_patterns[hour][label] += 1
            
            if label not in self.known_object_locations:
                self.known_object_locations[label] = []
            self.known_object_locations[label].append(obj['bbox'])
            
            if len(self.known_object_locations[label]) > 100:
                self.known_object_locations[label] = self.known_object_locations[label][-100:]
        
        self.total_frames_learned += 1
        self.update_confidence()
    
    def add_scene_histogram(self, hist):
        self.scene_histograms.append(hist)
    
    def add_motion_pattern(self, motion_score, timestamp):
        hour = datetime.datetime.fromtimestamp(timestamp).hour
        self.motion_patterns.append({
            'hour': hour,
            'score': motion_score,
            'timestamp': timestamp
        })
    
    def is_object_anomalous(self, obj, current_hour):
        label = obj['label']
        
        if label not in self.known_objects:
            return True, 0.8, f"Unknown object: {label}"
        
        if current_hour in self.temporal_patterns:
            hour_objects = self.temporal_patterns[current_hour]
            if label not in hour_objects:
                return True, 0.6, f"{label} unusual at this hour"
        
        if label in self.known_object_locations:
            bbox = obj['bbox']
            typical_locations = self.known_object_locations[label]
            
            min_dist = float('inf')
            for typical_bbox in typical_locations:
                dist = np.sqrt((bbox[0] - typical_bbox[0])**2 + (bbox[1] - typical_bbox[1])**2)
                min_dist = min(min_dist, dist)
            
            if min_dist > 200:
                return True, 0.5, f"{label} in unusual location"
        
        return False, 0.0, ""
    
    def update_confidence(self):
        if self.total_frames_learned < LEARNING_FRAMES_THRESHOLD:
            self.confidence_score = self.total_frames_learned / LEARNING_FRAMES_THRESHOLD
        else:
            self.confidence_score = min(1.0, 0.8 + (self.total_frames_learned / (LEARNING_FRAMES_THRESHOLD * 5)) * 0.2)
    
    def save(self, filepath):
        data = {
            'known_objects': dict(self.known_objects),
            'known_object_locations': self.known_object_locations,
            'temporal_patterns': {k: dict(v) for k, v in self.temporal_patterns.items()},
            'scene_histograms': list(self.scene_histograms),
            'motion_patterns': list(self.motion_patterns),
            'learning_start_time': self.learning_start_time,
            'total_frames_learned': self.total_frames_learned,
            'confidence_score': self.confidence_score,
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        log.info(f"💾 Knowledge saved: {filepath}")
    
    def load(self, filepath):
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            self.known_objects = Counter(data['known_objects'])
            self.known_object_locations = data['known_object_locations']
            self.temporal_patterns = {k: Counter(v) for k, v in data['temporal_patterns'].items()}
            self.scene_histograms = deque(data['scene_histograms'], maxlen=1000)
            self.motion_patterns = deque(data['motion_patterns'], maxlen=1000)
            self.learning_start_time = data['learning_start_time']
            self.total_frames_learned = data['total_frames_learned']
            self.confidence_score = data['confidence_score']
            log.info(f"📂 Knowledge loaded: {filepath} ({self.total_frames_learned} frames)")
            return True
        except Exception as e:
            log.error(f"Failed to load knowledge: {e}")
            return False
    
    def get_stats(self):
        return {
            'total_objects_seen': sum(self.known_objects.values()),
            'unique_object_types': len(self.known_objects),
            'most_common_objects': self.known_objects.most_common(5),
            'hours_learned': list(self.temporal_patterns.keys()),
            'total_frames': self.total_frames_learned,
            'confidence': self.confidence_score,
            'learning_duration': time.time() - self.learning_start_time
        }


# ==================== GLOBAL STATE ====================
camera = None  # Initialize here at module level
camera_lock = threading.Lock()
latest_frame = None
frame_count = 0
start_time = time.time()

prev_gray = None
motion_regions = []
MOTION_THRESHOLD = 25
MOTION_MIN_AREA = 500

brightness_history = deque(maxlen=500)
motion_score_history = deque(maxlen=500)
fps_history = deque(maxlen=100)
reconstruction_error_history = deque(maxlen=500)

detected_objects = []
detected_faces = []

autoencoder = ConvAutoencoder().to(DEVICE)
optimizer = optim.Adam(autoencoder.parameters(), lr=0.001)
criterion = nn.MSELoss()
knowledge_base = KnowledgeBase()

learning_mode = "INITIAL"
anomaly_alerts = deque(maxlen=100)
last_save_frame = 0

# Lazy-load YOLO to avoid startup hang
yolo_model = None
yolo_loading = False
yolo_loaded = False

def load_yolo_async():
    """Load YOLO model in background thread to speed up startup"""
    global yolo_model, yolo_loading, yolo_loaded
    if yolo_loaded or yolo_loading:
        return
    
    yolo_loading = True
    try:
        from ultralytics import YOLO
        log.info(f"🔥 Loading YOLO on {DEVICE} (background)...")
        yolo_model = YOLO('yolov8n.pt')
        if CUDA_AVAILABLE:
            yolo_model.to(DEVICE)
        yolo_loaded = True
        log.info("✅ YOLO loaded successfully")
    except Exception as e:
        log.warning(f"⚠️  YOLO unavailable: {e}")
    finally:
        yolo_loading = False

# Start YOLO loading in background thread (non-blocking)
log.info("⚡ Starting YOLO load in background...")
threading.Thread(target=load_yolo_async, daemon=True).start()

# Face detection
face_cascade = None
try:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    log.info("✅ Face detection loaded")
except Exception as e:
    log.warning(f"⚠️  Face detection unavailable: {e}")

# Load existing knowledge
knowledge_file = KNOWLEDGE_DIR / "knowledge_base.pkl"
if knowledge_base.load(knowledge_file):
    if knowledge_base.confidence_score >= CONFIDENCE_THRESHOLD:
        learning_mode = "TRAINED"
        log.info(f"📚 Loaded trained knowledge (confidence: {knowledge_base.confidence_score:.1%})")
    else:
        learning_mode = "INITIAL"
        log.info(f"📚 Resuming initial learning (confidence: {knowledge_base.confidence_score:.1%})")

# Load autoencoder
model_file = MODEL_DIR / "autoencoder.pth"
if model_file.exists():
    try:
        autoencoder.load_state_dict(torch.load(model_file, map_location=DEVICE))
        log.info(f"🧠 Loaded autoencoder model")
    except Exception as e:
        log.warning(f"⚠️  Could not load autoencoder: {e}")


# ==================== CAMERA FUNCTIONS ====================
def get_camera():
    """BUGFIX: Properly handle camera variable scope"""
    global camera
    
    for attempt in range(3):
        # Check if camera exists and is opened
        if camera is not None:
            if camera.isOpened():
                return camera
            else:
                # Camera exists but not opened, release it
                try:
                    camera.release()
                except:
                    pass
                camera = None
        
        log.info(f"🎥 Opening camera (attempt {attempt+1})...")
        
        # Try to open camera with timeout handling
        try:
            camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
            
            # Set properties
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            camera.set(cv2.CAP_PROP_FPS, 30)
            camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer to avoid timeouts
            
            time.sleep(1)
            
            if camera.isOpened():
                # Test read a frame
                ret, test_frame = camera.read()
                if ret and test_frame is not None:
                    log.info(f"✅ Camera opened: {test_frame.shape[1]}x{test_frame.shape[0]}")
                    return camera
                else:
                    log.warning(f"⚠️  Camera opened but frame read failed")
                    camera.release()
                    camera = None
        except Exception as e:
            log.error(f"❌ Camera open error: {e}")
            if camera is not None:
                try:
                    camera.release()
                except:
                    pass
                camera = None
        
        time.sleep(2)
    
    log.error("❌ Failed to open camera after 3 attempts")
    return None


def detect_motion_advanced(frame):
    global prev_gray, motion_regions
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    
    if prev_gray is None:
        prev_gray = gray
        return [], 0.0
    
    delta = cv2.absdiff(prev_gray, gray)
    thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=3)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    regions = []
    total_motion = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MOTION_MIN_AREA:
            continue
        total_motion += area
        (x, y, w, h) = cv2.boundingRect(contour)
        regions.append((x, y, w, h))
    
    motion_score = min(total_motion / (frame.shape[0] * frame.shape[1]), 1.0)
    motion_score_history.append({'t': time.time(), 'v': motion_score})
    
    prev_gray = gray
    motion_regions = regions
    return regions, motion_score


def detect_objects_yolo(frame):
    global detected_objects
    if yolo_model is None:
        return []
    
    try:
        results = yolo_model(frame, verbose=False, device=DEVICE)
        objects = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                label = yolo_model.names[class_id]
                
                if confidence > 0.5:
                    objects.append({
                        'label': label,
                        'confidence': confidence,
                        'bbox': (int(x1), int(y1), int(x2-x1), int(y2-y1)),
                        'class_id': class_id
                    })
        
        detected_objects = objects
        return objects
    except Exception as e:
        log.error(f"YOLO error: {e}")
        return []


def detect_faces(frame):
    global detected_faces
    if face_cascade is None:
        return []
    
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        face_list = [{'bbox': (int(x), int(y), int(w), int(h))} for (x, y, w, h) in faces]
        detected_faces = face_list
        return face_list
    except Exception as e:
        log.error(f"Face detection error: {e}")
        return []


def train_autoencoder(frame):
    global optimizer, criterion
    
    frame_resized = cv2.resize(frame, (128, 128))
    frame_tensor = torch.from_numpy(frame_resized).permute(2, 0, 1).float() / 255.0
    frame_tensor = frame_tensor.unsqueeze(0).to(DEVICE)
    
    autoencoder.train()
    optimizer.zero_grad()
    output = autoencoder(frame_tensor)
    loss = criterion(output, frame_tensor)
    loss.backward()
    optimizer.step()
    
    return loss.item()


def detect_anomaly_autoencoder(frame):
    autoencoder.eval()
    
    frame_resized = cv2.resize(frame, (128, 128))
    frame_tensor = torch.from_numpy(frame_resized).permute(2, 0, 1).float() / 255.0
    frame_tensor = frame_tensor.unsqueeze(0).to(DEVICE)
    
    with torch.no_grad():
        output = autoencoder(frame_tensor)
        loss = criterion(output, frame_tensor)
        reconstruction_error = loss.item()
    
    reconstruction_error_history.append({'t': time.time(), 'v': reconstruction_error})
    
    is_anomalous = reconstruction_error > ANOMALY_THRESHOLD
    
    return is_anomalous, reconstruction_error


def analyze_scene(frame, objects, motion_score):
    global learning_mode, last_save_frame
    
    timestamp = time.time()
    current_hour = datetime.datetime.now().hour
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
    hist = hist / (hist.sum() + 1e-6)
    
    brightness = np.mean(gray)
    brightness_history.append({'t': timestamp, 'v': brightness})
    
    knowledge_base.add_scene_histogram(hist)
    knowledge_base.add_motion_pattern(motion_score, timestamp)
    knowledge_base.add_objects(objects, timestamp)
    
    anomalies = []
    
    if learning_mode == "INITIAL" and knowledge_base.confidence_score >= CONFIDENCE_THRESHOLD:
        learning_mode = "TRAINED"
        log.info(f"✅ Initial learning complete! Confidence: {knowledge_base.confidence_score:.1%}")
    
    if learning_mode == "TRAINED" or learning_mode == "CONTINUOUS":
        is_scene_anomalous, recon_error = detect_anomaly_autoencoder(frame)
        if is_scene_anomalous:
            anomalies.append({
                'type': 'scene',
                'severity': 'HIGH' if recon_error > ANOMALY_THRESHOLD * 1.5 else 'MEDIUM',
                'score': recon_error,
                'message': f"Unusual scene pattern (error: {recon_error:.3f})"
            })
        
        for obj in objects:
            is_anom, anom_score, reason = knowledge_base.is_object_anomalous(obj, current_hour)
            if is_anom:
                anomalies.append({
                    'type': 'object',
                    'severity': 'HIGH' if anom_score > 0.7 else 'MEDIUM' if anom_score > 0.4 else 'LOW',
                    'score': anom_score,
                    'message': reason,
                    'object': obj['label']
                })
        
        if len(motion_score_history) > 50:
            recent_motion = [m['v'] for m in list(motion_score_history)[-50:]]
            avg_motion = np.mean(recent_motion)
            if motion_score > avg_motion * 2.5:
                anomalies.append({
                    'type': 'motion',
                    'severity': 'MEDIUM',
                    'score': motion_score,
                    'message': f"Unusual motion intensity ({motion_score:.2f} vs avg {avg_motion:.2f})"
                })
    
    if learning_mode == "TRAINED" and CONTINUOUS_LEARNING:
        learning_mode = "CONTINUOUS"
    
    if learning_mode == "CONTINUOUS" and frame_count % 10 == 0:
        train_autoencoder(frame)
    
    if learning_mode == "INITIAL" and frame_count % 2 == 0:
        train_autoencoder(frame)
    
    if anomalies:
        for anom in anomalies:
            anomaly_alerts.append({
                'timestamp': datetime.datetime.now().isoformat(),
                'type': anom['type'],
                'severity': anom['severity'],
                'score': anom['score'],
                'message': anom['message'],
                'confidence': knowledge_base.confidence_score
            })
            log.warning(f"⚠️  ANOMALY [{anom['severity']}]: {anom['message']}")
    
    if frame_count - last_save_frame >= SAVE_INTERVAL:
        save_knowledge()
        last_save_frame = frame_count
    
    return anomalies


def save_knowledge():
    try:
        knowledge_base.save(KNOWLEDGE_DIR / "knowledge_base.pkl")
        torch.save(autoencoder.state_dict(), MODEL_DIR / "autoencoder.pth")
        log.info("💾 Knowledge and model saved")
    except Exception as e:
        log.error(f"Save error: {e}")


def annotate_frame(frame, anomalies):
    output = frame.copy()
    h, w = output.shape[:2]
    
    for (x, y, w, h) in motion_regions:
        cv2.rectangle(output, (x, y), (x+w, y+h), (0, 0, 255), 2)
    
    for obj in detected_objects:
        x, y, w, h = obj['bbox']
        is_anomalous = any(a['type'] == 'object' and a.get('object') == obj['label'] for a in anomalies)
        color = (0, 255, 255) if is_anomalous else (0, 255, 0)
        cv2.rectangle(output, (x, y), (x+w, y+h), color, 2)
        label = f"{obj['label']} {obj['confidence']:.0%}"
        if is_anomalous:
            label += " ⚠"
        cv2.putText(output, label, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    for face in detected_faces:
        x, y, w, h = face['bbox']
        cv2.rectangle(output, (x, y), (x+w, y+h), (255, 255, 0), 2)
    
    if anomalies:
        max_severity = max((a['severity'] for a in anomalies), key=lambda s: {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}[s])
        border_color = (0, 255, 255) if max_severity == 'LOW' else (0, 165, 255) if max_severity == 'MEDIUM' else (0, 0, 255)
        cv2.rectangle(output, (5, 5), (w-5, h-5), border_color, 4)
        cv2.putText(output, f"⚠️ ANOMALY DETECTED", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, border_color, 2)
    
    mode_color = (255, 0, 255) if learning_mode == "INITIAL" else (0, 255, 0) if learning_mode == "TRAINED" else (0, 255, 255)
    stats = [
        f"Mode: {learning_mode}",
        f"Confidence: {knowledge_base.confidence_score:.0%}",
        f"Frames: {knowledge_base.total_frames_learned}/{LEARNING_FRAMES_THRESHOLD}",
        f"Objects: {len(detected_objects)} | Faces: {len(detected_faces)}",
        f"FPS: {get_current_fps():.1f}",
    ]
    
    y_pos = h - 120
    for stat in stats:
        cv2.putText(output, stat, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, mode_color, 1)
        y_pos += 20
    
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(output, ts, (10, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    return output


def get_current_fps():
    if len(fps_history) < 2:
        return 0.0
    recent = list(fps_history)[-20:]
    time_diffs = [recent[i]['t'] - recent[i-1]['t'] for i in range(1, len(recent))]
    if time_diffs:
        return 1.0 / (sum(time_diffs) / len(time_diffs))
    return 0.0


# ==================== CAPTURE LOOP ====================
# Initialize anomaly recorder
anomaly_recorder = AnomalyRecorder(ANOMALY_CLIPS_DIR, fps=30)

def capture_loop():
    global latest_frame, frame_count, camera
    
    log.info("🎬 Capture loop started with adaptive learning")
    detect_counter = 0
    consecutive_failures = 0
    
    while True:
        try:
            with camera_lock:
                cam = get_camera()
            
            if cam is None:
                consecutive_failures += 1
                if consecutive_failures > 10:
                    log.error("❌ Too many camera failures, waiting longer...")
                    time.sleep(10)
                    consecutive_failures = 0
                else:
                    time.sleep(2)
                continue
            
            ret, frame = cam.read()
            if not ret or frame is None:
                log.warning("⚠️  Frame read failed")
                consecutive_failures += 1
                with camera_lock:
                    if camera is not None:
                        try:
                            camera.release()
                        except:
                            pass
                        camera = None
                time.sleep(1)
                continue
            
            # Reset failure counter on success
            consecutive_failures = 0
            
            fps_history.append({'t': time.time()})
            
            regions, motion_score = detect_motion_advanced(frame)
            
            if detect_counter % 5 == 0:
                if yolo_model:
                    detect_objects_yolo(frame)
                if face_cascade:
                    detect_faces(frame)
            
            detect_counter += 1
            
            anomalies = analyze_scene(frame, detected_objects, motion_score)
            

            annotated = annotate_frame(frame, anomalies)
            
            # Anomaly recording logic
            anomaly_recorder.add_frame(annotated)
            
            if anomalies and not anomaly_recorder.is_recording:
                clip_id = anomaly_recorder.start_recording(anomalies[0])
                if clip_id:
                    anomalies[0]["clip_id"] = clip_id
            
            if anomaly_recorder.is_recording:
                anomaly_recorder.record_frame(annotated)

            
            latest_frame = annotated.copy()
            frame_count += 1
            
            time.sleep(0.01)
            
        except Exception as e:
            log.error(f"❌ Capture error: {e}")
            # Ensure camera is properly cleaned up
            with camera_lock:
                if camera is not None:
                    try:
                        camera.release()
                    except:
                        pass
                    camera = None
            time.sleep(1)


# Start capture thread
threading.Thread(target=capture_loop, daemon=True).start()


def generate_frames():
    while True:
        if latest_frame is not None:
            _, buf = cv2.imencode(".jpg", latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        time.sleep(0.033)


# ==================== HTML (Same as before, truncated for brevity) ====================
HTML_TEMPLATE = """<!DOCTYPE html><html><head><title>Adaptive ML Camera</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0a0a1a;color:#e0e0e0;font-family:'Segoe UI',sans-serif;padding:20px}h1{color:#0ff;text-align:center;margin-bottom:20px}.grid{display:grid;grid-template-columns:1fr 400px;gap:20px}@media(max-width:1200px){.grid{grid-template-columns:1fr}}img{width:100%;border-radius:8px;border:2px solid #0ff}.card{background:#12122a;border:1px solid #ffffff15;border-radius:10px;margin-bottom:15px;overflow:hidden}.card-header{padding:12px 15px;border-bottom:1px solid #ffffff15;background:rgba(0,255,255,0.05)}.card-header h3{margin:0;color:#0ff;font-size:1.1em}.card-body{padding:15px}.stat{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #ffffff08}.stat-val{color:#0ff;font-weight:600}.badge{padding:5px 12px;border-radius:15px;font-size:0.85em;font-weight:bold;margin:5px}.learning{background:#ff02;color:#ff0;border:1px solid #ff0;animation:pulse 1s infinite}.trained{background:#0f02;color:#0f0;border:1px solid #0f0}.continuous{background:#0ff2;color:#0ff;border:1px solid #0ff}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}.anomaly-list{max-height:300px;overflow-y:auto;font-size:0.85em}.anomaly-item{padding:8px;margin:4px 0;background:#1a1a2a;border-radius:4px}.severity-HIGH{border-left:3px solid #f00}.severity-MEDIUM{border-left:3px solid #fa0}.severity-LOW{border-left:3px solid #ff0}.btn{display:inline-block;padding:10px 20px;background:#0ff2;color:#0ff;border:1px solid #0ff;border-radius:8px;cursor:pointer;text-decoration:none;margin:5px;transition:0.3s}.btn:hover{background:#0ff4;transform:translateY(-2px)}.chart{height:120px;margin-top:10px}</style></head><body><h1>🧠 Adaptive ML Camera Monitor</h1><div style="text-align:center;margin-bottom:20px"><span class="badge" id="modeBadge">LEARNING</span></div><div class="grid"><div><div class="card"><div class="card-body"><img src="/video_feed" alt="Live Feed"></div></div><div class="card"><div class="card-header"><h3>📊 Learning Progress</h3></div><div class="card-body"><div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;margin-bottom:5px"><span>Frames Learned</span><span id="learnFrames" style="color:#0ff">0/1000</span></div><div style="height:8px;background:#1a1a2a;border-radius:4px;overflow:hidden"><div id="learnBar" style="height:100%;background:linear-gradient(90deg,#0ff,#0f0);width:0%;transition:0.5s"></div></div></div><div class="stat"><span>Confidence</span><span class="stat-val" id="confidence">0%</span></div><div class="stat"><span>Known Objects</span><span class="stat-val" id="knownObjs">0</span></div><div class="stat"><span>Object Types</span><span class="stat-val" id="objTypes">0</span></div></div></div><div class="card"><div class="card-header"><h3>📈 Analytics</h3></div><div class="card-body"><div style="margin-bottom:15px"><div style="font-size:0.9em;margin-bottom:5px;color:#888">Reconstruction Error</div><div class="chart"><canvas id="reconChart"></canvas></div></div><div><div style="font-size:0.9em;margin-bottom:5px;color:#888">Motion Score</div><div class="chart"><canvas id="motionChart"></canvas></div></div></div></div></div><div><div class="card"><div class="card-header"><h3>⚡ Status</h3></div><div class="card-body"><div class="stat"><span>Mode</span><span class="stat-val" id="mode">--</span></div><div class="stat"><span>FPS</span><span class="stat-val" id="fps">--</span></div><div class="stat"><span>Objects</span><span class="stat-val" id="objCount">--</span></div><div class="stat"><span>Faces</span><span class="stat-val" id="faceCount">--</span></div></div></div><div class="card"><div class="card-header"><h3>📸 Controls</h3></div><div class="card-body" style="text-align:center"><button class="btn" onclick="takeSnapshot()">📸 Snapshot</button><button class="btn" onclick="saveKnowledge()">💾 Save Knowledge</button><button class="btn" onclick="resetLearning()">🔄 Reset Learning</button></div></div><div class="card"><div class="card-header"><h3>⚠️ Anomaly Alerts</h3></div><div class="card-body"><div class="anomaly-list" id="anomalyList">No anomalies detected</div></div></div><div class="card"><div class="card-header"><h3>📹 Anomaly Clips</h3></div><div class="card-body"><div id="clipsList" style="max-height:400px;overflow-y:auto"><div style="color:#888;padding:10px;text-align:center">Loading clips...</div></div></div></div></div></div><div id="videoModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.95);z-index:9999;padding:20px"><div style="max-width:1200px;margin:auto;position:relative"><button onclick="closeVideo()" style="position:absolute;top:10px;right:10px;background:#f00;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-size:18px;z-index:10000">✕ Close</button><div style="background:#000;border-radius:10px;overflow:hidden;margin-top:50px"><video id="videoPlayer" controls autoplay style="width:100%;max-height:80vh"><source id="videoSource" src="" type="video/mp4">Your browser does not support video playback.</video></div><div style="color:#fff;margin-top:15px;text-align:center"><h2 id="videoTitle" style="color:#0ff">Anomaly Clip</h2><p id="videoInfo" style="color:#888"></p></div></div></div><style>.clip-item{background:#1a1a2a;border-radius:8px;padding:10px;margin-bottom:10px;cursor:pointer;transition:0.3s;border:2px solid transparent;display:flex;gap:10px;align-items:center}.clip-item:hover{border-color:#0ff;background:#252540;transform:translateX(5px)}.clip-thumbnail{width:120px;height:68px;object-fit:cover;border-radius:4px;border:1px solid #0ff4}.clip-info{flex:1}.clip-time{color:#0ff;font-size:0.9em;font-weight:bold}.clip-severity{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75em;margin-right:5px}.severity-tag-HIGH{background:#f004;color:#f00;border:1px solid #f00}.severity-tag-MEDIUM{background:#fa04;color:#fa0;border:1px solid #fa0}.severity-tag-LOW{background:#ff04;color:#ff0;border:1px solid #ff0}.clip-type{color:#888;font-size:0.85em}.no-clips{color:#888;text-align:center;padding:20px;font-style:italic}</style><script>function loadClips(){fetch('/api/anomaly_clips').then(r=>r.json()).then(clips=>{let el=document.getElementById('clipsList');if(clips.length===0){el.innerHTML='<div class="no-clips">No clips recorded yet</div>'}else{el.innerHTML=clips.map(clip=>`<div class="clip-item" onclick="playClip('${clip.clip_id}','${clip.timestamp}','${clip.severity}','${clip.type}')"><img src="/api/anomaly_thumbnail/${clip.clip_id}" class="clip-thumbnail" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22120%22 height=%2268%22><rect fill=%22%23333%22 width=%22120%22 height=%2268%22/><text x=%2250%%22 y=%2250%%22 text-anchor=%22middle%22 fill=%22%23666%22>No Thumb</text></svg>'"><div class="clip-info"><div class="clip-time">${formatTimestamp(clip.timestamp)}</div><div><span class="clip-severity severity-tag-${clip.severity}">${clip.severity}</span><span class="clip-type">${clip.type.toUpperCase()}</span></div><div style="font-size:0.75em;color:#666;margin-top:3px">${clip.size}</div></div></div>`).join('')}}).catch(err=>{document.getElementById('clipsList').innerHTML='<div class="no-clips">Error loading clips</div>'})}function formatTimestamp(ts){let d=new Date(ts);return d.toLocaleTimeString()+' - '+d.toLocaleDateString()}function playClip(clipId,timestamp,severity,type){document.getElementById('videoSource').src='/api/anomaly_clip/'+clipId;document.getElementById('videoPlayer').load();document.getElementById('videoTitle').textContent=`${type.toUpperCase()} Anomaly - ${severity}`;document.getElementById('videoInfo').textContent=`Captured: ${formatTimestamp(timestamp)} | Clip ID: ${clipId}`;document.getElementById('videoModal').style.display='block'}function closeVideo(){document.getElementById('videoModal').style.display='none';document.getElementById('videoPlayer').pause()}loadClips();setInterval(loadClips,30000);document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeVideo()}})</div></div><script>let reconChart,motionChart;function initCharts(){reconChart=new Chart(document.getElementById('reconChart').getContext('2d'),{type:'line',data:{labels:[],datasets:[{label:'Error',data:[],borderColor:'#f00',backgroundColor:'rgba(255,0,0,0.1)',tension:0.4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,grid:{color:'#ffffff10'}},x:{display:false}}}});motionChart=new Chart(document.getElementById('motionChart').getContext('2d'),{type:'line',data:{labels:[],datasets:[{label:'Motion',data:[],borderColor:'#0ff',backgroundColor:'rgba(0,255,255,0.1)',tension:0.4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:1,grid:{color:'#ffffff10'}},x:{display:false}}}})}function updateCharts(recon,motion){if(recon.length>0){reconChart.data.labels=recon.map((_,i)=>i);reconChart.data.datasets[0].data=recon.map(d=>d.v);reconChart.update('none')}if(motion.length>0){motionChart.data.labels=motion.map((_,i)=>i);motionChart.data.datasets[0].data=motion.map(d=>d.v);motionChart.update('none')}}function takeSnapshot(){window.open('/snapshot','_blank')}function saveKnowledge(){fetch('/api/save_knowledge',{method:'POST'}).then(r=>r.json()).then(d=>alert(d.message))}function resetLearning(){if(confirm('Reset all learning? This will start from scratch.')){fetch('/api/reset_learning',{method:'POST'}).then(r=>r.json()).then(d=>alert(d.message))}}function poll(){fetch('/api/status').then(r=>r.json()).then(d=>{document.getElementById('mode').textContent=d.mode;document.getElementById('fps').textContent=d.fps.toFixed(1);document.getElementById('objCount').textContent=d.objects;document.getElementById('faceCount').textContent=d.faces;document.getElementById('confidence').textContent=Math.round(d.confidence*100)+'%';document.getElementById('learnFrames').textContent=d.frames_learned+'/'+d.learning_threshold;document.getElementById('knownObjs').textContent=d.known_objects;document.getElementById('objTypes').textContent=d.unique_types;let pct=Math.min(d.frames_learned/d.learning_threshold*100,100);document.getElementById('learnBar').style.width=pct+'%';let badge=document.getElementById('modeBadge');if(d.mode==='INITIAL'){badge.textContent='🔄 LEARNING';badge.className='badge learning'}else if(d.mode==='TRAINED'){badge.textContent='✅ TRAINED';badge.className='badge trained'}else{badge.textContent='🔁 CONTINUOUS LEARNING';badge.className='badge continuous'}});fetch('/api/anomalies').then(r=>r.json()).then(d=>{let el=document.getElementById('anomalyList');if(d.length===0){el.innerHTML='<div style="color:#888;padding:10px;text-align:center">No anomalies</div>'}else{el.innerHTML=d.slice(-20).reverse().map(a=>'<div class="anomaly-item severity-'+a.severity+'"><div style="font-size:0.75em;color:#888">'+a.timestamp.split('T')[1].split('.')[0]+'</div><div><strong>['+a.type.toUpperCase()+']</strong> '+a.message+'</div><div style="font-size:0.75em;color:#888">Confidence: '+Math.round(a.confidence*100)+'%</div></div>').join('')}});fetch('/api/history').then(r=>r.json()).then(d=>updateCharts(d.reconstruction_error,d.motion))}initCharts();setInterval(poll,2000);poll();</script></body></html>"""


# ==================== FLASK ROUTES ====================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/snapshot")
def snapshot():
    if latest_frame is not None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SNAP_DIR / f"snap_{ts}.jpg"
        cv2.imwrite(str(path), latest_frame)
        _, buf = cv2.imencode(".jpg", latest_frame)
        log.info(f"📸 Snapshot: {path}")
        return Response(buf.tobytes(), mimetype="image/jpeg")
    return "No frame", 503

@app.route("/api/status")
def api_status():
    stats = knowledge_base.get_stats()
    return jsonify({
        "mode": learning_mode,
        "confidence": knowledge_base.confidence_score,
        "fps": get_current_fps(),
        "objects": len(detected_objects),
        "faces": len(detected_faces),
        "frames_learned": knowledge_base.total_frames_learned,
        "learning_threshold": LEARNING_FRAMES_THRESHOLD,
        "known_objects": stats['total_objects_seen'],
        "unique_types": stats['unique_object_types'],
        "most_common": stats['most_common_objects']
    })

@app.route("/api/anomalies")
def api_anomalies():
    return jsonify(list(anomaly_alerts))

@app.route("/api/history")
def api_history():
    return jsonify({
        "reconstruction_error": list(reconstruction_error_history)[-100:],
        "motion": list(motion_score_history)[-100:]
    })

@app.route("/api/save_knowledge", methods=["POST"])
def api_save_knowledge():
    save_knowledge()
    return jsonify({"status": "ok", "message": "Knowledge saved successfully"})

@app.route("/api/reset_learning", methods=["POST"])
def api_reset_learning():
    global learning_mode, anomaly_alerts
    
    knowledge_base.__init__()
    autoencoder.__init__()
    autoencoder.to(DEVICE)
    anomaly_alerts.clear()
    learning_mode = "INITIAL"
    
    log.warning("🔄 Learning reset - starting fresh")
    return jsonify({"status": "ok", "message": "Learning reset. Starting fresh."})

@app.route("/api/health")
def health():
    global camera
    cam_ok = camera is not None and camera.isOpened() if camera else False
    return jsonify({
        "status": "healthy" if cam_ok else "degraded",
        "camera": cam_ok,
        "gpu": CUDA_AVAILABLE,
        "mode": learning_mode,
        "confidence": knowledge_base.confidence_score
    }), 200 if cam_ok else 503




@app.route("/api/anomaly_clip/<clip_id>")
def get_anomaly_clip(clip_id):
    clip_path = anomaly_recorder.get_clip_path(clip_id)
    if clip_path and clip_path.exists():
        return send_file(clip_path, mimetype="video/mp4")
    return "Clip not found", 404

@app.route("/api/anomaly_thumbnail/<clip_id>")
def get_anomaly_thumbnail(clip_id):
    thumb_path = anomaly_recorder.get_thumbnail_path(clip_id)
    if thumb_path and thumb_path.exists():
        return send_file(thumb_path, mimetype="image/jpeg")
    return "Thumbnail not found", 404

@app.route("/api/anomaly_clips")
def list_anomaly_clips():
    """List all anomaly clips with metadata"""
    try:
        clips = []
        clips_dir = ANOMALY_CLIPS_DIR
        
        for clip_file in sorted(clips_dir.glob("*.mp4"), reverse=True):
            # Parse filename: anomaly_YYYYMMDD_HHMMSS_SEVERITY_TYPE_CLIPID.mp4
            parts = clip_file.stem.split('_')
            if len(parts) >= 6:
                date_str = parts[1]  # YYYYMMDD
                time_str = parts[2]  # HHMMSS
                severity = parts[3]  # MEDIUM/HIGH/LOW
                atype = parts[4]     # motion/person/etc
                clip_id = parts[5]   # 8-char hex
                
                # Format timestamp
                timestamp = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                
                # Get file size
                size_bytes = clip_file.stat().st_size
                if size_bytes < 1024*1024:
                    size = f"{size_bytes/1024:.1f} KB"
                else:
                    size = f"{size_bytes/(1024*1024):.1f} MB"
                
                clips.append({
                    "clip_id": clip_id,
                    "timestamp": timestamp,
                    "severity": severity,
                    "type": atype,
                    "filename": clip_file.name,
                    "size": size,
                    "size_bytes": size_bytes
                })
        
        return jsonify(clips)
    except Exception as e:
        log.error(f"Error listing clips: {e}")
        return jsonify([])



if __name__ == "__main__":
    log.info("="*80)
    log.info("🧠 ADAPTIVE ML CAMERA MONITOR v2.2.1 (PERFORMANCE)")
    log.info("="*80)
    log.info(f"Device: {DEVICE} ({GPU_NAME})")
    log.info(f"Learning Threshold: {LEARNING_FRAMES_THRESHOLD} frames")
    log.info(f"YOLO: {'✅' if yolo_model else '❌'}")
    log.info(f"Initial Mode: {learning_mode}")
    log.info(f"Confidence: {knowledge_base.confidence_score:.1%}")
    log.info("="*80)
    log.info("Starting on port 5000...")
    log.info("="*80)
    
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
