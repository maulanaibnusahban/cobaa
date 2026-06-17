import threading

from pixhawk.mavlink_client import MAVLinkClient
from services.gateway_service import GatewayService
from state.shared_state import SharedState
from models.mission import Mission, MissionItem
from protocol.parser import build_mission_ack_packet, build_cmd_response_packet
from utils.logger import get_logger

log = get_logger("MISSION")


class MissionService:
    """
    Manajer Misi.
    Berbeda dengan service lain, class ini tidak memiliki thread loop sendiri.
    Method-nya dipanggil oleh CommandService dari dalam thread command.
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
        
        self._mission_buffer = Mission()

    # COMMAND HANDLERS (Dipanggil dari CommandService)

    def handle_mission_upload(self, data: dict):
        """
        Terima satu waypoint dari Ground.
        Format: seq, action, lat, lon, alt, param1, param2
        
        Strategi:
        - Jika seq == 0, reset buffer dan mulai misi baru.
        - Jika seq > 0, append ke buffer.
        - ACK setiap paket.
        - Kita tunggu beberapa saat tanpa paket baru, lalu trigger commit 
          (atau bisa menggunakan command eksplisit COMMIT, tapi karena 
          protokol awal tidak ada COMMIT, kita bisa anggap 
          kita buffer dulu, lalu pas MISSION_START di-upload).
          Atau upload bisa dilakukan secara periodik, 
          atau paling benar: karena protokol mission uploader biasanya 
          membutuhkan total count di awal (yang tidak dikirim dari ESP32 ground 
          di protokol yang ada), kita harus buffer semuanya lalu 
          saat GROUND mengirim "MISSION_START", kita upload semua buffer 
          ke Pixhawk, LALU baru auto mode.
        """
        seq = data.get("seq", 0)
        
        # Reset jika seq 0
        if seq == 0:
            log.info("Mulai terima misi baru (seq=0). Resetting buffer.")
            self._mission_buffer.clear()
            self._state.clear_mission_items()
            self._state.update_mission_status(state="UPLOADING")

        # Buat objek item
        item = MissionItem.from_dict(data)
        
        # Override seq sesuai buffer kita untuk keamanan
        self._mission_buffer.add_item(item)
        self._state.add_mission_item(item.to_dict())
        
        log.info(f"Buffered Mission Item {item.seq}: {item.action_name}")

        # Kirim ACK
        ack_pkt = build_mission_ack_packet(item.seq)
        self._gateway.send_packet(ack_pkt)

    def handle_mission_clear(self):
        """Hapus semua mission."""
        log.info("Membersihkan misi (Mission Clear)")
        self._mission_buffer.clear()
        self._state.clear_mission_items()
        
        ok = self._mav.clear_mission()
        
        status = "OK" if ok else "FAIL"
        resp = build_cmd_response_packet(f"MISSION_CLEAR_{status}")
        self._gateway.send_packet(resp)

    def handle_mission_start(self):
        """
        1. Upload buffered mission ke Pixhawk
        2. Set mode ke AUTO
        """
        log.info("Menerima MISSION_START command")
        
        total = self._mission_buffer.count
        if total == 0:
            log.warning("MISSION_START tapi buffer kosong!")
            resp = build_cmd_response_packet("MISSION_START_FAIL_EMPTY")
            self._gateway.send_packet(resp)
            return

        self._state.update_mission_status(state="UPLOADING_TO_PIXHAWK")
        
        # 1. Upload ke Pixhawk via thread background agar command loop tidak terblokir lama
        # Karena ini operasi synchronous dan bisa makan waktu beberapa detik
        upload_thread = threading.Thread(
            target=self._upload_and_start_task,
            name="MissionUpload"
        )
        upload_thread.start()

    def _upload_and_start_task(self):
        """Background task untuk upload ke Pixhawk lalu start."""
        total = self._mission_buffer.count
        log.info(f"Mengunggah {total} item misi ke Pixhawk...")
        
        ok = self._mav.upload_mission(self._mission_buffer.items)
        
        if ok:
            log.info("Upload misi ke Pixhawk berhasil. Mengaktifkan mode AUTO.")
            self._state.update_mission_status(state="UPLOADED", uploaded=total)
            
            # 2. Start Mission = mode AUTO
            started = self._mav.start_mission()
            
            if started:
                self._state.update_mission_status(state="RUNNING")
                resp = build_cmd_response_packet("MISSION_START_OK")
            else:
                resp = build_cmd_response_packet("MISSION_START_FAIL_MODE")
        else:
            log.error("Upload misi ke Pixhawk gagal.")
            self._state.update_mission_status(state="FAIL")
            resp = build_cmd_response_packet("MISSION_START_FAIL_UPLOAD")

        # Informasikan Ground Station
        self._gateway.send_packet(resp)
