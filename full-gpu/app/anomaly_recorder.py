
import cv2
import uuid
import threading
import logging
import datetime
from collections import deque
from pathlib import Path

log = logging.getLogger("anomaly-recorder")

class AnomalyRecorder:
    def __init__(self, clips_dir, fps=30):
        self.clips_dir = Path(clips_dir)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.frame_buffer = deque(maxlen=150)
        self.is_recording = False
        self.clip_id = None
        self.writer = None
        self.frames_after = 0
        self.lock = threading.Lock()
        log.info(f"📹 Anomaly Recorder initialized")
    
    def add_frame(self, frame):
        if frame is not None:
            self.frame_buffer.append(frame.copy())
    
    def start_recording(self, anomaly_data):
        with self.lock:
            if self.is_recording:
                return None
            self.is_recording = True
            self.clip_id = str(uuid.uuid4())[:8]
            self.frames_after = 0
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            severity = anomaly_data.get("severity", "UNK")
            atype = anomaly_data.get("type", "unknown")
            filename = f"anomaly_{timestamp}_{severity}_{atype}_{self.clip_id}.mp4"
            filepath = self.clips_dir / filename
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(str(filepath), fourcc, self.fps, (1280,720))
            if not self.writer.isOpened():
                log.error(f"❌ Failed to open video writer")
                self.is_recording = False
                return None
            for f in self.frame_buffer:
                if f is not None:
                    self.writer.write(f)
            anomaly_data["clip_id"] = self.clip_id
            anomaly_data["clip_filename"] = filename
            log.info(f"📹 Recording clip: {self.clip_id}")
            return self.clip_id
    
    def record_frame(self, frame):
        with self.lock:
            if self.is_recording and self.writer:
                self.writer.write(frame)
                self.frames_after += 1
                if self.frames_after >= 150:
                    self.stop_recording()
    
    def stop_recording(self):
        if self.writer:
            self.writer.release()
            self._make_thumbnail()
        self.is_recording = False
        cid = self.clip_id
        self.clip_id = None
        if cid:
            log.info(f"✅ Clip saved: {cid}")
    
    def _make_thumbnail(self):
        if not self.clip_id:
            return
        clips = list(self.clips_dir.glob(f"*{self.clip_id}*.mp4"))
        if not clips:
            return
        cap = cv2.VideoCapture(str(clips[0]))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
            ret, frame = cap.read()
            if ret and frame is not None:
                thumb = cv2.resize(frame, (320, 180))
                cv2.imwrite(str(clips[0].with_suffix(".jpg")), thumb)
        cap.release()
    
    def get_clip_path(self, clip_id):
        clips = list(self.clips_dir.glob(f"*{clip_id}*.mp4"))
        return clips[0] if clips else None
    
    def get_thumbnail_path(self, clip_id):
        thumbs = list(self.clips_dir.glob(f"*{clip_id}*.jpg"))
        return thumbs[0] if thumbs else None
