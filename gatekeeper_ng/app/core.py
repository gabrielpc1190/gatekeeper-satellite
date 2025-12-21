import asyncio
import logging
import signal
from .ble_scanner import BLEScanner
from .config_mgr import ConfigManager
from .mqtt_client import MQTTClient
from .tracker import DeviceTracker
# Import Admin (Relative import based on package structure)
from admin.server import WebAdmin

class CoreService:
    def __init__(self, base_path, legacy_path):
        self.logger = logging.getLogger("Core")
        
        # Init Config
        self.config_mgr = ConfigManager(base_path, legacy_path)
        mqtt_conf = self.config_mgr.load_mqtt()
        
        # Init Components
        self.mqtt_client = MQTTClient(mqtt_conf)
        self.tracker = DeviceTracker(self.config_mgr, self.mqtt_client)
        self.scanner = BLEScanner(device_id=0)
        
        # Init Web Admin
        self.web_admin = WebAdmin(self.config_mgr, tracker=self.tracker, scanner=self.scanner)
        
        # Link callbacks
        self.scanner.callback = self.tracker.process_packet
        self.mqtt_client.satellite_callback = self.tracker.process_remote_packet

        self.running = False

    async def run(self):
        self.running = True
        
        # Start MQTT
        await self.mqtt_client.start()
        
        # Start Web Admin
        self.web_admin.start()
        
        # Send initial discovery
        devices = self.config_mgr.load_devices()
        await self.mqtt_client.publish_discovery(devices)
        
        # Start Tracker Loops
        maintenance_task = asyncio.create_task(self.tracker.maintenance_loop())
        
        # Force register Hub so it appears in UI immediately
        await self.tracker.process_remote_packet('gatekeeper-hub', '00:00:00:00:00:00', -100)
        
        # Start Scanner
        self.logger.info("Starting Service...")
        
        try:
            # Start Scanner Loop
            scanner_task = asyncio.create_task(self.scanner.scan_loop())
            
            # Application Main Loop
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info("Service stopping...")
        finally:
            self.running = False
            # Clean Shutdown
            maintenance_task.cancel()
            scanner_task.cancel()
            self.mqtt_client.stop()
            self.logger.info("Service Stopped.")
            
    def stop(self):
        self.running = False
        self.scanner.scanning = False

async def main_entry(base_path, legacy_path):
    # Setup Logging with more detailed format
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    
    # Silence noisy werkzeug logs (web server requests)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    
    service = CoreService(base_path, legacy_path)
    
    # Handle Signals
    loop = asyncio.get_running_loop()
    stop_signal = asyncio.Event()
    
    def signal_handler():
        service.stop()
        stop_signal.set()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
        
    # Run
    await service.run()
