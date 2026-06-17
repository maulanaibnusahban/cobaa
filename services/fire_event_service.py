"""
KRTI UAV System — Fire Event Service
========================================
Thread state machine untuk memproses fire detection.
Monitor shared state fire_status, kelola event (IDLE/FIRE_ACTIVE),
dan picu image capture & transmisi jika ada api.
"""

import threading
import time
import cv2
import base64

from config.settings import (
    FIRE_CONFIDENCE_THRESHOLD, IMAGE_COOLDOWN_SEC,
    FIRE_RESET_SEC, FIRE_ACK_TIMEOUT_SEC, FIRE_ACK_MAX_RETRY,
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    IMAGE_JPEG_QUALITY, IMAGE_RESIZE_W, IMAGE_RESIZE_H,
    IMAGE_CHUNK_SIZE
)
from state.shared_state import SharedState
from models.fire_event import FireState
from services.gateway_service import GatewayService
from protocol.parser import (
    build_fire_event_packet, build_image_start_packet,
    build_image_data_packet, build_image_end_packet
)
from utils.logger import get_logger

log = get_logger("FIRE_EVENT")


class FireEventService:
    """
    Service pengelola state machine Fire Event.
    """

    def __init__(self, state: SharedState, gateway: GatewayService):
        self._state = state
        self._gateway = gateway
        self._running = False
        self._thread = None
        
        # Kamera terpisah dari deteksi (hanya untuk capture saat trigger)
        # Note: karena opencv terkadang bermasalah jika 1 device diakses 2 service,
        # kita bisa memanfaatkan frame dari fire_detection jika ada mekanisme sharing,
        # tapi untuk kesederhanaan dan kestabilan, kita asumsikan FireEvent 
        # melakukan snapshot mandiri atau kita bisa gabungkan frame capture ke shared state.
        # Disini kita buka VideoCapture mandiri sejenak saat butuh snapshot,
        # atau jika gagal, kita tidak kirim gambar.
        # Pendekatan terbaik: ambil frame dari kamera saat dibutuhkan.
        self._event_id_counter = int(time.time()) & 0xFFFF  # Randomizer start

    def start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="FireEvent", daemon=True
        )
        self._thread.start()
        log.info("Fire event service started")

    def stop(self):
        self._running = False
        log.info("Fire event service stopped")

    def _run(self):
        """State machine loop."""
        while self._running:
            fire_status = self._state.get_fire_status()
            fire_event = self._state.get_fire_event()
            now = time.time()

            detected = fire_status["detected"]
            conf = fire_status["confidence"]

            if fire_event["state"] == FireState.IDLE:
                if detected and conf >= FIRE_CONFIDENCE_THRESHOLD:
                    log.warning(f"🔥 API TERDETEKSI! Confidence: {conf:.2f}")
                    self._trigger_new_event()
                else:
                    time.sleep(0.1)

            elif fire_event["state"] == FireState.FIRE_ACTIVE:
                if detected and conf >= FIRE_CONFIDENCE_THRESHOLD:
                    # Api masih ada, perbarui timer
                    self._state.update_fire_event(fire_lost_time=now)

                    # Cek cooldown gambar
                    if now - fire_event["last_image_time"] >= IMAGE_COOLDOWN_SEC:
                        log.info("Cooldown selesai, ambil gambar lagi...")
                        self._capture_and_send_image(fire_event["event_id"])
                        self._state.update_fire_event(last_image_time=time.time())
                else:
                    # Api tidak terdeteksi
                    lost_duration = now - fire_event["fire_lost_time"]
                    if lost_duration >= FIRE_RESET_SEC:
                        log.info(f"Api hilang selama {FIRE_RESET_SEC}s. Reset ke IDLE.")
                        self._state.reset_fire_event()
                
                time.sleep(0.1)

    def _trigger_new_event(self):
        """Transisi dari IDLE -> FIRE_ACTIVE."""
        self._event_id_counter += 1
        event_id = self._event_id_counter

        # Ambil lokasi dari telemetry
        telem = self._state.get_telemetry()
        lat, lon, alt = telem["lat"], telem["lon"], telem["rel_alt"]

        # Update state
        now = time.time()
        self._state.update_fire_event(
            event_id=event_id,
            state=FireState.FIRE_ACTIVE,
            lat=lat, lon=lon, alt=alt,
            timestamp=now,
            last_image_time=now,
            fire_lost_time=now,
            ack_received=False
        )

        # Kirim metadata FIRE
        packet = build_fire_event_packet(event_id, lat, lon, alt)
        
        # Kirim dengan retry sampai dapat ACK (lewat shared state)
        ack_ok = False
        for i in range(FIRE_ACK_MAX_RETRY):
            log.info(f"Mengirim FIRE metadata (Try {i+1}/{FIRE_ACK_MAX_RETRY}): {packet}")
            self._gateway.send_packet(packet)
            
            # Tunggu ACK
            start_wait = time.time()
            while time.time() - start_wait < FIRE_ACK_TIMEOUT_SEC:
                ev = self._state.get_fire_event()
                if ev["ack_received"]:
                    ack_ok = True
                    break
                time.sleep(0.1)
            
            if ack_ok:
                log.info(f"✓ ACK_FIRE diterima untuk event {event_id}")
                break
        
        if not ack_ok:
            log.warning(f"Timeout menunggu ACK_FIRE event {event_id}. Melanjutkan proses image.")

        # Ambil dan kirim gambar
        self._capture_and_send_image(event_id)

    def _capture_and_send_image(self, event_id: int):
        """Ambil gambar dari webcam, kompres, encode Base64, dan kirim per chunk."""
        cap = cv2.VideoCapture(CAMERA_INDEX)
        # Flush beberapa frame agar exposure menyesuaikan
        for _ in range(5):
            cap.read()
            
        ret, frame = cap.read()
        cap.release()

        if not ret:
            log.error("Gagal mengambil gambar dari kamera")
            return

        # Resize
        frame = cv2.resize(frame, (IMAGE_RESIZE_W, IMAGE_RESIZE_H))

        # Compress ke JPEG
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, IMAGE_JPEG_QUALITY])
        if not ok:
            log.error("Gagal encode gambar ke JPEG")
            return

        # Ambil byte data
        image_bytes = buf.tobytes()
        
        # Encode ke Base64 agar text-safe
        b64_bytes = base64.b64encode(image_bytes)
        b64_string = b64_bytes.decode('ascii')
        
        total_size = len(b64_string)
        
        # Pecah jadi chunks
        chunks = [
            b64_string[i : i + IMAGE_CHUNK_SIZE]
            for i in range(0, total_size, IMAGE_CHUNK_SIZE)
        ]
        total_packets = len(chunks)

        log.info(f"Mengirim gambar ID {event_id} ({total_packets} chunks, {total_size} chars)")

        # 1. Kirim IMG_START
        start_pkt = build_image_start_packet(event_id, total_packets, total_size)
        self._gateway.send_packet(start_pkt)
        time.sleep(0.2) # Jeda agar ESP32 sempat proses

        # 2. Kirim chunks
        for seq, chunk in enumerate(chunks):
            data_pkt = build_image_data_packet(event_id, seq, total_packets, chunk)
            self._gateway.send_packet(data_pkt)
            # Beri jeda antar chunk agar tidak flood UART/LoRa buffer (akan di schedule di ESP32 juga)
            time.sleep(0.1)

        # 3. Kirim IMG_END
        end_pkt = build_image_end_packet(event_id)
        self._gateway.send_packet(end_pkt)
        log.info(f"Gambar ID {event_id} selesai diteruskan ke gateway")
