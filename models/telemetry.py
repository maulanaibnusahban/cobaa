from dataclasses import dataclass, field
import time


@dataclass
class TelemetryData:
    """Representasi data telemetry dari Pixhawk."""

    # Attitude (degrees)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0

    # Position
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0       # AMSL altitude (m)
    rel_alt: float = 0.0   # Relative altitude (m)

    # Velocity (m/s)
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0

    # GPS
    gps_fix: int = 0
    satellites: int = 0

    # Battery
    battery: float = 0.0       # Voltage (V)
    battery_pct: int = 0       # Percentage (0-100)

    # Status
    armed: int = 0             # 0 = disarmed, 1 = armed
    mode: int = 255            # Flight mode integer

    # Timestamp
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Convert ke dictionary untuk shared state."""
        return {
            "roll": self.roll,
            "pitch": self.pitch,
            "yaw": self.yaw,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.alt,
            "rel_alt": self.rel_alt,
            "vx": self.vx,
            "vy": self.vy,
            "vz": self.vz,
            "gps_fix": self.gps_fix,
            "satellites": self.satellites,
            "battery": self.battery,
            "battery_pct": self.battery_pct,
            "armed": self.armed,
            "mode": self.mode,
            "timestamp": self.timestamp,
        }
