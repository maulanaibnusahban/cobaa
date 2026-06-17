from dataclasses import dataclass, field
import time


class FireState:
    IDLE = "IDLE"
    FIRE_ACTIVE = "FIRE_ACTIVE"


@dataclass
class FireEvent:

    event_id: int = 0
    state: str = FireState.IDLE
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0

    # Timing
    detected_time: float = 0.0
    last_image_time: float = 0.0
    fire_lost_time: float = 0.0

    # ACK tracking
    ack_received: bool = False

    def to_dict(self) -> dict:
        """Convert ke dictionary untuk shared state."""
        return {
            "event_id": self.event_id,
            "state": self.state,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.alt,
            "timestamp": self.detected_time,
            "last_image_time": self.last_image_time,
            "fire_lost_time": self.fire_lost_time,
        }
