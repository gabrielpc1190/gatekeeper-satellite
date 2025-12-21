import asyncio
import json
import logging
import socket
import uuid

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

class MQTTClient:
    """
    Asyncio-compatible wrapper for Paho MQTT Client.
    Runs the Paho loop in a background thread but invokes callbacks
    safely on the main asyncio event loop.
    """
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("MQTT")
        self.client = None
        self.connected = False
        self.satellite_callback = None # Function(satellite_id, identifier, rssi, extra)
        self.topic_prefix = config.get("topic_prefix", "monitor")
        self.identity = "gatekeeper" 
        self.loop = None 

    async def start(self):
        """Starts the MQTT client background thread."""
        if not mqtt:
            self.logger.error("paho-mqtt library not found. MQTT disabled.")
            return

        # Capture the running loop for thread-safe callbacks
        self.loop = asyncio.get_running_loop()
        
        unique_suffix = str(uuid.uuid4())[:8]
        client_id = f"{self.identity}_{socket.gethostname()}_{unique_suffix}"
        
        self.client = mqtt.Client(client_id=client_id)
        
        if self.config.get("user"):
            self.client.username_pw_set(self.config["user"], self.config.get("password"))
            
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        try:
            # Connect synchronously (blocking brief) then start loop
            self.client.connect(self.config["broker"], self.config.get("port", 1883), 60)
            self.client.loop_start()
            self.logger.info("MQTT Client background thread started.")
            
            # Wait for connection check
            for _ in range(50):
                if self.connected:
                    break
                await asyncio.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT: {e}")

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            self.logger.info("Connected to MQTT Broker")
            # Subscribe to satellite topics
            topic = f"{self.topic_prefix}/satellite/#" 
            client.subscribe(topic)
            self.logger.info(f"Subscribed to {topic}")
        else:
            self.logger.error(f"Failed to connect: {rc}")

    def _on_message(self, client, userdata, msg):
        """Handle incoming messages in Paho thread."""
        try:
            # Topic: prefix/satellite/satellite_id/...
            parts = msg.topic.split('/')
            
            if len(parts) < 3 or parts[1] != 'satellite':
                return
            
            satellite_id = parts[2]
            
            # Dispatch to async callback slightly differently for MAC vs UUID
            # UUID: .../uuid/UUID -> Payload JSON
            if len(parts) >= 5 and parts[3] == 'uuid':
                uuid_val = parts[4]
                try:
                    payload = json.loads(msg.payload.decode())
                    rssi = int(payload.get('rssi', -100))
                    extra = {'major': payload.get('major'), 'minor': payload.get('minor')}
                    
                    self._dispatch_callback(satellite_id, uuid_val, rssi, extra)
                except Exception as e:
                    self.logger.warning(f"Invalid UUID payload: {e}")
            
            # MAC: .../MAC -> Payload RSSI (int)
            elif len(parts) >= 4:
                mac = parts[3].upper()
                try:
                    rssi = int(float(msg.payload.decode()))
                    self._dispatch_callback(satellite_id, mac, rssi, {})
                except ValueError:
                    pass

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _dispatch_callback(self, sid, ident, rssi, extra):
        """Thread-safe dispatch to main loop."""
        if self.satellite_callback and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.satellite_callback(sid, ident, rssi, extra), 
                self.loop
            )

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.logger.warning("Disconnected from MQTT Broker")
        self.connected = False

    async def publish_presence(self, device, present, rssi=None, attributes=None):
        """Publish device tracker state to HA."""
        if not self.client or not self.connected: 
            return

        alias = device['alias']
        # Normalize alias for topic usage
        safe_alias = alias.replace(' ', '_').replace('-', '_').lower()
        
        topic_base = f"{self.topic_prefix}/{self.identity}/{safe_alias}"
        state_topic = f"{topic_base}/device_tracker"
        attr_topic = topic_base 
        
        payload = "home" if present else "not_home"
        
        # Publish calls are thread-safe in Paho
        self.client.publish(state_topic, payload, retain=True)
        
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

    async def publish_discovery(self, devices):
        """Publish Home Assistant Discovery payloads."""
        if not self.connected: return
            
        # 0. HUB Discovery (The "Parent" device)
        hub_id = f"gk_{self.identity}_hub"
        hub_disc_topic = f"homeassistant/binary_sensor/{hub_id}/config"
        hub_device = {
            "identifiers": [hub_id],
            "name": f"Gatekeeper Hub ({self.identity})",
            "manufacturer": "Gatekeeper",
            "model": "Gatekeeper NG Hub",
            "sw_version": "1.0.1"
        }
        hub_payload = {
            "name": "Status",
            "unique_id": hub_id,
            "state_topic": f"{self.topic_prefix}/{self.identity}/status",
            "payload_on": "online",
            "payload_off": "offline",
            "device_class": "connectivity",
            "device": hub_device
        }
        self.client.publish(hub_disc_topic, json.dumps(hub_payload), retain=True)
        # Also publish the hub status itself
        self.client.publish(f"{self.topic_prefix}/{self.identity}/status", "online", retain=True)

        for d in devices:
            alias = d['alias']
            
            # --- CLEANUP LEGACY TOPICS ---
            # Old node IDs used hyphens/caps and different unique_id schemes
            old_safe = alias.replace(' ', '_')
            old_node = f"gk_{self.identity}_{old_safe}"
            # Clear old device tracker (it used node_id as unique_id)
            self.client.publish(f"homeassistant/device_tracker/{old_node}/config", "", retain=True)
            # Clear old sensors (Step 1453 style)
            for s in ["room", "distance", "rssi"]:
                self.client.publish(f"homeassistant/sensor/{old_node}_{s}/config", "", retain=True)
            
            # --- NEW CLEAN NAMING ---
            safe_alias = alias.replace(' ', '_').replace('-', '_').lower()
            node_id = f"gk_{self.identity}_{safe_alias}"
            
            # Additional Cleanup: Clear the lowercased node_id tracker topic (pre-Step 1627)
            self.client.publish(f"homeassistant/device_tracker/{node_id}/config", "", retain=True)
            
            # Tracker Unique ID
            disc_topic = f"homeassistant/device_tracker/{node_id}/config"
            
            monitor_alias = safe_alias 
            state_topic = f"{self.topic_prefix}/{self.identity}/{monitor_alias}/device_tracker"
            attr_topic = f"{self.topic_prefix}/{self.identity}/{monitor_alias}"
            
            id_type = d.get('identifier_type', 'mac')
            
            # Device definition for this tracked entity
            device_info = {
                "identifiers": [f"device_{node_id}"],
                "name": alias,
                "manufacturer": "Gatekeeper",
                "model": "Generic Tracked Device",
                "via_device": hub_id
            }

            payload = {
                "name": "Presence",
                "unique_id": f"{node_id}_presence",
                "state_topic": state_topic,
                "payload_home": "home",
                "payload_not_home": "not_home",
                "source_type": "bluetooth",
                "json_attributes_topic": attr_topic,
                "icon": "mdi:bluetooth" if id_type == 'mac' else "mdi:identifier-variant",
                "device": device_info
            }
            
            # 1. Device Tracker Discovery
            self.client.publish(disc_topic, json.dumps(payload), retain=True)
            
            # 2. Room Sensor Discovery
            room_node_id = f"{node_id}_room"
            room_disc_topic = f"homeassistant/sensor/{room_node_id}/config"
            room_payload = {
                "name": "Room",
                "unique_id": room_node_id,
                "state_topic": attr_topic,
                "value_template": "{{ value_json.room }}",
                "icon": "mdi:room-service",
                "device": device_info
            }
            self.client.publish(room_disc_topic, json.dumps(room_payload), retain=True)

            # 3. Distance Sensor Discovery
            dist_node_id = f"{node_id}_distance"
            dist_disc_topic = f"homeassistant/sensor/{dist_node_id}/config"
            dist_payload = {
                "name": "Distance",
                "unique_id": dist_node_id,
                "state_topic": attr_topic,
                "value_template": "{{ value_json.distance if value_json.distance != -1 else 'N/A' }}",
                "unit_of_measurement": "m",
                "icon": "mdi:ruler",
                "device": device_info
            }
            self.client.publish(dist_disc_topic, json.dumps(dist_payload), retain=True)

            # 4. RSSI Sensor Discovery
            rssi_node_id = f"{node_id}_rssi"
            rssi_disc_topic = f"homeassistant/sensor/{rssi_node_id}/config"
            rssi_payload = {
                "name": "RSSI",
                "unique_id": rssi_node_id,
                "state_topic": attr_topic,
                "value_template": "{{ value_json.rssi }}",
                "unit_of_measurement": "dBm",
                "device_class": "signal_strength",
                "icon": "mdi:signal",
                "device": device_info
            }
            self.client.publish(rssi_disc_topic, json.dumps(rssi_payload), retain=True)

            self.logger.info(f"Published Discovery (Tracker + 3 Sensors) for {alias}")
