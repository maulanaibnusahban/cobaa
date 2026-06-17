import threading
import time

from config.settings import TELEMETRY_INTERVAL_MS
from pixhawk.mavlink_client import MAVLinkClient
from services.gateway_service import GatewayService
from state.shared_state import SharedState
from protocol.parser import build_telemetry_packet
from utils.logger import get_logger

log = get_logger("TELEMETRY")


class TelemetryService:
    """
    Service telemetry — berjalan sebagai thread terpisah.

    Dua tugas utama:
    1. Baca MAVLink messages → update shared state
    2. Setiap TELEMETRY_INTERVAL_MS, format dan kirim ke ground
    """

    def __init__(
        self,
        mavlink_client: MAVLinkClient,
        gateway: GatewayService,
        state: SharedState,
    ):
        self._mav = mavlink_client
        self._gateway = gateway
        self._state = state
        self._running = False
        self._thread = None

    def start(self):
        """Start telemetry thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="Telemetry", daemon=True
        )
        self._thread.start()
        log.info("Telemetry service started")

    def stop(self):
        """Stop telemetry thread."""
        self._running = False
        log.info("Telemetry service stopped")

    def _run(self):
        """Main loop — baca MAVLink dan kirim telemetry periodik."""
        last_send = time.time()
        interval_sec = TELEMETRY_INTERVAL_MS / 1000.0

        while self._running:
            # ── 1. Baca MAVLink message (non-blocking) ─────────────
            if not self._mav.connected:
                log.warning("MAVLink disconnected, attempting reconnect...")
                if not self._mav.reconnect():
                    time.sleep(1)
                    continue

            msg = self._mav.recv_message(blocking=True, timeout=0.05)

            if msg is not None:
                msg_type = msg.get_type()

                if msg_type == "ATTITUDE":
                    data = self._mav.parse_attitude(msg)
                    self._state.update_telemetry(data)

                elif msg_type == "GLOBAL_POSITION_INT":
                    data = self._mav.parse_global_position(msg)
                    self._state.update_telemetry(data)

                elif msg_type == "GPS_RAW_INT":
                    data = self._mav.parse_gps_raw(msg)
                    self._state.update_telemetry(data)

                elif msg_type == "SYS_STATUS":
                    data = self._mav.parse_sys_status(msg)
                    self._state.update_telemetry(data)

                elif msg_type == "HEARTBEAT":
                    # Filter hanya heartbeat dari vehicle, bukan GCS
                    if msg.get_srcSystem() != 255:
                        data = self._mav.parse_heartbeat(msg)
                        self._state.update_telemetry(data)
                        self._state.update_vehicle_status(
                            armed=bool(data["armed"]),
                            mode=data["mode"],
                            connected=True,
                        )

            # ── 2. Kirim telemetry ke ground setiap interval ───────
            now = time.time()
            if now - last_send >= interval_sec:
                telem = self._state.get_telemetry()
                packet = build_telemetry_packet(telem)
                self._gateway.send_packet(packet)
                last_send = now

                log.debug(
                    f"TEL → lat={telem['lat']:.6f} lon={telem['lon']:.6f} "
                    f"alt={telem['rel_alt']:.1f}m mode={telem['mode']} "
                    f"armed={telem['armed']}"
                )
