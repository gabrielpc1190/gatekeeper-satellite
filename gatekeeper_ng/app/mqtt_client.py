import asyncio
import json
import logging
import socket
import uuid

# We'll use paho-mqtt but wrap it for asyncio-like usage or run in executor
# Since we don't know if paho-mqtt is installed, we should probably add it to requirements.
# For this code snippet, I'll write a wrapper assuming paho.mqtt.client is available.
# Standard paho-mqtt usage involves callbacks. 

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

class MQTTClient:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("MQTT")
        self.client = None
        self.connected = False
        self.satellite_callback = None # Function(room, mac, rssi)
        self.topic_prefix = config.get("topic_prefix", "monitor")
        self.identity = "gatekeeper" # Could be hostname
        self.loop = None  # Store reference to main event loop

    async def start(self):
        if not mqtt:
            self.logger.error("paho-mqtt library not found. MQTT disabled.")
            return

        # Store reference to the current event loop
        self.loop = asyncio.get_running_loop()
        
        # Unique ID to avoid collision if service restarts rapidly or zombies exist
        unique_suffix = str(uuid.uuid4())[:8]
        self.client = mqtt.Client(client_id=f"{self.identity}_{socket.gethostname()}_{unique_suffix}")
        
        if self.config.get("user"):
            self.client.username_pw_set(self.config["user"], self.config.get("password"))
            
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        try:
            # Paho's connect is blocking, run in simple way or executor
            self.client.connect(self.config["broker"], self.config.get("port", 1883), 60)
            self.client.loop_start() # Spawns a thread, which is "okay" for this simple integration
            self.logger.info("MQTT Client background thread started.")
            
            # Wait for connection
            for _ in range(50):
                if self.connected:
                    break
                await asyncio.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT: {e}")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            self.logger.info("Connected to MQTT Broker")
            # Subscribe to satellite topics
            # Topic format: gatekeeper/satellite/<room>/<mac>
            topic = f"{self.topic_prefix}/satellite/#" 
            # Note: topic_prefix default is 'monitor'. So 'monitor/satellite/#'
            client.subscribe(topic)
            self.logger.info(f"Subscribed to {topic}")
        else:
            self.logger.error(f"Failed to connect: {rc}")

    def _on_message(self, client, userdata, msg):
        # Handle incoming satellite messages
        try:
            # Topic patterns:
            # MAC-based: prefix/satellite/satellite_id/mac (payload: rssi int)
            # UUID-based: prefix/satellite/satellite_id/uuid/UUID (payload: JSON)
            parts = msg.topic.split('/')
            
            if len(parts) < 4 or parts[1] != 'satellite':
                return  # Not a satellite message
            
            satellite_id = parts[2]
            
            # Check if UUID-based or MAC-based
            if len(parts) >= 5 and parts[3] == 'uuid':
                # UUID-based: prefix/satellite/sat_id/uuid/UUID
                uuid = parts[4]
                try:
                    payload_data = json.loads(msg.payload.decode())
                    rssi = int(payload_data.get('rssi', -100))
                    major = payload_data.get('major')
                    minor = payload_data.get('minor')
                    
                    if self.satellite_callback and self.loop:
                        asyncio.run_coroutine_threadsafe(
                            self.satellite_callback(satellite_id, uuid, rssi, {'major': major, 'minor': minor}), 
                            self.loop
                        )
                except (ValueError, json.JSONDecodeError) as e:
                    self.logger.warning(f"Invalid UUID payload: {e}")
                    
            elif len(parts) >= 4:
                # MAC-based (legacy/fallback): prefix/satellite/sat_id/mac
                mac = parts[3].upper()
                try:
                    rssi = int(float(msg.payload.decode()))
                    
                    if self.satellite_callback and self.loop:
                        asyncio.run_coroutine_threadsafe(
                            self.satellite_callback(satellite_id, mac, rssi), 
                            self.loop
                        )
                except ValueError:
                    pass  # Invalid payload
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            
    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.logger.warning("Disconnected from MQTT Broker")
        self.connected = False

    async def publish_presence(self, device, present, rssi=None, attributes=None):
        if not self.client or not self.connected:
            return

        # The new code uses 'device['alias']' directly.
        # Ensure we match the logic in publish_discovery: replace space and dash with underscore, lower case.
        alias = device['alias']
        monitor_alias = alias.replace(' ', '_').replace('-', '_').lower()
        
        topic_base = f"{self.topic_prefix}/{self.identity}/{monitor_alias}"
        state_topic = f"{topic_base}/device_tracker" # Changed to match HA discovery state topic
        
        payload = "home" if present else "not_home"
        self.client.publish(state_topic, payload, retain=True)
        
        # HA Device Tracker JSON attributes
        attr_topic = topic_base 
        
        identifier = device.get('identifier', device.get('mac'))
        id_type = device.get('identifier_type', 'mac')
        
        attr_data = {
            "rssi": rssi,
            "identifier": identifier,
            "id_type": id_type,
            "source_type": "bluetooth",
            "confidence": 100 if present else 0
        }
        if id_type == 'mac':
            attr_data['mac'] = identifier
        if attributes:
            attr_data.update(attributes)
            
        self.client.publish(attr_topic, json.dumps(attr_data), retain=True)
        
        self.logger.debug(f"Published {payload} for {device.get('alias')}")

    async def publish_discovery(self, devices):
        if not self.connected:
            return
            
        for d in devices:
            alias = d['alias']
            safe_alias = alias.replace(' ', '_')
            # unique_id: gk_<identity>_<safe_alias> (e.g. gk_gatekeeper_Diana_iPhone)
            node_id = f"gk_{self.identity}_{safe_alias}"
            
            # HA Discovery Topic
            disc_topic = f"homeassistant/device_tracker/{node_id}/config"
            
            monitor_alias = safe_alias.replace('-', '_').lower()
            state_topic = f"{self.topic_prefix}/{self.identity}/{monitor_alias}/device_tracker"
            attr_topic = f"{self.topic_prefix}/{self.identity}/{monitor_alias}"

            identifier = d.get('identifier', d.get('mac'))
            id_type = d.get('identifier_type', 'mac')
            
            payload = {
                "name": f"{alias} ({self.identity})",
                "unique_id": node_id,
                "state_topic": state_topic,
                "payload_home": "home",
                "payload_not_home": "not_home",
                "source_type": "bluetooth",
                "json_attributes_topic": attr_topic,
                "icon": "mdi:bluetooth" if id_type == 'mac' else "mdi:identifier-variant"
            }
            
            # Use JSON string for payload
            self.client.publish(disc_topic, json.dumps(payload), retain=True)
            self.logger.info(f"Published Discovery for {alias}")
