"""
KRTI UAV System — Gateway Service
=====================================
UART communication dengan ESP32 Drone Gateway.
Thread-safe send/receive dengan auto-reconnect.

Raspberry Pi ←→ ESP32 Drone Gateway via UART.
Semua komunikasi LoRa dihandle oleh ESP32, bukan Raspberry Pi.
"""

import serial
import threading
import queue
import time

from config.settings import ESP_PORT, ESP_BAUDRATE, UART_RECONNECT_DELAY
from protocol.parser import parse_line
from utils.logger import get_logger

log = get_logger("GATEWAY")


class GatewayService:
    """
    Service untuk komunikasi UART dengan ESP32 Drone Gateway.

    - outgoing_queue: packet yang akan dikirim ke ESP32 (→ LoRa → Ground)
    - incoming_queue: packet yang diterima dari ESP32 (← LoRa ← Ground)
    """

    def __init__(self):
        self._serial = None
        self._lock = threading.Lock()
        self._running = False

        # Queue untuk packet management
        self.outgoing_queue = queue.Queue(maxsize=100)
        self.incoming_queue = queue.Queue(maxsize=100)

        # Threads
        self._rx_thread = None
        self._tx_thread = None

    # ══════════════════════════════════════════════════════════════════
    # CONNECTION
    # ══════════════════════════════════════════════════════════════════

    def connect(self) -> bool:
        """Buka koneksi UART ke ESP32."""
        try:
            self._serial = serial.Serial(
                ESP_PORT,
                ESP_BAUDRATE,
                timeout=0.1
            )
            time.sleep(0.5)  # Tunggu ESP32 ready
            log.info(f"UART terhubung: {ESP_PORT} @ {ESP_BAUDRATE}")
            return True
        except Exception as e:
            log.error(f"Gagal buka UART: {e}")
            self._serial = None
            return False

    def reconnect(self) -> bool:
        """Reconnect UART dengan delay."""
        log.warning(f"UART reconnect dalam {UART_RECONNECT_DELAY}s...")
        try:
            if self._serial:
                self._serial.close()
        except Exception:
            pass
        self._serial = None
        time.sleep(UART_RECONNECT_DELAY)
        return self.connect()

    # ══════════════════════════════════════════════════════════════════
    # START / STOP
    # ══════════════════════════════════════════════════════════════════

    def start(self):
        """Start RX dan TX threads."""
        self._running = True

        self._rx_thread = threading.Thread(
            target=self._rx_loop, name="GW-RX", daemon=True
        )
        self._tx_thread = threading.Thread(
            target=self._tx_loop, name="GW-TX", daemon=True
        )

        self._rx_thread.start()
        self._tx_thread.start()
        log.info("Gateway service started (RX + TX threads)")

    def stop(self):
        """Stop service dan tutup serial."""
        self._running = False
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        log.info("Gateway service stopped")

    # ══════════════════════════════════════════════════════════════════
    # SEND (Thread-safe)
    # ══════════════════════════════════════════════════════════════════

    def send_packet(self, text_line: str):
        """
        Kirim satu baris text ke ESP32 via UART.
        Thread-safe — bisa dipanggil dari service manapun.

        Args:
            text_line: String tanpa trailing newline (akan ditambahkan)
        """
        try:
            self.outgoing_queue.put_nowait(text_line)
        except queue.Full:
            log.warning("Outgoing queue full, packet dropped")

    # ══════════════════════════════════════════════════════════════════
    # INTERNAL THREADS
    # ══════════════════════════════════════════════════════════════════

    def _rx_loop(self):
        """Background thread: baca data dari ESP32 UART secara terus-menerus."""
        while self._running:
            if not self._serial or not self._serial.is_open:
                if not self.reconnect():
                    continue

            try:
                raw = self._serial.readline()
                if raw:
                    line = raw.decode("ascii", errors="ignore").strip()
                    if line:
                        # Parse dan masukkan ke incoming queue
                        pkt_type, pkt_data = parse_line(line)
                        try:
                            self.incoming_queue.put_nowait((pkt_type, pkt_data))
                        except queue.Full:
                            log.warning("Incoming queue full, packet dropped")
            except serial.SerialException as e:
                log.error(f"UART RX error: {e}")
                self._serial = None
                time.sleep(0.5)
            except Exception as e:
                log.error(f"RX unexpected error: {e}")
                time.sleep(0.1)

    def _tx_loop(self):
        """Background thread: kirim data ke ESP32 UART dari outgoing queue."""
        while self._running:
            try:
                # Blocking get dengan timeout agar bisa di-stop
                text_line = self.outgoing_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if not self._serial or not self._serial.is_open:
                # Re-queue packet dan coba reconnect
                try:
                    self.outgoing_queue.put_nowait(text_line)
                except queue.Full:
                    pass
                if not self.reconnect():
                    continue

            try:
                with self._lock:
                    packet = text_line + "\n"
                    self._serial.write(packet.encode("ascii"))
                    self._serial.flush()
            except serial.SerialException as e:
                log.error(f"UART TX error: {e}")
                self._serial = None
                # Re-queue packet
                try:
                    self.outgoing_queue.put_nowait(text_line)
                except queue.Full:
                    pass
                time.sleep(0.5)
            except Exception as e:
                log.error(f"TX unexpected error: {e}")
                time.sleep(0.1)
