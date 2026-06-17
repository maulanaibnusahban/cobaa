import threading
import time

from pixhawk.mavlink_client import MAVLinkClient
from services.gateway_service import GatewayService
from state.shared_state import SharedState
from protocol.parser import build_cmd_response_packet
from protocol.packet_types import (
    PKT_ARM, PKT_DISARM, PKT_MODE, PKT_ACK_FIRE,
    PKT_MISSION_UPLOAD, PKT_MISSION_START, PKT_MISSION_CLEAR
)
from utils.logger import get_logger

log = get_logger("COMMAND")


class CommandService:
    def __init__(
        self,
        mavlink_client: MAVLinkClient,
        gateway: GatewayService,
        state: SharedState,
        mission_service, # Dihindari circular import type hint
    ):
        self._mav = mavlink_client
        self._gateway = gateway
        self._state = state
        self._mission_service = mission_service
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="Command", daemon=True
        )
        self._thread.start()
        log.info("Command service started")

    def stop(self):
        self._running = False
        log.info("Command service stopped")

    def _run(self):
        """Loop membaca dan mengeksekusi packet."""
        while self._running:
            try:
                # Blokir sebentar menunggu item, agar bisa di stop
                pkt_type, pkt_data = self._gateway.incoming_queue.get(timeout=0.1)
                self._process_packet(pkt_type, pkt_data)
            except Exception as e:
                # queue.Empty adalah wajar karena timeout=0.1
                import queue
                if not isinstance(e, queue.Empty):
                    log.error(f"Error process command: {e}")

    def _process_packet(self, pkt_type: str, pkt_data: dict):
        """Routing packet ke handler yang sesuai."""
        log.info(f"Rx Packet: {pkt_type} | Data: {pkt_data}")

        # ── ARM / DISARM ───────────────────────────────────────────
        if pkt_type == PKT_ARM:
            ok = self._mav.arm()
            self._reply_cmd("ARM", ok)

        elif pkt_type == PKT_DISARM:
            ok = self._mav.disarm()
            self._reply_cmd("DISARM", ok)

        # ── MODE ───────────────────────────────────────────────────
        elif pkt_type == PKT_MODE:
            mode_int = pkt_data.get("mode", 255)
            ok = self._mav.set_mode(mode_int)
            self._reply_cmd(f"MODE_{mode_int}", ok)

        # ── ACK FIRE ───────────────────────────────────────────────
        elif pkt_type == PKT_ACK_FIRE:
            ev_id = pkt_data.get("event_id", 0)
            cur_ev = self._state.get_fire_event()
            if cur_ev["event_id"] == ev_id:
                self._state.update_fire_event(ack_received=True)
                log.info(f"Set ACK_FIRE flag True untuk event_id {ev_id}")

        # ── MISSION UPLOAD ─────────────────────────────────────────
        elif pkt_type == PKT_MISSION_UPLOAD:
            # Diteruskan ke mission service untuk dibuffer
            self._mission_service.handle_mission_upload(pkt_data)

        # ── MISSION CLEAR ──────────────────────────────────────────
        elif pkt_type == PKT_MISSION_CLEAR:
            self._mission_service.handle_mission_clear()

        # ── MISSION START ──────────────────────────────────────────
        elif pkt_type == PKT_MISSION_START:
            self._mission_service.handle_mission_start()

        # ── UNKNOWN ATAU LAINNYA ───────────────────────────────────
        else:
            log.warning(f"Unhandled packet type: {pkt_type}")

    def _reply_cmd(self, cmd_name: str, success: bool):
        """Kirim CMD_RESP ke Ground Station."""
        status = "OK" if success else "FAIL"
        msg = f"{cmd_name}_{status}"
        resp = build_cmd_response_packet(msg)
        self._gateway.send_packet(resp)
