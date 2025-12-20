from flask import Flask, render_template, request, redirect, url_for, flash
import logging
import os
import json
import threading

# We import ConfigManager from app to reuse logic
from app.config_mgr import ConfigManager

class WebAdmin:
    def __init__(self, config_mgr, tracker=None, scanner=None, host='0.0.0.0', port=80):
        self.app = Flask(__name__, template_folder='templates')
        self.app.secret_key = 'gatekeeper_secret_ng'
        self.config_mgr = config_mgr
        self.tracker = tracker
        self.scanner = scanner
        self.host = host
        self.port = port
        self.logger = logging.getLogger("WebAdmin")

        # Register Routes
        self.app.add_url_rule('/', 'dashboard', self.dashboard)
        self.app.add_url_rule('/health', 'health', self.health)
        self.app.add_url_rule('/devices', 'manage_devices', self.manage_devices)
        self.app.add_url_rule('/devices/add', 'add_device', self.add_device, methods=['POST'])
        self.app.add_url_rule('/devices/edit', 'edit_device', self.edit_device, methods=['POST'])
        self.app.add_url_rule('/devices/delete', 'delete_device', self.delete_device, methods=['POST'])
        self.app.add_url_rule('/devices/announce', 'announce_devices', self.announce_devices, methods=['POST'])
        self.app.add_url_rule('/mqtt', 'manage_mqtt', self.manage_mqtt)
        self.app.add_url_rule('/mqtt/save', 'save_mqtt', self.save_mqtt, methods=['POST'])
        self.app.add_url_rule('/preferences', 'manage_preferences', self.manage_preferences)
        self.app.add_url_rule('/preferences/save', 'save_preferences', self.save_preferences, methods=['POST'])
        self.app.add_url_rule('/bluetooth', 'bluetooth_tools', self.bluetooth_tools)
        self.app.add_url_rule('/bluetooth/scan', 'bluetooth_scan_api', self.bluetooth_scan_api, methods=['POST'])
        self.app.add_url_rule('/satellites', 'manage_satellites', self.manage_satellites)
        self.app.add_url_rule('/satellites/update', 'update_satellite', self.update_satellite, methods=['POST'])
        self.app.add_url_rule('/satellites/calibrate', 'calibrate_satellite', self.calibrate_satellite, methods=['GET'])
        self.app.add_url_rule('/satellites/update_ref', 'update_satellite_ref', self.update_satellite_ref, methods=['POST'])
        self.app.add_url_rule('/logs', 'view_logs', self.view_logs)
        self.app.add_url_rule('/restart', 'restart_service', self.restart_service, methods=['POST'])

    def run_server(self):
        self.logger.info(f"Starting Web Admin on port {self.port}")
        # Disable Flask banner to keep logs clean
        cli = list(self.app.logger.handlers) 
        for h in cli: self.app.logger.removeHandler(h)
        
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

    def start(self):
        t = threading.Thread(target=self.run_server, daemon=True)
        t.start()
        
    # --- ROUTES ---

    def health(self):
        return json.dumps({"status": "ok"})

    def dashboard(self):
        devices = self.config_mgr.load_devices()
        
        # Enrich with live data
        if self.tracker:
            import time
            for d in devices:
                key = d.get('identifier', d.get('mac'))
                # Normalize key
                if d.get('identifier_type') == 'mac' or not d.get('identifier_type'):
                     key = key.upper()
                     
                state = self.tracker.current_state.get(key)
                if state and state.get('present'):
                    seen = state.get('last_seen')
                    # Format time roughly
                    d['last_seen'] = time.ctime(seen)
                    d['last_seen_fmt'] = f"{int(time.time() - seen)}s ago"
                    d['present'] = True
                    d['room'] = state.get('room', 'Unknown')
                    d['distance'] = state.get('distance', -1)
                elif state:
                     d['last_seen'] = time.ctime(state.get('last_seen'))
                     diff = int(time.time() - state.get('last_seen'))
                     if diff > 86400:
                         d['last_seen_fmt'] = f"{diff // 86400} days ago"
                     elif diff > 3600:
                         d['last_seen_fmt'] = f"{diff // 3600}h ago"
                     else:
                         d['last_seen_fmt'] = f"{diff // 60}m ago"
                     d['present'] = False
                else:
                    d['last_seen'] = "No recent data"
                    d['present'] = False
        
        return render_template('dashboard.html', 
                             service_active=True, 
                             file_count=len(devices),
                             devices=devices)

    def manage_devices(self):
        devices = self.config_mgr.load_devices()
        return render_template('devices.html', devices=devices)

    def add_device(self):
        # Support both MAC and UUID identifiers
        identifier = request.form.get('identifier', '').strip()
        identifier_type = request.form.get('identifier_type', 'mac')  # 'mac' or 'uuid'
        alias = request.form.get('alias', '').strip()
        dev_type = request.form.get('type', 'Phone' if identifier_type == 'uuid' else 'Bluetooth')
        
        # Backward compatibility: if identifier not provided, use 'mac'
        if not identifier:
            identifier = request.form.get('mac', '').strip().upper()
            identifier_type = 'mac'
        
        if identifier and alias:
            devices = self.config_mgr.load_devices()
            # Check dupes (check both old and new schema)
            for d in devices:
                existing = d.get('identifier', d.get('mac'))
                if existing == identifier:
                    flash('Device already exists')
                    return redirect(url_for('manage_devices'))
            
            # Use new schema
            new_device = {
                'identifier': identifier,
                'identifier_type': identifier_type,
                'alias': alias,
                'type': dev_type
            }
            
            devices.append(new_device)
            self.config_mgr.save_devices(devices)
            
            # Hot reload tracker config
            if self.tracker:
                self.tracker.reload_config()
            
            flash(f'Added {alias}')
        
        return redirect(url_for('manage_devices'))

    def delete_device(self):
        # target can be either MAC or UUID
        target = request.form.get('identifier', request.form.get('mac', '')).strip()
        if not target:
             flash('No device specified')
             return redirect(url_for('manage_devices'))

        devices = self.config_mgr.load_devices()
        new_list = []
        found = False
        
        for d in devices:
            ident = d.get('identifier', d.get('mac', '')).strip()
            if ident.upper() == target.upper():
                found = True
                continue
            new_list.append(d)
            
        if found:
            self.config_mgr.save_devices(new_list)
            if self.tracker:
                self.tracker.reload_config()
            flash('Device deleted')
        else:
            flash('Device not found')
            
        return redirect(url_for('manage_devices'))

    def edit_device(self):
        original_id = request.form.get('original_identifier', request.form.get('original_mac', '')).strip()
        new_id = request.form.get('identifier', request.form.get('mac', '')).strip()
        new_alias = request.form.get('alias', '').strip()
        new_type = request.form.get('type', 'Bluetooth').strip()
        id_type = request.form.get('identifier_type', 'mac')

        if not original_id or not new_id or not new_alias:
            flash('Missing required fields')
            return redirect(url_for('manage_devices'))

        devices = self.config_mgr.load_devices()
        updated = False
        for i, d in enumerate(devices):
            ident = d.get('identifier', d.get('mac', '')).strip()
            if ident.upper() == original_id.upper():
                # Update existing entry
                devices[i] = {
                    'identifier': new_id if id_type == 'mac' else new_id, # Keep case for UUID
                    'identifier_type': id_type,
                    'alias': new_alias,
                    'type': new_type
                }
                # Normalize MAC if it's a MAC
                if id_type == 'mac':
                    devices[i]['identifier'] = devices[i]['identifier'].upper()
                
                updated = True
                break
        
        if updated:
            self.config_mgr.save_devices(devices)
            if self.tracker:
                self.tracker.reload_config()
            flash(f'Updated {new_alias}')
        else:
            flash('Could not find device to update')
            
        return redirect(url_for('manage_devices'))

    def announce_devices(self):
        try:
            if not self.tracker or not self.tracker.mqtt_client:
                flash('MQTT not connected or tracker missing')
                return redirect(url_for('manage_devices'))
                
            import asyncio
            import traceback
            devices = self.config_mgr.load_devices()
            
            # We need to run the async publish_discovery in the main event loop
            # The MQTT client stores a reference to it
            loop = getattr(self.tracker.mqtt_client, 'loop', None)
            
            if loop:
                asyncio.run_coroutine_threadsafe(
                    self.tracker.mqtt_client.publish_discovery(devices),
                    loop
                )
                flash('MQTT Discovery messages published')
            else:
                flash('System loop not ready. Try again in a moment.')
                
        except Exception as e:
            import traceback
            self.logger.error(f"Error in announce_devices: {e}\n{traceback.format_exc()}")
            flash(f"Error: {str(e)}")
            
        return redirect(url_for('manage_devices'))

    def manage_mqtt(self):
        prefs = self.config_mgr.load_mqtt()
        view_prefs = {
            'mqtt_address': prefs.get('broker'),
            'mqtt_port': prefs.get('port'),
            'mqtt_user': prefs.get('user'),
            'mqtt_password': prefs.get('password'),
            'mqtt_topicpath': prefs.get('topic_prefix'),
            'mqtt_publisher_identity': 'gatekeeper'
        }
        return render_template('mqtt.html', prefs=view_prefs)

    def save_mqtt(self):
        data = request.form
        new_conf = {
            "broker": data.get('mqtt_address'),
            "port": int(data.get('mqtt_port', 1883)),
            "user": data.get('mqtt_user'),
            "password": data.get('mqtt_password'),
            "topic_prefix": data.get('mqtt_topicpath')
        }
        
        # Save directly (ConfigMgr has atomic write helper but exposed as save_settings/devices)
        # We can use the atomic _atomic_write if we access it, but let's stick to standard open for now or expose it.
        # Ideally, add save_mqtt to ConfigMgr. For now, use robust open.
        mqtt_file = self.config_mgr.mqtt_file
        try:
            # Atomic-ish write manually
            tmp_path = mqtt_file + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(new_conf, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, mqtt_file)
            
            flash('MQTT Saved. Please Restart.')
        except Exception as e:
            flash(f"Error: {e}")
            
        return redirect(url_for('manage_mqtt'))

    def manage_preferences(self):
        prefs = self.config_mgr.load_settings()
        return render_template('preferences.html', prefs=prefs)

    def save_preferences(self):
        # Flatten form data to dict
        new_prefs = {k: v for k, v in request.form.items()}
        # Handle Checkboxes
        if 'PREF_DEVICE_TRACKER_REPORT' not in new_prefs: new_prefs['PREF_DEVICE_TRACKER_REPORT'] = 'false'
        if 'PREF_ENABLE_LOGGING' not in new_prefs: new_prefs['PREF_ENABLE_LOGGING'] = 'false'
        
        self.config_mgr.save_settings(new_prefs)
        
        if self.tracker:
            self.tracker.reload_config()
            
        flash('Preferences Saved.')
        return redirect(url_for('manage_preferences'))

    def bluetooth_tools(self):
        return render_template('bluetooth.html', scan_results=[])
    
    def bluetooth_scan_api(self):
        # Get known identifiers (both MAC and UUID)
        known_identifiers = set()
        if self.config_mgr:
            devices = self.config_mgr.load_devices()
            for d in devices:
                if 'identifier' in d:
                    known_identifiers.add(d['identifier'])
                elif 'mac' in d:
                    known_identifiers.add(d['mac'].upper())
        
        results = []
        
        # Add iBeacons from tracker cache
        if self.tracker and hasattr(self.tracker, 'recent_ibeacons'):
            import time
            now = time.time()
            for uuid, data in list(self.tracker.recent_ibeacons.items()):
                if now - data.get('last_seen', 0) < 60:
                    results.append({
                        'type': 'ibeacon',
                        'identifier': uuid,
                        'uuid_short': uuid[:8] + '...' + uuid[-4:],
                        'uuid_full': uuid,
                        'rssi': data.get('rssi', -100),
                        'major': data.get('major'),
                        'minor': data.get('minor'),
                        'name': f"iBeacon {data.get('major', '?')}/{data.get('minor', '?')}",
                        'tracked': uuid in known_identifiers,
                        'sources': ', '.join(data.get('sources', []))
                    })
        
        # Add regular BLE from local scanner
        if self.scanner:
            found = self.scanner.get_recent_devices(seconds=30)
            for d in found:
                results.append({
                    'type': 'ble',
                    'identifier': d['mac'],
                    'mac': d['mac'],
                    'name': d.get('name', 'Unknown'),
                    'rssi': d.get('rssi', -100),
                    'tracked': d['mac'].upper() in known_identifiers
                })
        
        return json.dumps({"results": results})

    def manage_satellites(self):
        satellites = self.config_mgr.load_satellites()
        
        import time
        now = time.time()
        for sid, info in satellites.items():
            last = info.get('last_seen', 0)
            diff = int(now - last)
            if diff < 60:
                info['last_seen_fmt'] = f"Just now ({diff}s ago)"
            elif diff < 3600:
                info['last_seen_fmt'] = f"{diff//60}m ago"
            else:
                info['last_seen_fmt'] = f"{diff//3600}h ago"
                
        return render_template('satellites.html', satellites=satellites)

    def update_satellite(self):
        sats = self.config_mgr.load_satellites()
        updated = False
        
        for sid in sats.keys():
            room = request.form.get(f'room_{sid}', '').strip()
            x = request.form.get(f'x_{sid}', '0')
            y = request.form.get(f'y_{sid}', '0')
            
            if room:
                sats[sid]['room'] = room
                try:
                    sats[sid]['x'] = float(x)
                    sats[sid]['y'] = float(y)
                    updated = True
                except ValueError:
                    pass
        
        if updated:
            self.config_mgr.save_satellites(sats)
            flash("Configuration saved")
        else:
            flash("No changes saved")
        
        return redirect(url_for('manage_satellites'))

    def update_satellite_ref(self):
        sid = request.form.get('satellite_id')
        ref = request.form.get('ref_rssi')
        
        if sid and ref:
            sats = self.config_mgr.load_satellites()
            if sid in sats:
                try:
                    sats[sid]['ref_rssi_1m'] = int(float(ref))
                    self.config_mgr.save_satellites(sats)
                    flash(f"Calibrated {sid} reference RSSI to {ref} dBm")
                except ValueError:
                    flash("Invalid RSSI value")
            else:
                flash("Satellite not found")
        return redirect(url_for('manage_satellites'))

    # Calibration State
    _calib_sessions = {}

    def calibrate_satellite(self):
        sid = request.args.get('satellite')
        action = request.args.get('action')
        
        if not sid: 
            return json.dumps({'error': 'No satellite ID'})

        import time
        now = time.time()
        
        if action == 'start':
            self._calib_sessions[sid] = {'start': now, 'readings': []}
            return json.dumps({'status': 'started', 'satellite': sid})
            
        elif action == 'status':
            session = self._calib_sessions.get(sid)
            if not session:
                return json.dumps({'error': 'No session'})
            
            elapsed = now - session['start']
            
            last_rssi = None
            if self.tracker:
                sig_data = getattr(self.tracker, 'last_sat_signals', {}).get(sid)
                if sig_data and (now - sig_data['time']) < 3:
                    last_rssi = sig_data['rssi']
                    session['readings'].append(last_rssi)

            # Logic
            import statistics
            is_stable = False
            progress = 0
            count = len(session['readings'])
            
            if count >= 30:
                std_dev = statistics.stdev(session['readings'][-30:])
                if std_dev < 2.0 and elapsed > 15:
                    is_stable = True
            
            if elapsed >= 45:
                is_stable = True
                
            progress = min(99, int((elapsed / 25.0) * 100))
            if is_stable: progress = 100

            avg_rssi = -100
            if progress == 100 and count > 10:
                vals = sorted(session['readings'])
                trim = max(1, int(len(vals) * 0.1))
                trimmed_vals = vals[trim:-trim]
                if trimmed_vals:
                    avg_rssi = sum(trimmed_vals) / len(trimmed_vals)
            elif count > 0:
                avg_rssi = sum(session['readings']) / count
            
            return json.dumps({
                'progress': int(progress),
                'last_rssi': last_rssi,
                'avg_rssi': avg_rssi,
                'count': count,
                'stable': is_stable
            })
            
        return json.dumps({'error': 'Invalid action'})

    def view_logs(self):
        log_content = ""
        try:
             # Try home dir first as per deployment (nohup)
             with open('/home/rpi/gatekeeper.log', 'r') as f:
                 lines = f.readlines()
                 log_content = "".join(lines[-200:])
        except:
            log_content = "Log file not found or unreadable."
            
        return render_template('logs.html', logs=log_content) # Consistent var name

    def restart_service(self):
        flash('Restart triggered (Not implemented in Thread mode yet)')
        return redirect(url_for('dashboard'))
