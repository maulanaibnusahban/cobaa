from dataclasses import dataclass, field
from typing import List
from config.settings import (
    MISSION_ACTION_TAKEOFF,
    MISSION_ACTION_WAYPOINT,
    MISSION_ACTION_LOITER,
    MISSION_ACTION_RTL,
    MISSION_ACTION_LAND,
    MISSION_ACTION_IMAGE_CAPTURE,
)


# ── Mission Action → Nama (untuk logging) ─────────────────────────
MISSION_ACTION_NAMES = {
    MISSION_ACTION_TAKEOFF:       "TAKEOFF",
    MISSION_ACTION_WAYPOINT:      "WAYPOINT",
    MISSION_ACTION_LOITER:        "LOITER",
    MISSION_ACTION_RTL:           "RTL",
    MISSION_ACTION_LAND:          "LAND",
    MISSION_ACTION_IMAGE_CAPTURE: "IMAGE_CAPTURE",
}


@dataclass
class MissionItem:
    """Satu item mission."""

    seq: int = 0                # Sequence number (0-based)
    action: int = 0             # Mission action enum
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    param1: float = 0.0        # Contoh: loiter time (detik)
    param2: float = 0.0        # Reserved

    @property
    def action_name(self) -> str:
        """Nama action untuk logging."""
        return MISSION_ACTION_NAMES.get(self.action, f"UNKNOWN({self.action})")

    def to_dict(self) -> dict:
        """Convert ke dictionary."""
        return {
            "seq": self.seq,
            "action": self.action,
            "lat": self.lat,
            "lon": self.lon,
            "alt": self.alt,
            "param1": self.param1,
            "param2": self.param2,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MissionItem":
        """Buat MissionItem dari dictionary (hasil parse protocol)."""
        return cls(
            seq=data.get("seq", 0),
            action=data.get("action", 0),
            lat=data.get("lat", 0.0),
            lon=data.get("lon", 0.0),
            alt=data.get("alt", 0.0),
            param1=data.get("param1", 0.0),
            param2=data.get("param2", 0.0),
        )


@dataclass
class Mission:
    """Kumpulan mission items."""

    items: List[MissionItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    def add_item(self, item: MissionItem):
        """Tambah mission item, auto-set seq."""
        item.seq = len(self.items)
        self.items.append(item)

    def clear(self):
        """Hapus semua items."""
        self.items.clear()

    def get_item(self, seq: int):
        """Ambil item berdasarkan seq number."""
        if 0 <= seq < len(self.items):
            return self.items[seq]
        return None
