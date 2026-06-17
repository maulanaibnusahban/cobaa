"""
KRTI UAV System — Shared State
=================================
Thread-safe shared state untuk komunikasi antar service.
Semua service membaca/menulis melalui objek ini.
Menggunakan threading.Lock untuk thread safety.
"""

import threading
import time
from utils.logger import get_logger

log = get_logger("STATE")


class SharedState:
    """
    Thread-safe shared state container.
    Semua field dilindungi oleh lock individual untuk
    mengurangi contention antar thread.
    """

    def __init__(self):
        # ── Locks ──────────────────────────────────────────────────
        self._telem_lock = threading.Lock()
        self._fire_lock = threading.Lock()
        self._fire_event_lock = threading.Lock()
        self._mission_lock = threading.Lock()
        self._vehicle_lock = threading.Lock()

        # ── Telemetry ──────────────────────────────────────────────
        self._latest_telemetry = {
            "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
            "lat": 0.0, "lon": 0.0,
            "alt": 0.0, "rel_alt": 0.0,
            "vx": 0.0, "vy": 0.0, "vz": 0.0,
            "gps_fix": 0, "satellites": 0,
            "battery": 0.0, "battery_pct": 0,
            "armed": 0, "mode": 255,
            "timestamp": 0.0,
        }

        # ── Fire Detection Status ──────────────────────────────────
        self._fire_status = {
            "detected": False,
            "confidence": 0.0,
            "timestamp": 0.0,
        }

        # ── Current Fire Event ─────────────────────────────────────
        self._current_fire_event = {
            "event_id": 0,
            "state": "IDLE",        # IDLE | FIRE_ACTIVE
            "lat": 0.0,
            "lon": 0.0,
            "alt": 0.0,
            "timestamp": 0.0,
            "last_image_time": 0.0,
            "fire_lost_time": 0.0,
        }

        # ── Mission Status ─────────────────────────────────────────
        self._mission_status = {
            "state": "IDLE",        # IDLE | UPLOADING | UPLOADED | RUNNING
            "items": [],            # list of mission item dicts
            "total": 0,
            "uploaded": 0,
            "timestamp": 0.0,
        }

        # ── Vehicle Status ─────────────────────────────────────────
        self._vehicle_status = {
            "armed": False,
            "mode": 255,
            "connected": False,
            "timestamp": 0.0,
        }

    # ── Telemetry ──────────────────────────────────────────────────

    def update_telemetry(self, data: dict):
        """Update telemetry data (dipanggil oleh TelemetryService)."""
        with self._telem_lock:
            self._latest_telemetry.update(data)
            self._latest_telemetry["timestamp"] = time.time()

    def get_telemetry(self) -> dict:
        """Ambil salinan telemetry terbaru."""
        with self._telem_lock:
            return dict(self._latest_telemetry)

    # ── Fire Detection Status ──────────────────────────────────────

    def update_fire_status(self, detected: bool, confidence: float):
        """Update fire detection result (dipanggil oleh FireDetectionService)."""
        with self._fire_lock:
            self._fire_status["detected"] = detected
            self._fire_status["confidence"] = confidence
            self._fire_status["timestamp"] = time.time()

    def get_fire_status(self) -> dict:
        """Ambil salinan fire detection status."""
        with self._fire_lock:
            return dict(self._fire_status)

    # ── Fire Event ─────────────────────────────────────────────────

    def update_fire_event(self, **kwargs):
        """Update fire event state (dipanggil oleh FireEventService)."""
        with self._fire_event_lock:
            self._current_fire_event.update(kwargs)

    def get_fire_event(self) -> dict:
        """Ambil salinan fire event."""
        with self._fire_event_lock:
            return dict(self._current_fire_event)

    def reset_fire_event(self):
        """Reset fire event ke IDLE."""
        with self._fire_event_lock:
            self._current_fire_event = {
                "event_id": self._current_fire_event.get("event_id", 0),
                "state": "IDLE",
                "lat": 0.0, "lon": 0.0, "alt": 0.0,
                "timestamp": 0.0,
                "last_image_time": 0.0,
                "fire_lost_time": 0.0,
            }

    # ── Mission Status ─────────────────────────────────────────────

    def update_mission_status(self, **kwargs):
        """Update mission state."""
        with self._mission_lock:
            self._mission_status.update(kwargs)
            self._mission_status["timestamp"] = time.time()

    def get_mission_status(self) -> dict:
        """Ambil salinan mission status."""
        with self._mission_lock:
            return dict(self._mission_status)

    def add_mission_item(self, item: dict):
        """Tambah satu mission item ke buffer."""
        with self._mission_lock:
            self._mission_status["items"].append(item)
            self._mission_status["total"] = len(self._mission_status["items"])

    def clear_mission_items(self):
        """Hapus semua mission items."""
        with self._mission_lock:
            self._mission_status["items"] = []
            self._mission_status["total"] = 0
            self._mission_status["uploaded"] = 0
            self._mission_status["state"] = "IDLE"

    # ── Vehicle Status ─────────────────────────────────────────────

    def update_vehicle_status(self, **kwargs):
        """Update vehicle status."""
        with self._vehicle_lock:
            self._vehicle_status.update(kwargs)
            self._vehicle_status["timestamp"] = time.time()

    def get_vehicle_status(self) -> dict:
        """Ambil salinan vehicle status."""
        with self._vehicle_lock:
            return dict(self._vehicle_status)
