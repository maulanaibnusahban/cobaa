import math
import time
import threading
from pymavlink import mavutil

from config.settings import (
    PIXHAWK_PORT, PIXHAWK_BAUDRATE,
    MAVLINK_DATA_RATE, MAVLINK_HEARTBEAT_TIMEOUT,
    MAVLINK_RECONNECT_DELAY,
    ARDUPILOT_MODE_TO_INT, INT_TO_ARDUPILOT_MODE,
    MISSION_ACTION_TAKEOFF, MISSION_ACTION_WAYPOINT,
    MISSION_ACTION_LOITER, MISSION_ACTION_RTL,
    MISSION_ACTION_LAND, MISSION_ACTION_IMAGE_CAPTURE,
)
from utils.logger import get_logger

log = get_logger("MAVLINK")


class MAVLinkClient:
    """
    Thread-safe MAVLink client untuk Pixhawk.
    Semua operasi MAVLink melalui kelas ini.
    """

    def __init__(self):
        self._master = None
        self._lock = threading.Lock()
        self._connected = False

    # CONNECTION

    def connect(self) -> bool:
        """
        Hubungkan ke Pixhawk. Blocking sampai heartbeat diterima.
        Returns True jika berhasil.
        """
        with self._lock:
            try:
                log.info(f"Menghubungkan ke Pixhawk: {PIXHAWK_PORT} @ {PIXHAWK_BAUDRATE}")
                self._master = mavutil.mavlink_connection(
                    PIXHAWK_PORT, baud=PIXHAWK_BAUDRATE
                )
                self._master.wait_heartbeat(timeout=MAVLINK_HEARTBEAT_TIMEOUT)
                log.info(
                    f"Terhubung! System ID: {self._master.target_system}, "
                    f"Component: {self._master.target_component}"
                )

                # Request semua data stream
                self._master.mav.request_data_stream_send(
                    self._master.target_system,
                    self._master.target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    MAVLINK_DATA_RATE,
                    1  # start
                )
                log.info(f"Data stream requested @ {MAVLINK_DATA_RATE} Hz")

                self._connected = True
                return True

            except Exception as e:
                log.error(f"Gagal terhubung ke Pixhawk: {e}")
                self._master = None
                self._connected = False
                return False

    def reconnect(self) -> bool:
        """Reconnect ke Pixhawk dengan delay."""
        log.warning(f"Reconnecting dalam {MAVLINK_RECONNECT_DELAY}s...")
        time.sleep(MAVLINK_RECONNECT_DELAY)
        return self.connect()

    @property
    def connected(self) -> bool:
        return self._connected

    # TELEMETRY READING (Non-blocking)

    def recv_message(self, blocking=False, timeout=0.1):
        """
        Baca satu MAVLink message.
        Returns message object atau None.
        """
        if not self._master:
            return None

        try:
            msg = self._master.recv_match(blocking=blocking, timeout=timeout)
            return msg
        except Exception as e:
            log.error(f"Error baca MAVLink: {e}")
            self._connected = False
            return None

    def parse_attitude(self, msg) -> dict:
        """Parse ATTITUDE message → roll/pitch/yaw dalam derajat."""
        return {
            "roll":  round(math.degrees(msg.roll), 2),
            "pitch": round(math.degrees(msg.pitch), 2),
            "yaw":   round(math.degrees(msg.yaw), 2),
        }

    def parse_global_position(self, msg) -> dict:
        """Parse GLOBAL_POSITION_INT → lat/lon/alt/vel."""
        return {
            "lat":     msg.lat / 1e7,
            "lon":     msg.lon / 1e7,
            "alt":     msg.alt / 1000.0,
            "rel_alt": msg.relative_alt / 1000.0,
            "vx":      msg.vx / 100.0,     # cm/s → m/s
            "vy":      msg.vy / 100.0,
            "vz":      msg.vz / 100.0,
        }

    def parse_gps_raw(self, msg) -> dict:
        """Parse GPS_RAW_INT → fix type, satellites."""
        return {
            "gps_fix":    msg.fix_type,
            "satellites": msg.satellites_visible,
        }

    def parse_sys_status(self, msg) -> dict:
        """Parse SYS_STATUS → battery voltage, percentage."""
        pct = msg.battery_remaining
        return {
            "battery":     msg.voltage_battery / 1000.0,    # mV → V
            "battery_pct": pct if pct >= 0 else 0,
        }

    def parse_heartbeat(self, msg) -> dict:
        """Parse HEARTBEAT → armed status, flight mode."""
        armed = int(
            (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
        )

        # Konversi mode string ArduPilot ke integer kita
        mode_str = mavutil.mode_string_v10(msg)
        if mode_str:
            mode_int = ARDUPILOT_MODE_TO_INT.get(mode_str.upper(), 255)
        else:
            mode_int = 255

        return {
            "armed": armed,
            "mode":  mode_int,
        }

    # COMMANDS

    def arm(self) -> bool:
        """ARM vehicle."""
        if not self._master:
            return False
        try:
            with self._lock:
                self._master.mav.command_long_send(
                    self._master.target_system,
                    self._master.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,
                    1,  # 1 = ARM
                    0, 0, 0, 0, 0, 0
                )
            log.info("→ ARM command sent")
            return True
        except Exception as e:
            log.error(f"ARM failed: {e}")
            return False

    def disarm(self) -> bool:
        """DISARM vehicle."""
        if not self._master:
            return False
        try:
            with self._lock:
                self._master.mav.command_long_send(
                    self._master.target_system,
                    self._master.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,
                    0,  # 0 = DISARM
                    0, 0, 0, 0, 0, 0
                )
            log.info("→ DISARM command sent")
            return True
        except Exception as e:
            log.error(f"DISARM failed: {e}")
            return False

    def set_mode(self, mode_int: int) -> bool:
        """
        Set flight mode menggunakan integer dari protocol.
        Konversi ke ArduPilot mode string lalu set.
        """
        if not self._master:
            return False

        mode_str = INT_TO_ARDUPILOT_MODE.get(mode_int)
        if mode_str is None:
            log.error(f"Unknown mode integer: {mode_int}")
            return False

        try:
            with self._lock:
                self._master.set_mode(mode_str)
            log.info(f"→ Set Mode: {mode_str} (int={mode_int})")
            return True
        except Exception as e:
            log.error(f"Set mode failed: {e}")
            return False

    def takeoff(self, altitude: float) -> bool:
        """
        Takeoff ke altitude tertentu.
        Memerlukan mode GUIDED.
        """
        if not self._master:
            return False
        try:
            with self._lock:
                # Set GUIDED dulu
                self._master.set_mode("GUIDED")
                log.info("→ Set Mode: GUIDED (persiapan takeoff)")
                time.sleep(0.5)

                self._master.mav.command_long_send(
                    self._master.target_system,
                    self._master.target_component,
                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                    0,
                    0, 0, 0, 0, 0, 0,
                    altitude
                )
            log.info(f"→ TAKEOFF command sent (alt={altitude}m)")
            return True
        except Exception as e:
            log.error(f"TAKEOFF failed: {e}")
            return False

    # MISSION UPLOAD (MAVLink Mission Protocol)

    def clear_mission(self) -> bool:
        """Clear semua mission items di Pixhawk."""
        if not self._master:
            return False
        try:
            with self._lock:
                self._master.mav.mission_clear_all_send(
                    self._master.target_system,
                    self._master.target_component
                )
            log.info("→ Mission cleared")
            return True
        except Exception as e:
            log.error(f"Mission clear failed: {e}")
            return False

    def upload_mission(self, items: list) -> bool:
        """
        Upload mission ke Pixhawk menggunakan MAVLink mission protocol.

        Args:
            items: List of MissionItem objects

        Returns:
            True jika berhasil
        """
        if not self._master or len(items) == 0:
            return False

        try:
            with self._lock:
                # 1. Send MISSION_COUNT
                self._master.mav.mission_count_send(
                    self._master.target_system,
                    self._master.target_component,
                    len(items)
                )
                log.info(f"→ Mission count: {len(items)}")

                # 2. Untuk setiap item, tunggu MISSION_REQUEST lalu kirim MISSION_ITEM
                for item in items:
                    # Tunggu request dari Pixhawk
                    msg = self._master.recv_match(
                        type="MISSION_REQUEST", blocking=True, timeout=5
                    )
                    if msg is None:
                        log.error(f"Timeout waiting MISSION_REQUEST seq={item.seq}")
                        return False

                    # Map action ke MAVLink command
                    mav_cmd = self._action_to_mav_cmd(item.action)
                    frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT

                    # Kirim mission item
                    self._master.mav.mission_item_send(
                        self._master.target_system,
                        self._master.target_component,
                        item.seq,               # seq
                        frame,                  # frame
                        mav_cmd,                # command
                        0,                      # current
                        1,                      # autocontinue
                        item.param1,            # param1
                        item.param2,            # param2
                        0,                      # param3
                        0,                      # param4
                        item.lat,               # x (lat)
                        item.lon,               # y (lon)
                        item.alt,               # z (alt)
                    )
                    log.info(
                        f"→ Mission item {item.seq}: {item.action_name} "
                        f"({item.lat:.6f}, {item.lon:.6f}, {item.alt:.1f}m)"
                    )

                # 3. Tunggu MISSION_ACK
                ack = self._master.recv_match(
                    type="MISSION_ACK", blocking=True, timeout=5
                )
                if ack is None:
                    log.error("Timeout waiting MISSION_ACK")
                    return False

                if ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    log.info("✓ Mission upload ACCEPTED")
                    return True
                else:
                    log.error(f"Mission upload REJECTED: type={ack.type}")
                    return False

        except Exception as e:
            log.error(f"Mission upload failed: {e}")
            return False

    def start_mission(self) -> bool:
        """Set mode AUTO untuk mulai mission."""
        return self.set_mode(2)  # 2 = AUTO

    def _action_to_mav_cmd(self, action: int) -> int:
        """Map mission action enum ke MAVLink command."""
        mapping = {
            MISSION_ACTION_TAKEOFF:       mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            MISSION_ACTION_WAYPOINT:      mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            MISSION_ACTION_LOITER:        mavutil.mavlink.MAV_CMD_NAV_LOITER_TIME,
            MISSION_ACTION_RTL:           mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            MISSION_ACTION_LAND:          mavutil.mavlink.MAV_CMD_NAV_LAND,
            MISSION_ACTION_IMAGE_CAPTURE: mavutil.mavlink.MAV_CMD_IMAGE_START_CAPTURE,
        }
        return mapping.get(action, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT)

    # FEEDBACK (Non-blocking)

    def recv_command_ack(self):
        """Read COMMAND_ACK message (non-blocking)."""
        if not self._master:
            return None
        try:
            msg = self._master.recv_match(
                type="COMMAND_ACK", blocking=False
            )
            return msg
        except Exception:
            return None
