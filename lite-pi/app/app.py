from flask import Flask, Response, render_template_string, jsonify
import cv2, threading, time, datetime, os, logging, numpy as np
from collections import deque

# TFLite for object detection
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
except:
    TFLITE_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cam-enhanced")

app = Flask(__name__)

# --- Config ---
SNAP_DIR = os.path.expanduser("~/camera-monitor/snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)
MODEL_PATH = os.path.expanduser("~/camera-monitor/detect.tflite")
LABELS_PATH = os.path.expanduser("~/camera-monitor/labelmap.txt")

# --- Shared State ---
camera = None
lock = threading.Lock()
latest_frame = None
motion_regions = []
detected_objects = []
frame_count = 0
start_time = time.time()
prev_gray = None
MOTION_THRESHOLD = 25
MOTION_MIN_AREA = 500

# Adaptive learning state
scene_baseline = None
scene_history = deque(maxlen=100)
brightness_history = deque(maxlen=100)
motion_score_history = deque(maxlen=100)
anomaly_alerts = deque(maxlen=50)
learning_samples = 0
LEARNING_THRESHOLD = 300
anomaly_score = 0.0
learning_confidence = 0.0

# Adaptive re-learning
consecutive_high_anomalies = 0
RELEARN_TRIGGER = 10
is_relearning = False
relearn_reason = ""
total_relearns = 0
last_relearn_time = None

# Scene change detection
scene_change_history = deque(maxlen=50)
SCENE_CHANGE_THRESHOLD = 0.4

# TFLite setup
interpreter = None
labels = []

if TFLITE_AVAILABLE and os.path.exists(MODEL_PATH):
    try:
        interpreter = tflite.Interpreter(model_path=MODEL_PATH)
        interpreter.allocate_tensors()
        with open(LABELS_PATH, 'r') as f:
            labels = [line.strip() for line in f.readlines()]
        log.info("TFLite model loaded successfully")
    except Exception as e:
        log.error(f"Failed to load TFLite model: {e}")
        interpreter = None

def get_camera():
    global camera
    for attempt in range(3):
        if camera is not None and camera.isOpened():
            return camera
        log.info(f"Opening camera (attempt {attempt+1})...")
        camera = cv2.VideoCapture(0)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 30)
        time.sleep(1)
        if camera.isOpened():
            log.info("Camera opened successfully")
            return camera
        time.sleep(2)
    log.error("Could not open camera after 3 attempts")
    return None

def reset_learning(reason="Manual reset"):
    global scene_baseline, scene_history, learning_samples, learning_confidence
    global consecutive_high_anomalies, is_relearning, relearn_reason, total_relearns, last_relearn_time
    
    scene_baseline = None
    scene_history.clear()
    learning_samples = 0
    learning_confidence = 0.0
    consecutive_high_anomalies = 0
    is_relearning = True
    relearn_reason = reason
    total_relearns += 1
    last_relearn_time = datetime.datetime.now().isoformat()
    
    log.warning(f"🔄 LEARNING RESET: {reason} (Total resets: {total_relearns})")

def detect_motion_regions(frame):
    global prev_gray, motion_regions
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    
    if prev_gray is None:
        prev_gray = gray
        return [], 0
    
    delta = cv2.absdiff(prev_gray, gray)
    thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    
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
    
    motion_score = min(total_motion / (640 * 480), 1.0)
    motion_score_history.append({'t': time.time(), 'v': motion_score})
    
    prev_gray = gray
    motion_regions = regions
    return regions, motion_score

def detect_scene_change(hist):
    if scene_baseline is None or learning_samples < LEARNING_THRESHOLD:
        return False, 1.0
    
    correlation = np.corrcoef(scene_baseline, hist)[0, 1]
    scene_change_history.append({'t': time.time(), 'v': correlation})
    
    if correlation < SCENE_CHANGE_THRESHOLD:
        return True, correlation
    
    if len(scene_change_history) >= 10:
        recent_correlations = [s['v'] for s in list(scene_change_history)[-10:]]
        avg_correlation = np.mean(recent_correlations)
        if avg_correlation < SCENE_CHANGE_THRESHOLD:
            return True, avg_correlation
    
    return False, correlation

def detect_anomaly(frame, motion_score):
    global scene_baseline, learning_samples, anomaly_score, learning_confidence
    global consecutive_high_anomalies, is_relearning
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    brightness_history.append({'t': time.time(), 'v': brightness})
    
    hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
    hist = hist / (hist.sum() + 1e-6)
    scene_history.append(hist)
    
    learning_samples += 1
    
    if learning_samples >= LEARNING_THRESHOLD:
        learning_confidence = min(100.0, (learning_samples / (LEARNING_THRESHOLD * 3)) * 100)
    else:
        learning_confidence = (learning_samples / LEARNING_THRESHOLD) * 100
    
    if learning_samples <= LEARNING_THRESHOLD:
        if learning_samples == LEARNING_THRESHOLD:
            scene_baseline = np.mean(list(scene_history), axis=0)
            is_relearning = False
            log.info(f"✅ Baseline established after {LEARNING_THRESHOLD} samples")
        anomaly_score = 0.0
        consecutive_high_anomalies = 0
        return 0.0
    
    scene_changed, correlation = detect_scene_change(hist)
    
    if scene_changed:
        reset_learning(f"Scene change detected (correlation: {correlation:.3f})")
        return 0.0
    
    if scene_baseline is not None:
        scene_baseline = 0.995 * scene_baseline + 0.005 * hist
    
    if scene_baseline is not None:
        correlation = np.corrcoef(scene_baseline, hist)[0, 1]
        anomaly_score = max(0, 1.0 - correlation)
        
        if anomaly_score > 0.5:
            consecutive_high_anomalies += 1
        else:
            consecutive_high_anomalies = 0
        
        if consecutive_high_anomalies >= RELEARN_TRIGGER:
            reset_learning(f"Persistent anomalies ({consecutive_high_anomalies} consecutive)")
            return 0.0
        
        if anomaly_score > 0.3 and not is_relearning:
            severity = "LOW" if learning_confidence < 50 else "MEDIUM" if learning_confidence < 80 else "HIGH"
            anomaly_alerts.append({
                'time': datetime.datetime.now().isoformat(),
                'score': round(anomaly_score, 3),
                'brightness': round(brightness, 1),
                'motion': round(motion_score, 3),
                'confidence': round(learning_confidence, 1),
                'severity': severity,
                'consecutive': consecutive_high_anomalies
            })
            log.warning(f"⚠️  Anomaly: score={anomaly_score:.3f}, confidence={learning_confidence:.1f}%, consecutive={consecutive_high_anomalies}")
        
        return anomaly_score
    
    return 0.0

def detect_objects_tflite(frame):
    global detected_objects
    
    if interpreter is None:
        return []
    
    try:
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        height = input_details[0]['shape'][1]
        width = input_details[0]['shape'][2]
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (width, height))
        input_data = np.expand_dims(frame_resized, axis=0)
        
        if input_details[0]['dtype'] == np.uint8:
            input_data = input_data.astype(np.uint8)
        else:
            input_data = input_data.astype(np.float32)
        
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        
        boxes = interpreter.get_tensor(output_details[0]['index'])[0]
        classes = interpreter.get_tensor(output_details[1]['index'])[0]
        scores = interpreter.get_tensor(output_details[2]['index'])[0]
        
        h, w = frame.shape[:2]
        objects = []
        
        for i in range(len(scores)):
            if scores[i] > 0.5:
                ymin, xmin, ymax, xmax = boxes[i]
                x1 = int(xmin * w)
                y1 = int(ymin * h)
                x2 = int(xmax * w)
                y2 = int(ymax * h)
                
                class_id = int(classes[i])
                label = labels[class_id] if class_id < len(labels) else f"Class {class_id}"
                
                objects.append({
                    'label': label,
                    'confidence': float(scores[i]),
                    'bbox': (x1, y1, x2-x1, y2-y1)
                })
        
        detected_objects = objects
        return objects
        
    except Exception as e:
        log.error(f"Object detection error: {e}")
        return []

def capture_loop():
    global latest_frame, frame_count, camera
    log.info("Capture loop started")
    object_detect_counter = 0
    
    while True:
        try:
            with lock:
                cam = get_camera()
            if cam is None:
                time.sleep(2)
                continue
            
            ret, frame = cam.read()
            if not ret:
                log.warning("Frame read failed, resetting camera")
                with lock:
                    if camera is not None:
                        camera.release()
                        camera = None
                time.sleep(1)
                continue
            
            regions, motion_score = detect_motion_regions(frame)
            anom_score = detect_anomaly(frame, motion_score)
            
            objects = []
            if interpreter and object_detect_counter % 10 == 0:
                objects = detect_objects_tflite(frame)
            object_detect_counter += 1
            
            for (x, y, w, h) in regions:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(frame, "MOTION", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            for obj in objects:
                x, y, w, h = obj['bbox']
                label = f"{obj['label']} {obj['confidence']:.0%}"
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, label, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            if anom_score > 0.3 and not is_relearning:
                cv2.rectangle(frame, (5, 5), (635, 475), (0, 255, 255), 3)
                cv2.putText(frame, f"ANOMALY {anom_score:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if is_relearning:
                cv2.rectangle(frame, (5, 5), (635, 475), (255, 0, 255), 3)
                cv2.putText(frame, f"RE-LEARNING {learning_samples}/{LEARNING_THRESHOLD}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            
            ts_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, ts_text, (10, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
            conf_text = f"Confidence: {learning_confidence:.0f}%"
            stats_text = f"M:{len(regions)} O:{len(objects)} A:{anom_score:.2f} {conf_text}"
            cv2.putText(frame, stats_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            frame_count += 1
            latest_frame = frame.copy()
            time.sleep(0.033)
            
        except Exception as e:
            log.error(f"Capture error: {e}")
            time.sleep(1)

threading.Thread(target=capture_loop, daemon=True).start()

def generate_frames():
    while True:
        if latest_frame is not None:
            _, buf = cv2.imencode(".jpg", latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        time.sleep(0.033)

HTML = """<!DOCTYPE html><html><head><title>Pi Cam Adaptive Learning</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a1a;color:#e0e0e0;font-family:'Segoe UI',sans-serif;padding:20px}
.header{text-align:center;padding:10px 0;border-bottom:1px solid #0ff3;margin-bottom:20px}
h1{color:#0ff;font-size:1.8em}
.sub{color:#888;font-size:0.9em;margin-top:4px}
.main{display:grid;grid-template-columns:1fr 350px;gap:20px}
@media(max-width:1100px){.main{grid-template-columns:1fr}}
.video-box{position:relative}
.video-box img{width:100%;border:2px solid #0ff;border-radius:8px}
.legend{display:flex;gap:15px;margin-top:10px;font-size:0.85em;flex-wrap:wrap}
.legend-item{display:flex;align-items:center;gap:5px}
.legend-box{width:15px;height:15px;border-radius:2px}
.red-box{background:#f00;border:1px solid #f00}
.green-box{background:#0f0;border:1px solid #0f0}
.yellow-box{background:#ff0;border:1px solid #ff0}
.purple-box{background:#f0f;border:1px solid #f0f}
.sidebar{display:flex;flex-direction:column;gap:12px}
.card{background:#12122a;border:1px solid #ffffff15;border-radius:8px;overflow:hidden}
.card-header{padding:12px 15px;border-bottom:1px solid #ffffff15;display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none}
.card-header:hover{background:#15152e}
.card-header h3{margin:0;color:#0ff;font-size:1em}
.card-header .toggle{color:#888;font-size:1.2em;transition:transform 0.3s}
.card-header .toggle.collapsed{transform:rotate(-90deg)}
.card-body{padding:15px;transition:max-height 0.3s ease-out;overflow:hidden}
.card-body.collapsed{max-height:0!important;padding:0 15px;display:none}
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.85em;font-weight:bold}
.live{background:#0f02;color:#0f0;border:1px solid #0f0}
.learning{background:#ff02;color:#ff0;border:1px solid #ff0}
.relearning{background:#f0f2;color:#f0f;border:1px solid #f0f;animation:pulse 1s infinite}
.trained{background:#0f02;color:#0f0;border:1px solid #0f0}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.stat{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #ffffff08;font-size:0.9em}
.stat-val{color:#0ff;font-weight:600}
.progress-container{margin:8px 0}
.progress-label{display:flex;justify-content:space-between;font-size:0.85em;margin-bottom:4px}
.progress-bar{height:8px;background:#1a1a2a;border-radius:4px;overflow:hidden}
.progress-fill{height:100%;background:linear-gradient(90deg,#0ff,#0f0);border-radius:4px;transition:width 0.5s}
.chart-container{height:120px;margin-top:10px}
canvas{max-height:120px}
.btn{display:inline-block;padding:8px 16px;background:#0ff2;color:#0ff;border:1px solid #0ff;
     border-radius:6px;cursor:pointer;text-decoration:none;font-size:0.9em;text-align:center;margin:4px}
.btn:hover{background:#0ff4}
.btn-danger{background:#f002;color:#f44;border:1px solid #f44}
.btn-danger:hover{background:#f004}
.obj-list{max-height:140px;overflow-y:auto;font-size:0.85em}
.obj-item{padding:4px 0;border-bottom:1px solid #ffffff08;display:flex;justify-content:space-between}
.anomaly-list{max-height:140px;overflow-y:auto;font-size:0.85em}
.anomaly-item{padding:6px;margin:4px 0;background:#1a1a2a;border-radius:4px}
.anomaly-item.severity-HIGH{border-left:3px solid #f44}
.anomaly-item.severity-MEDIUM{border-left:3px solid #fa0}
.anomaly-item.severity-LOW{border-left:3px solid #ff0}
.anomaly-time{font-size:0.75em;color:#888}
.anomaly-score{color:#f44;font-weight:bold}
.alert-box{background:#f002;border:1px solid #f44;border-radius:6px;padding:10px;margin:8px 0;font-size:0.85em}
.alert-box.info{background:#0ff2;border-color:#0ff}
.relearn-info{font-size:0.85em;color:#888;margin-top:4px}
</style></head><body>
<div class="header">
  <h1>🧠 Pi Camera Monitor - Adaptive Learning</h1>
  <p class="sub">Enhanced v5.0 with Intelligent Scene Adaptation</p>
  <p class="sub"><span class="badge live">● LIVE</span> <span id="learningBadge" class="badge learning">LEARNING</span></p>
</div>
<div class="main">
  <div>
    <div class="video-box">
      <img src="/video_feed" alt="Live Feed">
    </div>
    <div class="legend">
      <div class="legend-item"><div class="legend-box red-box"></div><span>Motion</span></div>
      <div class="legend-item"><div class="legend-box green-box"></div><span>Objects (ML)</span></div>
      <div class="legend-item"><div class="legend-box yellow-box"></div><span>Anomaly</span></div>
      <div class="legend-item"><div class="legend-box purple-box"></div><span>Re-Learning</span></div>
    </div>
    <div id="relearnAlert" class="alert-box info" style="display:none;margin-top:15px">
      <strong>🔄 Scene Change Detected!</strong><br>
      <span id="relearnReason">System is re-learning the new environment...</span>
    </div>
  </div>
  <div class="sidebar">
    <div class="card">
      <div class="card-header" onclick="toggleCard('status')">
        <h3>⚡ Status</h3>
        <span class="toggle" id="toggle-status">▼</span>
      </div>
      <div class="card-body" id="body-status">
        <div class="stat"><span>Uptime</span><span class="stat-val" id="uptime">--</span></div>
        <div class="stat"><span>Frames</span><span class="stat-val" id="frames">--</span></div>
        <div class="stat"><span>FPS</span><span class="stat-val" id="fps">--</span></div>
        <div class="stat"><span>Motion Regions</span><span class="stat-val" id="motionCount">--</span></div>
        <div class="stat"><span>Objects</span><span class="stat-val" id="objectCount">--</span></div>
        <div class="stat"><span>Anomaly Score</span><span id="anomalyScore" class="stat-val">--</span></div>
      </div>
    </div>
    <div class="card">
      <div class="card-header" onclick="toggleCard('learning')">
        <h3>🧠 Adaptive Learning</h3>
        <span class="toggle" id="toggle-learning">▼</span>
      </div>
      <div class="card-body" id="body-learning">
        <div class="progress-container">
          <div class="progress-label">
            <span>Training Progress</span>
            <span id="learnProgress">0/30</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="learnBar" style="width:0%"></div>
          </div>
        </div>
        <div class="stat"><span>Samples</span><span class="stat-val" id="learnSamples">--</span></div>
        <div class="stat"><span>Confidence</span><span class="stat-val" id="learnConfidence">--</span></div>
        <div class="stat"><span>Status</span><span id="learnStatus" class="badge learning">LEARNING</span></div>
        <div class="stat"><span>Total Relearns</span><span class="stat-val" id="totalRelearns">--</span></div>
        <div class="relearn-info" id="relearnInfo">Baseline not yet established</div>
      </div>
    </div>
    <div class="card">
      <div class="card-header" onclick="toggleCard('charts')">
        <h3>📊 History Charts</h3>
        <span class="toggle" id="toggle-charts">▼</span>
      </div>
      <div class="card-body" id="body-charts">
        <div style="margin-bottom:15px">
          <div style="font-size:0.9em;margin-bottom:5px;color:#888">Brightness History</div>
          <div class="chart-container"><canvas id="brightChart"></canvas></div>
        </div>
        <div>
          <div style="font-size:0.9em;margin-bottom:5px;color:#888">Motion Score History</div>
          <div class="chart-container"><canvas id="motionChart"></canvas></div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <h3>📸 Controls</h3>
      </div>
      <div class="card-body">
        <a class="btn" href="/snapshot" target="_blank">Snapshot</a>
        <button class="btn btn-danger" onclick="resetLearning()">🔄 Reset Learning</button>
      </div>
    </div>
    <div class="card">
      <div class="card-header" onclick="toggleCard('objects')">
        <h3>🔍 Detected Objects</h3>
        <span class="toggle" id="toggle-objects">▼</span>
      </div>
      <div class="card-body" id="body-objects">
        <div class="obj-list" id="objectList">Waiting...</div>
      </div>
    </div>
    <div class="card">
      <div class="card-header" onclick="toggleCard('anomalies')">
        <h3>⚠️ Anomaly Alerts</h3>
        <span class="toggle" id="toggle-anomalies">▼</span>
      </div>
      <div class="card-body" id="body-anomalies">
        <div class="anomaly-list" id="anomalyList">No anomalies detected</div>
      </div>
    </div>
  </div>
</div>
<script>
let brightChart, motionChart;
function initCharts(){
  const brightCtx=document.getElementById('brightChart').getContext('2d');
  brightChart=new Chart(brightCtx,{
    type:'line',
    data:{labels:[],datasets:[{label:'Brightness',data:[],borderColor:'#0ff',backgroundColor:'rgba(0,255,255,0.1)',tension:0.4}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:255,grid:{color:'#ffffff10'}},x:{display:false}}}
  });
  const motionCtx=document.getElementById('motionChart').getContext('2d');
  motionChart=new Chart(motionCtx,{
    type:'line',
    data:{labels:[],datasets:[{label:'Motion',data:[],borderColor:'#f00',backgroundColor:'rgba(255,0,0,0.1)',tension:0.4}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:1,grid:{color:'#ffffff10'}},x:{display:false}}}
  });
}
function updateCharts(bright,motion){
  if(bright.length>0){
    brightChart.data.labels=bright.map((_,i)=>i);
    brightChart.data.datasets[0].data=bright.map(d=>d.v);
    brightChart.update('none');
  }
  if(motion.length>0){
    motionChart.data.labels=motion.map((_,i)=>i);
    motionChart.data.datasets[0].data=motion.map(d=>d.v);
    motionChart.update('none');
  }
}
function toggleCard(id){
  const body=document.getElementById('body-'+id);
  const toggle=document.getElementById('toggle-'+id);
  body.classList.toggle('collapsed');
  toggle.classList.toggle('collapsed');
}
function resetLearning(){
  if(confirm('Reset learning baseline? The system will start learning from scratch.')){
    fetch('/api/reset_learning',{method:'POST'}).then(r=>r.json()).then(d=>{
      alert('Learning baseline reset: '+d.message);
    });
  }
}
function poll(){
  fetch("/api/status").then(r=>r.json()).then(d=>{
    document.getElementById("uptime").textContent=d.uptime;
    document.getElementById("frames").textContent=d.frames.toLocaleString();
    document.getElementById("fps").textContent=d.fps.toFixed(1);
    document.getElementById("motionCount").textContent=d.motion_regions;
    document.getElementById("objectCount").textContent=d.objects_detected;
    document.getElementById("anomalyScore").textContent=d.anomaly_score.toFixed(3);
    document.getElementById("learnSamples").textContent=d.learning_samples;
    document.getElementById("learnProgress").textContent=d.learning_samples+"/30";
    document.getElementById("learnConfidence").textContent=d.learning_confidence.toFixed(0)+"%";
    document.getElementById("totalRelearns").textContent=d.total_relearns;
    
    let pct=Math.min(d.learning_samples/30*100,100);
    document.getElementById("learnBar").style.width=pct+"%";
    
    let lb=document.getElementById("learningBadge");
    let ls=document.getElementById("learnStatus");
    let ri=document.getElementById("relearnInfo");
    let ra=document.getElementById("relearnAlert");
    
    if(d.is_relearning){
      lb.textContent="RE-LEARNING";lb.className="badge relearning";
      ls.textContent="RE-LEARNING";ls.className="badge relearning";
      ri.innerHTML="<strong>🔄 "+d.relearn_reason+"</strong><br>Progress: "+d.learning_samples+"/30";
      ra.style.display="block";
      document.getElementById("relearnReason").textContent=d.relearn_reason;
    }else if(d.learning_samples<30){
      lb.textContent="LEARNING";lb.className="badge learning";
      ls.textContent="LEARNING";ls.className="badge learning";
      ri.textContent="Establishing baseline... "+d.learning_samples+"/30 samples";
      ra.style.display="none";
    }else{
      lb.textContent="TRAINED";lb.className="badge trained";
      ls.textContent="TRAINED";ls.className="badge trained";
      ri.innerHTML="Baseline established<br>Confidence: "+d.learning_confidence.toFixed(0)+"%";
      ra.style.display="none";
    }
    
    if(d.anomaly_score>0.3){
      document.getElementById("anomalyScore").style.color="#f44";
    }else{
      document.getElementById("anomalyScore").style.color="#0ff";
    }
  }).catch(()=>{});
  
  fetch("/api/detections").then(r=>r.json()).then(d=>{
    let el=document.getElementById("objectList");
    if(d.objects.length===0){el.innerHTML="<div style='color:#888;padding:8px'>No objects</div>"}
    else{
      el.innerHTML=d.objects.map(o=>
        "<div class='obj-item'><span style='color:#0f0'>"+o.label+"</span><span style='color:#888'>"+Math.round(o.confidence*100)+"%</span></div>"
      ).join("");
    }
  }).catch(()=>{});
  
  fetch("/api/anomaly_alerts").then(r=>r.json()).then(d=>{
    let el=document.getElementById("anomalyList");
    if(d.length===0){el.innerHTML="<div style='color:#888;padding:8px'>No anomalies</div>"}
    else{
      el.innerHTML=d.slice(-10).reverse().map(a=>
        "<div class='anomaly-item severity-"+a.severity+"'><div class='anomaly-time'>"+a.time.split("T")[1].split(".")[0]+"</div>"+
        "<div>Score: <span class='anomaly-score'>"+a.score+"</span> | Confidence: "+a.confidence+"%</div>"+
        "<div style='font-size:0.75em;color:#888'>Consecutive: "+a.consecutive+"</div></div>"
      ).join("");
    }
  }).catch(()=>{});
  
  fetch("/api/history").then(r=>r.json()).then(d=>{
    updateCharts(d.brightness,d.motion);
  }).catch(()=>{});
}
initCharts();
setInterval(poll,2000);poll();
</script></body></html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/snapshot")
def snapshot():
    if latest_frame is not None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SNAP_DIR, f"snap_{ts}.jpg")
        cv2.imwrite(path, latest_frame)
        _, buf = cv2.imencode(".jpg", latest_frame)
        log.info(f"Snapshot saved: {path}")
        return Response(buf.tobytes(), mimetype="image/jpeg")
    return "No frame available", 503

@app.route("/api/status")
def api_status():
    elapsed = time.time() - start_time
    h, m = divmod(int(elapsed), 3600)
    m, s = divmod(m, 60)
    return jsonify({
        "motion_regions": len(motion_regions),
        "objects_detected": len(detected_objects),
        "frames": frame_count,
        "fps": round(frame_count / max(elapsed, 1), 1),
        "uptime": f"{h}h {m}m {s}s",
        "ml_active": interpreter is not None,
        "anomaly_score": anomaly_score,
        "learning_samples": learning_samples,
        "learning_confidence": learning_confidence,
        "is_relearning": is_relearning,
        "relearn_reason": relearn_reason,
        "total_relearns": total_relearns,
        "consecutive_anomalies": consecutive_high_anomalies
    })

@app.route("/api/detections")
def api_detections():
    return jsonify({
        "motion_regions": [{"x": x, "y": y, "w": w, "h": h} for x, y, w, h in motion_regions],
        "objects": detected_objects
    })

@app.route("/api/history")
def api_history():
    return jsonify({
        "brightness": list(brightness_history)[-50:],
        "motion": list(motion_score_history)[-50:]
    })

@app.route("/api/anomaly_alerts")
def api_anomaly_alerts():
    return jsonify(list(anomaly_alerts))

@app.route("/api/reset_learning", methods=["POST"])
def api_reset_learning():
    reset_learning("Manual reset via API")
    return jsonify({
        "status": "ok",
        "message": f"Learning reset. Starting fresh. (Total resets: {total_relearns})"
    })

@app.route("/api/health")
def health():
    cam_ok = camera is not None and camera.isOpened() if camera else False
    return jsonify({
        "status": "healthy" if cam_ok else "degraded",
        "camera": cam_ok,
        "ml": interpreter is not None,
        "frames": frame_count,
        "learning_complete": learning_samples >= LEARNING_THRESHOLD,
        "is_relearning": is_relearning,
        "total_relearns": total_relearns
    }), 200 if cam_ok else 503

if __name__ == "__main__":
    log.info("Starting Enhanced Camera Monitor v5.0 (Adaptive Learning) on port 5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)
