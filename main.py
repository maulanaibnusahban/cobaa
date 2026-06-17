
import sys
import time
import signal

from config.settings import LOG_LEVEL
from utils.logger import get_logger
from state.shared_state import SharedState
from pixhawk.mavlink_client import MAVLinkClient
from services.gateway_service import GatewayService
from services.telemetry_service import TelemetryService
from services.fire_detection_service import FireDetectionService
from services.fire_event_service import FireEventService
from services.command_service import CommandService
from services.mission_service import MissionService

log = get_logger("MAIN")


class UAVSystem:
    def __init__(self):
        log.info("══════════════════════════════════════════════════")
        log.info("      KRTI UAV System — Companion Computer        ")
        log.info("══════════════════════════════════════════════════")
        log.info(f"Log Level: {LOG_LEVEL}")

        # 1. State & Clients
        self.state = SharedState()
        self.mavlink = MAVLinkClient()
        self.gateway = GatewayService()

        # 2. Services
        self.telemetry_service = TelemetryService(
            mavlink_client=self.mavlink,
            gateway=self.gateway,
            state=self.state,
        )
        
        self.fire_detection_service = FireDetectionService(
            state=self.state,
        )
        
        self.fire_event_service = FireEventService(
            state=self.state,
            gateway=self.gateway,
        )
        
        self.mission_service = MissionService(
            mavlink_client=self.mavlink,
            gateway=self.gateway,
            state=self.state,
        )
        
        # Command service butuh reference ke mission_service
        self.command_service = CommandService(
            mavlink_client=self.mavlink,
            gateway=self.gateway,
            state=self.state,
            mission_service=self.mission_service,
        )

        # Flag running
        self._running = False

    def start(self):
        """Start seluruh sistem."""
        self._running = True
        
        # Tangkap sinyal terminasi untuk graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Connect MAVLink (blocking sampai terhubung)
        if not self.mavlink.connect():
            log.warning("Sistem berjalan TANPA koneksi Pixhawk.")

        # Connect UART Gateway
        if not self.gateway.connect():
            log.warning("Sistem berjalan TANPA koneksi ESP32 Gateway.")

        # Start Services
        log.info("Menjalankan semua background services...")
        self.gateway.start()
        self.telemetry_service.start()
        self.fire_detection_service.start()
        self.fire_event_service.start()
        self.command_service.start()

        log.info("Sistem UAV Siap!")

        # Main thread sleep loop
        try:
            while self._running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Graceful shutdown semua service."""
        if not self._running:
            return
            
        log.info("\nMematikan sistem UAV...")
        self._running = False
        
        self.command_service.stop()
        self.fire_event_service.stop()
        self.fire_detection_service.stop()
        self.telemetry_service.stop()
        self.gateway.stop()
        
        log.info("Shutdown selesai.")
        sys.exit(0)

    def _signal_handler(self, sig, frame):
        log.info(f"Signal {sig} diterima.")
        self.stop()


if __name__ == "__main__":
    system = UAVSystem()
    system.start()
