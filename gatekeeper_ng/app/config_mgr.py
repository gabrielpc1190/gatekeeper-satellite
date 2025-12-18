import json
import os
import shutil
import logging

class ConfigManager:
    def __init__(self, base_path, legacy_path=None):
        self.base_path = base_path
        self.config_dir = os.path.join(base_path, 'config')
        self.legacy_path = legacy_path
        self.logger = logging.getLogger("ConfigMgr")
        
        # Thread safety lock for file operations
        import threading
        self.lock = threading.Lock()
        
        # Ensure config dir exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.devices_file = os.path.join(self.config_dir, 'devices.json')
        self.devices_file = os.path.join(self.config_dir, 'devices.json')
        self.mqtt_file = os.path.join(self.config_dir, 'mqtt.json')
        self.settings_file = os.path.join(self.config_dir, 'settings.json')
        self.satellites_file = os.path.join(self.config_dir, 'satellites.json')
        
    def load_devices(self):
        if not os.path.exists(self.devices_file) and self.legacy_path:
            self._migrate_devices()
            
        if os.path.exists(self.devices_file):
            try:
                with self.lock:
                    with open(self.devices_file, 'r') as f:
                        return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading devices.json: {e}")
                return []
        return []

    def save_devices(self, devices):
        try:
            with self.lock:
                with open(self.devices_file, 'w') as f:
                    json.dump(devices, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving devices.json: {e}")

    def load_mqtt(self):
        # Default MQTT config
        defaults = {
            "broker": "localhost",
            "port": 1883,
            "user": "",
            "password": "",
            "topic_prefix": "gatekeeper"
        }
        
        if not os.path.exists(self.mqtt_file) and self.legacy_path:
            self._migrate_mqtt()
            
        if os.path.exists(self.mqtt_file):
            try:
                with open(self.mqtt_file, 'r') as f:
                    loaded = json.load(f)
                    defaults.update(loaded)
                    return defaults
            except Exception as e:
                self.logger.error(f"Error loading mqtt.json: {e}")
                
        return defaults

    def load_settings(self):
        defaults = {
            "PREF_INTER_SCAN_DELAY": "60",
            "PREF_ARRIVAL_SCAN_ATTEMPTS": "1",
            "PREF_DEPART_SCAN_ATTEMPTS": "2",
            "PREF_FAIL_OBSERVATION_TO_DEPART": "1",
            "PREF_BEACON_EXPIRATION": "60", # Default 60s
            "PREF_DEVICE_TRACKER_REPORT": "true",
            "PREF_ENABLE_LOGGING": "false"
        }
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    defaults.update(json.load(f))
            except Exception as e:
                self.logger.error(f"Error loading settings.json: {e}")
        return defaults

    def save_settings(self, settings):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving settings.json: {e}")

        except Exception as e:
            self.logger.error(f"Error saving settings.json: {e}")

    def load_satellites(self):
        # Returns id -> {room, name...}
        if os.path.exists(self.satellites_file):
            try:
                with self.lock:
                    with open(self.satellites_file, 'r') as f:
                        return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading satellites.json: {e}")
        return {}

    def save_satellites(self, data):
        try:
            with self.lock:
                with open(self.satellites_file, 'w') as f:
                    json.dump(data, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving satellites.json: {e}")

    def _migrate_devices(self):
        legacy_file = os.path.join(self.legacy_path, 'monitor', 'known_static_addresses')
        if not os.path.exists(legacy_file):
            return
            
        self.logger.info(f"Migrating devices from {legacy_file}")
        devices = []
        try:
            with open(legacy_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    # Parse: MAC ALIAS # TYPE
                    parts = line.split('#', 1)
                    main_part = parts[0].strip().split()
                    
                    if len(main_part) >= 1:
                        mac = main_part[0].upper()
                        alias = main_part[1] if len(main_part) > 1 else mac
                        dev_type = parts[1].strip() if len(parts) > 1 else 'Bluetooth'
                        
                        devices.append({
                            'mac': mac,
                            'alias': alias,
                            'type': dev_type
                        })
            
            self.save_devices(devices)
            
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")

    def _migrate_mqtt(self):
        legacy_file = os.path.join(self.legacy_path, 'monitor', 'mqtt_preferences')
        if not os.path.exists(legacy_file):
            return
            
        self.logger.info(f"Migrating MQTT from {legacy_file}")
        config = {}
        try:
            with open(legacy_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip() == 'mqtt_address': config['broker'] = v.strip()
                        if k.strip() == 'mqtt_port': config['port'] = int(v.strip())
                        if k.strip() == 'mqtt_user': config['user'] = v.strip()
                        if k.strip() == 'mqtt_password': config['password'] = v.strip()
                        if k.strip() == 'mqtt_topicpath': config['topic_prefix'] = v.strip()
            
            with open(self.mqtt_file, 'w') as f:
                json.dump(config, f, indent=4)
                
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
