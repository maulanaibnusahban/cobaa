
# PIXHAWK / MAVLINK
PIXHAWK_PORT = "/dev/ttyACM0"
PIXHAWK_BAUDRATE = 57600
MAVLINK_DATA_RATE = 10          # Hz — request data stream rate
MAVLINK_HEARTBEAT_TIMEOUT = 5   # detik — timeout waiting heartbeat
MAVLINK_RECONNECT_DELAY = 3     # detik — delay sebelum reconnect

# ESP32 DRONE GATEWAY (UART)
ESP_PORT = "/dev/ttyAMA0"
ESP_BAUDRATE = 115200
UART_RECONNECT_DELAY = 2        # detik — delay sebelum reconnect UART

# TELEMETRY
TELEMETRY_INTERVAL_MS = 450     # ms — interval kirim telemetry ke ground

# FIRE DETECTION
FIRE_MODEL_PATH = "fire_model.pt"
FIRE_CONFIDENCE_THRESHOLD = 0.70    # minimal confidence untuk trigger event
CAMERA_INDEX = 0                    # webcam index
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
INFERENCE_RESIZE_W = 640
INFERENCE_RESIZE_H = 480

# FIRE EVENT
IMAGE_COOLDOWN_SEC = 15         # detik — cooldown antar pengiriman gambar
FIRE_RESET_SEC = 10             # detik — durasi api hilang sebelum reset ke IDLE
FIRE_ACK_TIMEOUT_SEC = 5        # detik — timeout menunggu ACK_FIRE
FIRE_ACK_MAX_RETRY = 3          # max retry kirim FIRE metadata

# IMAGE TRANSMISSION
IMAGE_JPEG_QUALITY = 30         # kualitas JPEG compression
IMAGE_RESIZE_W = 160            # resolusi gambar untuk transmisi
IMAGE_RESIZE_H = 120
IMAGE_CHUNK_SIZE = 200          # bytes per chunk (sebelum base64 encoding)

# MISSION
MISSION_ACK_TIMEOUT_SEC = 3     # timeout ACK per waypoint
MISSION_MAX_RETRY = 3           # max retry per waypoint

# FLIGHT MODE ENUM
FLIGHT_MODE_MAP = {
    0: "STABILIZE",
    1: "GUIDED",
    2: "AUTO",
    3: "LOITER",
    4: "RTL",
    5: "LAND",
    6: "POSHOLD",
    7: "ALTHOLD",
    255: "UNKNOWN",
}

# ArduPilot mode string → integer kita
ARDUPILOT_MODE_TO_INT = {
    "STABILIZE": 0,
    "GUIDED":    1,
    "AUTO":      2,
    "LOITER":    3,
    "RTL":       4,
    "LAND":      5,
    "POSHOLD":   6,
    "ALT_HOLD":  7,
}

# Integer kita → ArduPilot mode string (untuk set_mode)
INT_TO_ARDUPILOT_MODE = {
    0: "STABILIZE",
    1: "GUIDED",
    2: "AUTO",
    3: "LOITER",
    4: "RTL",
    5: "LAND",
    6: "POSHOLD",
    7: "ALT_HOLD",
}

# MISSION ACTION ENUM
MISSION_ACTION_TAKEOFF       = 1
MISSION_ACTION_WAYPOINT      = 2
MISSION_ACTION_LOITER        = 3
MISSION_ACTION_RTL           = 4
MISSION_ACTION_LAND          = 5
MISSION_ACTION_IMAGE_CAPTURE = 6

# LOGGING
LOG_LEVEL = "INFO"              # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = False
LOG_FILE_PATH = "krti_uav.log"
