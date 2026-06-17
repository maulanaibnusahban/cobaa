from protocol.packet_types import (
    PKT_TELEMETRY, PKT_FIRE_EVENT, PKT_IMAGE_START, PKT_IMAGE_DATA,
    PKT_IMAGE_END, PKT_ARM, PKT_DISARM, PKT_MODE,
    PKT_MISSION_UPLOAD, PKT_MISSION_START, PKT_MISSION_CLEAR,
    PKT_ACK_FIRE, PKT_ACK_IMG, PKT_NACK_IMG,
    PKT_MISSION_ACK, PKT_MISSION_NACK, PKT_CMD_RESPONSE,
)
from utils.logger import get_logger

log = get_logger("PARSER")


def parse_line(line: str) -> tuple:
    """
    Parse satu baris text packet.

    Args:
        line: Raw text line (tanpa \\n trailing)

    Returns:
        tuple (packet_type: str, data: dict)
        Jika parsing gagal, returns ("UNKNOWN", {"raw": line})
    """
    line = line.strip()
    if not line:
        return ("UNKNOWN", {"raw": ""})

    parts = line.split(",")
    pkt_type = parts[0].upper()

    try:
        # ── TELEMETRY ──────────────────────────────────────────────
        if pkt_type == PKT_TELEMETRY and len(parts) == 17:
            return (PKT_TELEMETRY, {
                "roll":        float(parts[1]),
                "pitch":       float(parts[2]),
                "yaw":         float(parts[3]),
                "lat":         float(parts[4]),
                "lon":         float(parts[5]),
                "alt":         float(parts[6]),
                "rel_alt":     float(parts[7]),
                "vx":          float(parts[8]),
                "vy":          float(parts[9]),
                "vz":          float(parts[10]),
                "gps_fix":     int(parts[11]),
                "satellites":  int(parts[12]),
                "battery":     float(parts[13]),
                "battery_pct": int(parts[14]),
                "armed":       int(parts[15]),
                "mode":        int(parts[16]),
            })

        # ── FIRE EVENT ─────────────────────────────────────────────
        if pkt_type == PKT_FIRE_EVENT and len(parts) == 5:
            return (PKT_FIRE_EVENT, {
                "event_id": int(parts[1]),
                "lat":      float(parts[2]),
                "lon":      float(parts[3]),
                "alt":      float(parts[4]),
            })

        # ── ACK_FIRE ───────────────────────────────────────────────
        if pkt_type == PKT_ACK_FIRE and len(parts) == 2:
            return (PKT_ACK_FIRE, {
                "event_id": int(parts[1]),
            })

        # ── IMAGE START ────────────────────────────────────────────
        if pkt_type == PKT_IMAGE_START and len(parts) == 4:
            return (PKT_IMAGE_START, {
                "image_id":     int(parts[1]),
                "total_packets": int(parts[2]),
                "image_size":   int(parts[3]),
            })

        # ── IMAGE DATA ─────────────────────────────────────────────
        if pkt_type == PKT_IMAGE_DATA and len(parts) == 5:
            return (PKT_IMAGE_DATA, {
                "image_id": int(parts[1]),
                "seq":      int(parts[2]),
                "total":    int(parts[3]),
                "data":     parts[4],  # base64 encoded
            })

        # ── IMAGE END ──────────────────────────────────────────────
        if pkt_type == PKT_IMAGE_END and len(parts) == 2:
            return (PKT_IMAGE_END, {
                "image_id": int(parts[1]),
            })

        # ── ACK_IMG ────────────────────────────────────────────────
        if pkt_type == PKT_ACK_IMG and len(parts) == 3:
            return (PKT_ACK_IMG, {
                "image_id": int(parts[1]),
                "seq":      int(parts[2]),
            })

        # ── NACK_IMG ───────────────────────────────────────────────
        if pkt_type == PKT_NACK_IMG and len(parts) == 3:
            return (PKT_NACK_IMG, {
                "image_id": int(parts[1]),
                "seq":      int(parts[2]),
            })

        # ── ARM ────────────────────────────────────────────────────
        if pkt_type == PKT_ARM:
            return (PKT_ARM, {})

        # ── DISARM ─────────────────────────────────────────────────
        if pkt_type == PKT_DISARM:
            return (PKT_DISARM, {})

        # ── MODE ───────────────────────────────────────────────────
        if pkt_type == PKT_MODE and len(parts) == 2:
            return (PKT_MODE, {
                "mode": int(parts[1]),
            })

        # ── MISSION UPLOAD ─────────────────────────────────────────
        if pkt_type == PKT_MISSION_UPLOAD and len(parts) == 8:
            return (PKT_MISSION_UPLOAD, {
                "seq":    int(parts[1]),
                "action": int(parts[2]),
                "lat":    float(parts[3]),
                "lon":    float(parts[4]),
                "alt":    float(parts[5]),
                "param1": float(parts[6]),
                "param2": float(parts[7]),
            })

        # ── MISSION ACK ────────────────────────────────────────────
        if pkt_type == PKT_MISSION_ACK and len(parts) == 2:
            return (PKT_MISSION_ACK, {
                "seq": int(parts[1]),
            })

        # ── MISSION NACK ───────────────────────────────────────────
        if pkt_type == PKT_MISSION_NACK and len(parts) == 2:
            return (PKT_MISSION_NACK, {
                "seq": int(parts[1]),
            })

        # ── MISSION START ──────────────────────────────────────────
        if pkt_type == PKT_MISSION_START:
            return (PKT_MISSION_START, {})

        # ── MISSION CLEAR ──────────────────────────────────────────
        if pkt_type == PKT_MISSION_CLEAR:
            return (PKT_MISSION_CLEAR, {})

        # ── CMD RESPONSE ───────────────────────────────────────────
        if pkt_type == PKT_CMD_RESPONSE and len(parts) >= 2:
            return (PKT_CMD_RESPONSE, {
                "message": ",".join(parts[1:]),
            })

    except (ValueError, IndexError) as e:
        log.warning(f"Parse error: {e} | raw: {line}")

    return ("UNKNOWN", {"raw": line})


def build_telemetry_packet(telem: dict) -> str:
    """
    Format telemetry data menjadi text packet.

    Args:
        telem: dict dengan semua field telemetry

    Returns:
        String format: TEL,roll,pitch,...,mode\\n
    """
    return (
        f"TEL,"
        f"{telem.get('roll', 0.0):.2f},"
        f"{telem.get('pitch', 0.0):.2f},"
        f"{telem.get('yaw', 0.0):.2f},"
        f"{telem.get('lat', 0.0):.6f},"
        f"{telem.get('lon', 0.0):.6f},"
        f"{telem.get('alt', 0.0):.2f},"
        f"{telem.get('rel_alt', 0.0):.2f},"
        f"{telem.get('vx', 0.0):.2f},"
        f"{telem.get('vy', 0.0):.2f},"
        f"{telem.get('vz', 0.0):.2f},"
        f"{telem.get('gps_fix', 0)},"
        f"{telem.get('satellites', 0)},"
        f"{telem.get('battery', 0.0):.2f},"
        f"{telem.get('battery_pct', 0)},"
        f"{telem.get('armed', 0)},"
        f"{telem.get('mode', 255)}"
    )


def build_fire_event_packet(event_id: int, lat: float, lon: float, alt: float) -> str:
    """Format: FIRE,event_id,lat,lon,alt"""
    return f"FIRE,{event_id},{lat:.6f},{lon:.6f},{alt:.2f}"


def build_image_start_packet(image_id: int, total_packets: int, image_size: int) -> str:
    """Format: IMG_START,image_id,total_packets,image_size"""
    return f"IMG_START,{image_id},{total_packets},{image_size}"


def build_image_data_packet(image_id: int, seq: int, total: int, b64_data: str) -> str:
    """Format: IMG,image_id,seq,total,base64_data"""
    return f"IMG,{image_id},{seq},{total},{b64_data}"


def build_image_end_packet(image_id: int) -> str:
    """Format: IMG_END,image_id"""
    return f"IMG_END,{image_id}"


def build_mission_ack_packet(seq: int) -> str:
    """Format: MISSION_ACK,seq"""
    return f"MISSION_ACK,{seq}"


def build_mission_nack_packet(seq: int) -> str:
    """Format: MISSION_NACK,seq"""
    return f"MISSION_NACK,{seq}"


def build_cmd_response_packet(message: str) -> str:
    """Format: CMD_RESP,message"""
    return f"CMD_RESP,{message}"
