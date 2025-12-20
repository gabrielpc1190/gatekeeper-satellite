import time
import logging
import asyncio
from .signal_proc import SignalBuffer, calculate_distance

class DeviceTracker:
    def __init__(self, config_mgr, mqtt_client):
        self.config_mgr = config_mgr
        self.mqtt_client = mqtt_client
        self.logger = logging.getLogger("Tracker")
        
        # State
        self.known_devices = {} # identifier -> config_dict
        self.current_state = {} 
        # State Structure:
        # identifier -> {
        #    'present': bool,
        #    'last_seen': float,
        #    'room': str, 
        #    'rssi': int,
        #    'distance': float,  
        #    'sources': { 
        #         'sat_id': {'raw_rssi': int, 'smooth_rssi': float, 'distance': float, 'last_seen': float, 'room_name': str} 
        #    }
        # }
        
        # Signal Buffers
        self.signal_buffers = {}
        
        # Zoning State 
        self.zoning_state = {} 
        
        # iBeacon Cache for UI
        self.recent_ibeacons = {}
        
        # Calibration helper
        self.last_sat_signals = {}
        
        # Config
        self.timeout_interval = 45 
        self.min_rssi = -100 
        self.hysteresis_db = 3.0 
        self.debounce_time = 3.0 
        self.absence_timeout = 15.0 
        
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

    async def process_remote_packet(self, satellite_id, identifier, rssi, extra_data=None):
        # 1. Update Calibration Cache
        now = time.time()
        if satellite_id not in self.last_sat_signals or (now - self.last_sat_signals[satellite_id]['time']) > 2:
            self.last_sat_signals[satellite_id] = {'rssi': rssi, 'time': now}
        else:
            if rssi > self.last_sat_signals[satellite_id]['rssi']:
                self.last_sat_signals[satellite_id] = {'rssi': rssi, 'time': now}

        # 2. Cache iBeacons (UI only)
        if extra_data and ('-' in identifier and len(identifier) == 36):
            self._update_ibeacon_cache(satellite_id, identifier, rssi, extra_data)
            
        # 3. Manage Satellite Registration 
        await self._check_satellite_registration(satellite_id)
        
        # 4. Filter Unknown Devices
        if identifier not in self.known_devices:
            return

        # 5. Initialize State
        if identifier not in self.current_state:
            self.current_state[identifier] = {'present': False, 'sources': {}, 'room': 'unknown', 'rssi': -100, 'distance': -1, 'last_seen': 0}
            
        # 6. Signal Processing Pipeline
        buf_key = (satellite_id, identifier)
        if buf_key not in self.signal_buffers:
            self.signal_buffers[buf_key] = SignalBuffer()
        
        smooth_rssi = self.signal_buffers[buf_key].add_sample(rssi)
        
        # Apply Calibration & Distance
        sats = self.config_mgr.load_satellites()
        sat_info = sats.get(satellite_id, {})
        measured_ref = sat_info.get('ref_rssi_1m', -59)
        
        # Distance calculation
        dist = calculate_distance(smooth_rssi, tx_power=measured_ref)
        
        # Offset (Legacy approach, kept for RSSI normalization if needed, but distance is better)
        offset = measured_ref - (-59)
        normalized_rssi = smooth_rssi - offset
        
        # Update Source State
        state = self.current_state[identifier]
        actual_room = sat_info.get('room', 'Unassigned')
        if actual_room == 'Unassigned':
            actual_room = f"Sat:{satellite_id}"
            
        state['sources'][satellite_id] = {
            'raw_rssi': rssi,
            'smooth_rssi': normalized_rssi,
            'distance': dist,
            'last_seen': now,
            'room_name': actual_room
        }
        state['last_seen'] = now
        
        # 7. Zoning Logic
        await self._evaluate_zone(identifier)

    async def _evaluate_zone(self, identifier):
        state = self.current_state[identifier]
        now = time.time()
        
        best_sat = None
        best_rssi = -999
        
        for sat, data in state['sources'].items():
            if (now - data['last_seen']) < self.absence_timeout:
                if data['smooth_rssi'] > best_rssi:
                    best_rssi = data['smooth_rssi']
                    best_sat = sat
        
        if not best_sat: return
        
        candidate_source = state['sources'][best_sat]
        candidate_room = candidate_source['room_name']
        candidate_dist = candidate_source['distance']
        
        current_room = state.get('room', 'unknown')
        
        if identifier not in self.zoning_state:
            self.zoning_state[identifier] = {'pending_room': None, 'start': 0}
        z_state = self.zoning_state[identifier]
        
        # Immediate switch if unknown
        if current_room in ['unknown', 'Unassigned'] and candidate_room != 'Unassigned':
             await self._change_room(identifier, candidate_room, best_rssi, candidate_dist)
             return
        
        # Find current room strength
        current_room_rssi = -999
        for sat, data in state['sources'].items():
            if (now - data['last_seen']) < self.absence_timeout:
                if data['room_name'] == current_room:
                    if data['smooth_rssi'] > current_room_rssi:
                        current_room_rssi = data['smooth_rssi']
        
        if current_room_rssi == -999:
             await self._change_room(identifier, candidate_room, best_rssi, candidate_dist)
             return
             
        # Hysteresis Check
        if best_rssi > (current_room_rssi + self.hysteresis_db):
            if z_state['pending_room'] == candidate_room:
                if (now - z_state['start']) >= self.debounce_time:
                    await self._change_room(identifier, candidate_room, best_rssi, candidate_dist)
                    z_state['pending_room'] = None
            else:
                z_state['pending_room'] = candidate_room
                z_state['start'] = now
        else:
            z_state['pending_room'] = None

        if state['room'] == current_room:
            old_rssi = state.get('rssi', -100)
            state['rssi'] = current_room_rssi
            # Update distance for current room based on best sat in that room
            # (Simple approximation: use best sat's distance)
            # Better: recalculate best sat for current room
            best_curr_dist = -1
            for sat, data in state['sources'].items():
                 if data['room_name'] == current_room and data['smooth_rssi'] == current_room_rssi:
                     best_curr_dist = data['distance']
                     break
            state['distance'] = best_curr_dist
            
            if abs(old_rssi - current_room_rssi) > 2.0 or (now - state.get('last_pub', 0)) > 30:
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

    def _update_ibeacon_cache(self, satellite_id, identifier, rssi, extra_data):
        if identifier not in self.recent_ibeacons:
            self.recent_ibeacons[identifier] = {
                'uuid': identifier, 'rssi': rssi, 'major': extra_data.get('major'), 'minor': extra_data.get('minor'),
                'last_seen': time.time(), 'sources': [satellite_id]
            }
        else:
            c = self.recent_ibeacons[identifier]
            c['rssi'] = rssi; c['last_seen'] = time.time()
            if satellite_id not in c['sources']: c['sources'].append(satellite_id)

    async def _check_satellite_registration(self, satellite_id):
        if not hasattr(self, '_mem_satellites_cache'):
            satellites = self.config_mgr.load_satellites()
            self._mem_satellites_cache = set(satellites.keys())
        if satellite_id not in self._mem_satellites_cache:
            satellites = self.config_mgr.load_satellites()
            if satellite_id not in satellites:
                satellites[satellite_id] = {'room': 'Unassigned', 'last_seen': time.time()}
                self.config_mgr.save_satellites(satellites)
                self.logger.info(f"New Satellite: {satellite_id}")
            self._mem_satellites_cache.add(satellite_id)

    async def publish_update(self, identifier):
        if identifier not in self.known_devices or identifier not in self.current_state: return
        conf = self.known_devices[identifier]
        state = self.current_state[identifier]
        state['last_pub'] = time.time()
        extra = {
            "room": state.get('room', 'unknown'),
            "distance": state.get('distance', -1),
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
        await self.process_remote_packet('gatekeeper-hub', record.get('identifier', record['mac'].upper()), record['rssi'], extra_data=record.get('extra'))
