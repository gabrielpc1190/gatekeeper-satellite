import time
import logging
import asyncio
from .signal_proc import SignalBuffer, calculate_distance

class DeviceTracker:
    def __init__(self, config_mgr, mqtt_client):
        self.config_mgr = config_mgr
        self.mqtt_client = mqtt_client
        self.mqtt_client.health_callback = self.process_satellite_health
        self.logger = logging.getLogger("Tracker")
        
        # State
        self.known_devices = {} # identifier -> config_dict
        self.current_state = {} 
        self.satellite_stats = {} # sid -> {sensor_name: value, last_seen: time}
        
        # Signal Buffers
        self.signal_buffers = {}
        
        # Zoning State 
        self.zoning_state = {} 
        
        # Discovery Cache for UI (Shared for iBeacons and BLE MACs)
        self.discovery_cache = {}
        
        # Calibration helper
        self.last_sat_signals = {}
        
        # Config (Optimized for Low Duty Cycle)
        self.timeout_interval = 45 
        self.min_rssi = -100 
        self.hysteresis_dist = 0.8 
        self.debounce_time = 5.0     
        self.absence_timeout = 60.0  
        
        self.reload_config()

    def reload_config(self):
        devices = self.config_mgr.load_devices()
        self.known_devices = {}
        for d in devices:
            if 'identifier' in d:
                key = d['identifier'].upper() if d.get('identifier_type') == 'mac' else d['identifier']
            else:
                key = d['mac'].upper()
            self.known_devices[key] = d
            
        settings = self.config_mgr.load_settings()
        self.timeout_interval = int(settings.get("PREF_BEACON_EXPIRATION", 60))
        self.logger.info(f"Loaded {len(self.known_devices)} known devices.")

    async def process_satellite_health(self, satellite_id, sensor_name, value):
        """Handle health sensors from satellites (WiFi, Uptime, etc.)"""
        if satellite_id not in self.satellite_stats:
            self.satellite_stats[satellite_id] = {}
        
        self.satellite_stats[satellite_id][sensor_name] = value
        self.satellite_stats[satellite_id]['last_health_update'] = time.time()
        
        # Also ensure last_seen in config gets updated via remote packet or here
        await self._check_satellite_registration(satellite_id)

    async def process_remote_packet(self, satellite_id, identifier, rssi, extra_data=None):
        """Handle packet from remote satellite via MQTT."""
        # Normalize identifier to avoid case mismatches
        identifier = identifier.upper()
        
        # 1. Update Calibration Cache (Always update with latest for real-time stream)
        now = time.time()
        self.last_sat_signals[satellite_id] = {'rssi': rssi, 'time': now}

        # 2. Update Discovery Cache (UI only)
        self._update_discovery_cache(satellite_id, identifier, rssi, extra_data)
            
        # 3. Manage Satellite Registration (Freshness update)
        await self._check_satellite_registration(satellite_id)
        
        # 4. Filter Unknown Devices
        if identifier not in self.known_devices:
            return
            
        # 5. Get/Create Device State
        if identifier not in self.current_state:
            self.current_state[identifier] = {
                'identifier': identifier,
                'sources': {},
                'present': False,
                'room': 'Unknown',
                'rssi': -100,
                'distance': -1,
                'last_seen': 0
            }
        
        state = self.current_state[identifier]
        
        # 6. Signal Processing Pipeline
        # Determine room name and reference RSSI
        actual_room = 'Unassigned'
        ref_rssi = -65
        
        sats = self.config_mgr.load_satellites()
        if satellite_id in sats:
            actual_room = sats[satellite_id].get('room', 'Unassigned')
            ref_rssi = sats[satellite_id].get('ref_rssi_1m', -65)
        
        if actual_room == 'Unassigned':
            actual_room = f"Sat:{satellite_id}"
            
        # Signal Smoothing (EMA) via SignalBuffer
        buf_key = (satellite_id, identifier)
        if buf_key not in self.signal_buffers:
            self.signal_buffers[buf_key] = SignalBuffer()
        
        smooth_rssi = self.signal_buffers[buf_key].add_sample(rssi)
        dist = calculate_distance(smooth_rssi, tx_power=ref_rssi)
        
        # Update Source Details
        state['sources'][satellite_id] = {
            'raw_rssi': rssi,
            'smooth_rssi': smooth_rssi,
            'distance': dist,
            'last_seen': now,
            'room_name': actual_room
        }
        state['last_seen'] = now
        
        # 7. Evaluate Zoning
        await self._evaluate_zone(identifier)

    async def _evaluate_zone(self, identifier):
        state = self.current_state[identifier]
        now = time.time()
        
        best_sat = None
        min_dist = 999.0
        
        # 1. Select Best Satellite BASED ON DISTANCE (Lower is closer)
        for sat, data in state['sources'].items():
            age = now - data['last_seen']
            if age < self.absence_timeout:
                if data['distance'] < min_dist:
                    min_dist = data['distance']
                    best_sat = sat
        
        if not best_sat: return
        
        candidate_source = state['sources'][best_sat]
        candidate_room = candidate_source['room_name']
        candidate_dist = candidate_source['distance']
        candidate_rssi = candidate_source['smooth_rssi']
        
        current_room = state.get('room', 'unknown')
        
        if identifier not in self.zoning_state:
            self.zoning_state[identifier] = {'pending_room': None, 'start': 0}
        z_state = self.zoning_state[identifier]
        
        # Immediate assignment if currently unknown or not at home
        if current_room in ['unknown', 'Unassigned', 'not_home'] and candidate_room != 'Unassigned':
             await self._change_room(identifier, candidate_room, candidate_rssi, candidate_dist)
             return
        
        # 2. Get current room metrics
        current_room_min_dist = 999.0
        current_room_best_rssi = -999.0
        for sat, data in state['sources'].items():
            if (now - data['last_seen']) < self.absence_timeout:
                if data['room_name'] == current_room:
                    if data['distance'] < current_room_min_dist:
                        current_room_min_dist = data['distance']
                        current_room_best_rssi = data['smooth_rssi']
        
        # If current room lost all satellites (timeout), switch immediately to best available
        if current_room_min_dist == 999.0:
             self.logger.info(f"[{identifier}] Current room {current_room} TIMEOUT. Switching to {candidate_room}.")
             await self._change_room(identifier, candidate_room, candidate_rssi, candidate_dist)
             return
             
        # 3. Decision with Distance Hysteresis
        # Switch only if the candidate is significantly closer than current room's closest satellite
        margin = current_room_min_dist - candidate_dist
        if candidate_dist < (current_room_min_dist - self.hysteresis_dist):
            if z_state['pending_room'] == candidate_room:
                elapsed = now - z_state['start']
                if elapsed >= self.debounce_time:
                    self.logger.info(f"[{identifier}] DEBOUNCE OK: Switching {current_room} -> {candidate_room} (Margin: {margin:.1f}m)")
                    await self._change_room(identifier, candidate_room, candidate_rssi, candidate_dist)
                    z_state['pending_room'] = None
            else:
                z_state['pending_room'] = candidate_room
                z_state['start'] = now
                self.logger.info(f"[{identifier}] PENDING CHANGE: {current_room} -> {candidate_room} (Margin: {margin:.1f}m, Dist: {candidate_dist:.1f}m)")
        elif candidate_room == current_room:
            # If the best satellite IS the current room, reset any pending jump to another room
            if z_state['pending_room']:
                self.logger.debug(f"[{identifier}] Resetting pending jump to {z_state['pending_room']} - current is better.")
            z_state['pending_room'] = None

        # Update state with latest metrics from current room if still there
        if state['room'] == current_room:
            state['rssi'] = current_room_best_rssi
            state['distance'] = current_room_min_dist
            
            if (now - state.get('last_pub', 0)) > 30:
                await self.publish_update(identifier)

    async def _change_room(self, identifier, new_room, new_rssi, new_dist):
        state = self.current_state[identifier]
        old_room = state.get('room', 'unknown')
        state['room'] = new_room
        state['rssi'] = new_rssi
        state['distance'] = new_dist
        state['present'] = True
        self.logger.info(f"ZONE CHANGE: {identifier} {old_room} -> {new_room} (RSSI: {new_rssi:.1f}, Dist: {new_dist}m)")
        await self.publish_update(identifier)

    def _update_discovery_cache(self, satellite_id, identifier, rssi, extra_data):
        # We cap the cache size just in case
        if len(self.discovery_cache) > 200:
             # Clean old ones
             now = time.time()
             old_keys = [k for k, v in self.discovery_cache.items() if (now - v['last_seen']) > 300]
             for k in old_keys: del self.discovery_cache[k]
             
        if identifier not in self.discovery_cache:
            self.discovery_cache[identifier] = {
                'identifier': identifier, 
                'rssi': rssi, 
                'major': extra_data.get('major') if extra_data else None, 
                'minor': extra_data.get('minor') if extra_data else None,
                'name': extra_data.get('name') if extra_data else None,
                'last_seen': time.time(), 
                'sources': {satellite_id: rssi}
            }
        else:
            c = self.discovery_cache[identifier]
            c['rssi'] = max(c['rssi'], rssi) # Keep best RSSI
            c['last_seen'] = time.time()
            c['sources'][satellite_id] = rssi
            if extra_data and extra_data.get('name'):
                c['name'] = extra_data.get('name')

    def clear_discovery_cache(self):
        self.discovery_cache = {}
        self.logger.info("Discovery cache cleared by user.")

    async def _check_satellite_registration(self, satellite_id):
        if not hasattr(self, '_mem_satellites_cache'):
            satellites = self.config_mgr.load_satellites()
            self._mem_satellites_cache = set(satellites.keys())
        
        # Load fresh to check/update
        # Optimization: We could keep 'satellites' in memory but ConfigMgr loads from disk.
        # For now, let's load-check-save pattern but throttled.
        
        should_save = False
        satellites = self.config_mgr.load_satellites()
        
        if satellite_id not in satellites:
            satellites[satellite_id] = {'room': 'Unassigned', 'last_seen': time.time()}
            should_save = True
            self.logger.info(f"New Satellite: {satellite_id}")
            self._mem_satellites_cache.add(satellite_id)
        else:
            # Check if we need to update timestamp (throttle to every 60s)
            last = satellites[satellite_id].get('last_seen', 0)
            if (time.time() - last) > 60:
                satellites[satellite_id]['last_seen'] = time.time()
                should_save = True
        
        if should_save:
            self.config_mgr.save_satellites(satellites)

    async def publish_update(self, identifier):
        if identifier not in self.known_devices or identifier not in self.current_state: return
        conf = self.known_devices[identifier]
        state = self.current_state[identifier]
        state['last_pub'] = time.time()
        extra = {
            "room": state.get('room', 'unknown'),
            "distance": state.get('distance', -1),
            "last_seen": int(state.get('last_seen', 0)),
            "raw_sources": {k: int(v['raw_rssi']) for k, v in state.get('sources', {}).items()}
        }
        await self.mqtt_client.publish_presence(conf, state['present'], int(state.get('rssi', -100)), attributes=extra)

    async def maintenance_loop(self):
        while True:
            await asyncio.sleep(2)
            now = time.time()
            for identifier, state in list(self.current_state.items()):
                if not state['present']: continue
                if (now - state['last_seen']) > self.timeout_interval:
                    dev = self.known_devices.get(identifier, {'alias': identifier})
                    self.logger.info(f"DEPARTURE: {dev['alias']}")
                    state['present'] = False
                    state['room'] = 'not_home'
                    state['distance'] = -1
                    await self.publish_update(identifier)
                    continue
                current_room = state.get('room')
                room_alive = False
                for sat, data in state['sources'].items():
                     if data['room_name'] == current_room and (now - data['last_seen']) < self.absence_timeout:
                          room_alive = True
                          break
                if not room_alive and state['present']:
                    await self._evaluate_zone(identifier)

    async def process_packet(self, record):
        # Local packet from Hub
        await self.process_remote_packet('gatekeeper-hub', record.get('identifier', record['mac'].upper()), record['rssi'], extra_data=record)
