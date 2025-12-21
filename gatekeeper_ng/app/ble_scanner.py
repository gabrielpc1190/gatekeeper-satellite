import struct
import socket
import asyncio
import logging
import time
import threading
import subprocess
import os

class BLEScanner:
    def __init__(self, device_id=0):
        self.device_id = device_id
        self.scanning = False
        self.logger = logging.getLogger("BLEScanner")
        self.callback = None
        self.discovered_devices = {}
        self.loop = asyncio.get_running_loop()
        self.thread = None
        self.proc = None

    def parse_hex_packet(self, hex_str):
        try:
            # hex_str is space-separated hex like "04 3E 21 02 01 ..."
            data = bytes.fromhex(hex_str.replace(" ", ""))
            if len(data) < 4: return
            
            # HCI Packet Type 0x04 (Event)
            if data[0] != 0x04: return
            
            # Event Code 0x3E (LE Meta Event)
            if data[1] != 0x3E: return
            
            # Subevent 0x02 (LE Advertising Report)
            if data[3] != 0x02: return
            
            self.parse_le_advertising_report(data[4:])
        except Exception as e:
            self.logger.debug(f"Parser error: {e}")

    def parse_le_advertising_report(self, data):
        try:
            num_reports = data[0]
            offset = 1
            for i in range(num_reports):
                if offset >= len(data): break
                event_type = data[offset]; offset += 2 # type and addr_type
                
                addr_bytes = data[offset:offset+6]
                offset += 6
                mac = ':'.join(f'{b:02X}' for b in reversed(addr_bytes))
                
                data_len = data[offset]; offset += 1
                payload = data[offset:offset+data_len]
                offset += data_len
                rssi = struct.unpack('b', data[offset:offset+1])[0]
                offset += 1
                
                name_str = None
                identifier = mac
                extra = {}
                p_offset = 0
                while p_offset < len(payload):
                    ad_len = payload[p_offset]
                    if ad_len == 0 or (p_offset + 1 + ad_len) > len(payload): break
                    ad_type = payload[p_offset + 1]
                    ad_data = payload[p_offset + 2 : p_offset + 1 + ad_len]
                    
                    if ad_type in [0x08, 0x09]:
                        try: name_str = ad_data.decode('utf-8')
                        except: pass
                    elif ad_type == 0xFF: # iBeacon
                        if len(ad_data) >= 25 and ad_data[0:3] == b'\x4c\x00\x02':
                            uuid_bytes = ad_data[4:20]
                            identifier = '-'.join([uuid_bytes[0:4].hex(), uuid_bytes[4:6].hex(), uuid_bytes[6:8].hex(), uuid_bytes[8:10].hex(), uuid_bytes[10:16].hex()]).upper()
                            extra = {'major': struct.unpack('>H', ad_data[20:22])[0], 'minor': struct.unpack('>H', ad_data[22:24])[0]}
                    p_offset += (ad_len + 1)

                record = {'mac': mac, 'identifier': identifier, 'rssi': rssi, 'name': name_str, 'extra': extra}
                if self.callback:
                    if asyncio.iscoroutinefunction(self.callback):
                        asyncio.run_coroutine_threadsafe(self.callback(record), self.loop)
                    else: self.callback(record)
                self.discovered_devices[mac] = {'mac': mac, 'name': name_str or "Unknown", 'rssi': rssi, 'last_seen': time.time()}
        except Exception as e:
            self.logger.debug(f"Adv Parse error: {e}")

    def get_recent_devices(self, seconds=30):
        """Returns a list of devices seen within the last X seconds."""
        now = time.time()
        results = []
        for mac, data in list(self.discovered_devices.items()):
            if now - data.get('last_seen', 0) < seconds:
                results.append(data)
        return results

    def _worker(self):
        self.logger.info("BLE hcidump Worker Started")
        current_packet = ""
        try:
            # hcidump -R output is multi-line. Packets start with "> " or "< ".
            # Indented lines are continuations of the same packet.
            for line in iter(self.proc.stdout.readline, b''):
                if not self.scanning: break
                line_str = line.decode('utf-8').rstrip()
                if not line_str: continue

                if line_str.startswith('> ') or line_str.startswith('< '):
                    # New packet starts. Process the old one first.
                    if current_packet:
                        self.parse_hex_packet(current_packet)
                    current_packet = line_str[2:]
                elif line_str.startswith('  '):
                    # Continuation line
                    current_packet += line_str.strip()
            
            # Final packet
            if current_packet:
                self.parse_hex_packet(current_packet)
                
        except Exception as e:
            if self.scanning: self.logger.error(f"Worker Loop Error: {e}")
        finally:
            self.logger.info("BLE hcidump Worker Stopped")

    async def scan_loop(self):
        self.logger.info("Starting hcidump-based BLE Scan Loop")
        hcitool_proc = None
        try:
            # 1. Start background scan to trigger hardware
            subprocess.run(["sudo", "hciconfig", f"hci{self.device_id}", "up"], check=False)
            hcitool_proc = subprocess.Popen(
                ["sudo", "hcitool", "lescan", "--duplicates", "--passive"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # 2. Start hcidump -R (Raw Hex)
            self.proc = subprocess.Popen(
                ["sudo", "hcidump", "-i", f"hci{self.device_id}", "-R"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            self.scanning = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()
            
            while self.scanning:
                # Check health of sub-processes
                if hcitool_proc.poll() is not None:
                    hcitool_proc = subprocess.Popen(["sudo", "hcitool", "lescan", "--duplicates", "--passive"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if self.proc.poll() is not None:
                    self.logger.error("hcidump died!")
                    break
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            self.logger.info("Scan loop task cancelled")
        except Exception as e:
            self.logger.error(f"Scan loop error: {e}")
        finally:
            self.scanning = False
            if hcitool_proc:
                hcitool_proc.terminate()
            if self.proc:
                self.proc.terminate()
