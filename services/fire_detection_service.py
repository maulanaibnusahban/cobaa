
import threading
import time
import cv2
import math

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from config.settings import (
    FIRE_MODEL_PATH, FIRE_CONFIDENCE_THRESHOLD,
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    INFERENCE_RESIZE_W, INFERENCE_RESIZE_H,
)
from state.shared_state import SharedState
from utils.logger import get_logger

log = get_logger("FIRE_DETECT")


class FireDetectionService:
    """
    Service fire detection — berjalan sebagai thread terpisah.
    Hanya membaca dari webcam dan update shared state.
    """

    def __init__(self, state: SharedState):
        self._state = state
        self._running = False
        self._thread = None
        self._model = None
        self._cap = None

    def start(self):
        """Start fire detection thread."""
        if YOLO is None:
            log.error("ultralytics YOLO tidak terinstall. Fire detection disabled.")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="FireDetect", daemon=True
        )
        self._thread.start()
        log.info("Fire detection service started")

    def stop(self):
        """Stop fire detection thread."""
        self._running = False
        log.info("Fire detection service stopped")

    def _run(self):
        """Main inference loop."""
        # 1. Load Model
        try:
            log.info(f"Loading YOLO model dari: {FIRE_MODEL_PATH}")
            self._model = YOLO(FIRE_MODEL_PATH)
            log.info("YOLO model loaded")
        except Exception as e:
            log.error(f"Gagal load model: {e}")
            self._running = False
            return

        # 2. Init Camera
        try:
            log.info(f"Membuka camera index {CAMERA_INDEX}")
            self._cap = cv2.VideoCapture(CAMERA_INDEX)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            
            if not self._cap.isOpened():
                log.error("Gagal membuka camera")
                self._running = False
                return
        except Exception as e:
            log.error(f"Camera init error: {e}")
            self._running = False
            return

        # 3. Inference Loop
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                log.error("Gagal membaca frame, reconnecting...")
                self._cap.release()
                time.sleep(1)
                self._cap = cv2.VideoCapture(CAMERA_INDEX)
                continue

            frame_resized = cv2.resize(frame, (INFERENCE_RESIZE_W, INFERENCE_RESIZE_H))

            # Jalankan inferensi
            results = self._model(frame_resized, stream=True, verbose=False)

            detected = False
            highest_conf = 0.0

            for info in results:
                boxes = info.boxes
                for box in boxes:
                    confidence = float(box.conf[0])
                    # cls_idx = int(box.cls[0])
                    
                    if confidence > highest_conf:
                        highest_conf = confidence

                    if confidence >= FIRE_CONFIDENCE_THRESHOLD:
                        detected = True

            # Update shared state
            self._state.update_fire_status(detected, highest_conf)

            # Jeda sebentar agar tidak makan 100% CPU jika inferensi sangat cepat
            time.sleep(0.05)

        # Cleanup
        if self._cap:
            self._cap.release()
