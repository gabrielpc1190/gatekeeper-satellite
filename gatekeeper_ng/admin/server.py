from flask import Flask, render_template, request, redirect, url_for, flash
import logging
import os
import json
import threading
import time

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
        self.app.add_url_rule('/api/devices', 'api_devices', self.api_devices)
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
        self.app.add_url_rule('/bluetooth/clear', 'bluetooth_clear', self.bluetooth_clear, methods=['POST'])
        self.app.add_url_rule('/satellites', 'manage_satellites', self.manage_satellites)
        self.app.add_url_rule('/satellites/update', 'update_satellite', self.update_satellite, methods=['POST'])
        self.app.add_url_rule('/satellites/calibrate', 'calibrate_satellite', self.calibrate_satellite, methods=['GET'])
        self.app.add_url_rule('/satellites/update_ref', 'update_satellite_ref', self.update_satellite_ref, methods=['POST'])
        self.app.add_url_rule('/api/satellites', 'api_satellites', self.api_satellites)
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
        
    def api_devices(self):
        """API Endpoint for Real-time Dashboard Updates"""
        devices = self.config_mgr.load_devices()
        result = []
        
        if self.tracker:
            now = time.time()
            for d in devices:
                key = d.get('identifier', d.get('mac'))
                if d.get('identifier_type') == 'mac' or not d.get('identifier_type'):
                     key = key.upper()
                     
                state = self.tracker.current_state.get(key)
                
                item = {
                    'alias': d['alias'],
                    'mac': d.get('mac', key),
                    'room': 'Unknown',
                    'distance': '-',
                    'last_seen_fmt': 'No data',
                    'present': False
                }
                
                if state:
                    item['room'] = state.get('room', 'Unknown')
                    
                    dist = state.get('distance', -1)
                    if dist > 0:
                        item['distance'] = f"{dist}m"
                    
                    if state.get('present'):
                        seen = state.get('last_seen')
                        item['present'] = True
                        item['last_seen_fmt'] = f"{int(now - seen)}s ago" if seen else "Just now"
                    else:
                        last = state.get('last_seen', 0)
                        diff = int(now - last)
                        if diff > 86400: item['last_seen_fmt'] = f"{diff // 86400}d ago"
                        elif diff > 3600: item['last_seen_fmt'] = f"{diff // 3600}h ago"
                        else: item['last_seen_fmt'] = f"{diff // 60}m ago"
                        
                result.append(item)
                
        return json.dumps(result)

    def dashboard(self):
        # We render the template with initial data, JS handles polling
        return render_template('dashboard.html', 
                             service_active=True)

    def manage_devices(self):
        devices = self.config_mgr.load_devices()
        return render_template('devices.html', devices=devices)

    def add_device(self):
        identifier = request.form.get('identifier', '').strip()
        identifier_type = request.form.get('identifier_type', 'mac')  # 'mac' or 'uuid'
        alias = request.form.get('alias', '').strip()
        dev_type = request.form.get('type', 'Phone' if identifier_type == 'uuid' else 'Bluetooth')
        
        # Fallback for old forms
        if not identifier:
            identifier = request.form.get('mac', '').strip()
            identifier_type = 'mac'
            
        if identifier_type == 'mac':
            identifier = identifier.upper()

        self.logger.info(f"Adding device request: {identifier} ({alias})")
        
        if identifier and alias:
            devices = self.config_mgr.load_devices()
            # Check for duplicates
            for d in devices:
                existing = d.get('identifier', d.get('mac', '')).strip().upper()
                if existing == identifier:
                    self.logger.warning(f"Device {identifier} already exists")
                    flash('Device already exists')
                    return redirect(url_for('manage_devices'))
            
            new_device = {
                'identifier': identifier,
                'identifier_type': identifier_type,
                'alias': alias,
                'type': dev_type
            }
            
            devices.append(new_device)
            self.config_mgr.save_devices(devices)
            
            if self.tracker:
                self.tracker.reload_config()
            
            self.logger.info(f"Successfully added device {alias}")
            flash(f'Added {alias}')
        else:
             flash('Missing identifier or alias')
        
        return redirect(url_for('manage_devices'))

    def delete_device(self):
        target = request.form.get('identifier', request.form.get('mac', '')).strip()
        self.logger.info(f"Request to delete device: {target}")
        
        if not target:
             flash('No device specified')
             return redirect(url_for('manage_devices'))

        devices = self.config_mgr.load_devices()
        initial_count = len(devices)
        
        # Filter out the device (case insensitive check)
        new_list = [d for d in devices if d.get('identifier', d.get('mac', '')).strip().upper() != target.upper()]
        
        if len(new_list) < initial_count:
            self.config_mgr.save_devices(new_list)
            if self.tracker:
                self.tracker.reload_config()
            self.logger.info(f"Deleted device {target}")
            flash('Device deleted')
        else:
            self.logger.warning(f"Device {target} not found for deletion")
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
            
        if id_type == 'mac':
            new_id = new_id.upper()

        self.logger.info(f"Editing device {original_id} -> {new_id} ({new_alias})")

        devices = self.config_mgr.load_devices()
        updated = False
        for i, d in enumerate(devices):
            ident = d.get('identifier', d.get('mac', '')).strip()
            if ident.upper() == original_id.upper():
                devices[i] = {
                    'identifier': new_id,
                    'identifier_type': id_type,
                    'alias': new_alias,
                    'type': new_type
                }
                updated = True
                break
        
        if updated:
            self.config_mgr.save_devices(devices)
            if self.tracker:
                self.tracker.reload_config()
            self.logger.info(f"Successfully updated {new_alias}")
            flash(f'Updated {new_alias}')
        else:
            self.logger.warning(f"Could not find device {original_id} to update")
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
        
        mqtt_file = self.config_mgr.mqtt_file
        try:
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
        new_prefs = {k: v for k, v in request.form.items()}
        if 'PREF_DEVICE_TRACKER_REPORT' not in new_prefs: new_prefs['PREF_DEVICE_TRACKER_REPORT'] = 'false'
        if 'PREF_ENABLE_LOGGING' not in new_prefs: new_prefs['PREF_ENABLE_LOGGING'] = 'false'
        
        self.config_mgr.save_settings(new_prefs)
        
        if self.tracker:
            self.tracker.reload_config()
            
        flash('Preferences Saved.')
        return redirect(url_for('manage_preferences'))

    def bluetooth_tools(self):
        satellites = self.config_mgr.load_satellites()
        # Add the Hub as a virtual satellite for the UI
        sat_list = [{"id": "gatekeeper-hub", "name": "SalaTV-Cocina"}]
        for sid, sdata in satellites.items():
            sat_list.append({"id": sid, "name": sdata.get('room', sid)})
        return render_template('bluetooth.html', scan_results=[], satellites=sat_list)
    
    def bluetooth_scan_api(self):
        known_identifiers = set()
        if self.config_mgr:
            devices = self.config_mgr.load_devices()
            for d in devices:
                ident = d.get('identifier', d.get('mac', '')).strip()
                if d.get('identifier_type') == 'mac' or not d.get('identifier_type'):
                    known_identifiers.add(ident.upper())
                else:
                    known_identifiers.add(ident)
        
        # Load satellite mapping for room names
        satellites = self.config_mgr.load_satellites()
        
        results = []
        now = time.time()
        
        # 1. From Discovery Cache (Satellites + Hub)
        if self.tracker and hasattr(self.tracker, 'discovery_cache'):
            for ident, data in list(self.tracker.discovery_cache.items()):
                if now - data.get('last_seen', 0) < 60:
                    is_ibeacon = '-' in ident and len(ident) == 36
                    
                    # Convert satellite IDs to Names + RSSI
                    raw_sources = data.get('sources', {}) # Dict {sid: rssi}
                    named_sources_detailed = []
                    for sid, srssi in raw_sources.items():
                        if sid == 'gatekeeper-hub':
                            name = 'SalaTV-Cocina'
                            source_id = 'gatekeeper-hub'
                        else:
                            name = satellites.get(sid, {}).get('room', sid)
                            source_id = sid
                        named_sources_detailed.append({
                            'id': source_id,
                            'name': name, 
                            'rssi': srssi
                        })
                            
                    results.append({
                        'type': 'ibeacon' if is_ibeacon else 'ble',
                        'identifier': ident,
                        'uuid_short': ident[:8] + '...' + ident[-4:] if is_ibeacon else ident,
                        'uuid_full': ident if is_ibeacon else ident,
                        'mac': ident if not is_ibeacon else None,
                        'rssi': data.get('rssi', -100),
                        'major': data.get('major'),
                        'minor': data.get('minor'),
                        'name': data.get('name') or (f"iBeacon {data.get('major')}/{data.get('minor')}" if is_ibeacon else "Unknown"),
                        'tracked': ident.upper() in known_identifiers if not is_ibeacon else ident in known_identifiers,
                        'sources_detailed': named_sources_detailed
                    })
        
        # 2. Add anything from local scanner that might be missing
        if self.scanner:
            found = self.scanner.get_recent_devices(seconds=30)
            seen_idents = {r['identifier'] for r in results}
            for d in found:
                if d['mac'] not in seen_idents:
                    results.append({
                        'type': 'ble',
                        'identifier': d['mac'],
                        'mac': d['mac'],
                        'name': d.get('name', 'Unknown'),
                        'rssi': d.get('rssi', -100),
                        'tracked': d['mac'].upper() in known_identifiers,
                        'sources_detailed': [{'id': 'gatekeeper-hub', 'name': 'SalaTV-Cocina', 'rssi': d.get('rssi', -100)}]
                    })
        
        # Sort by RSSI Descending (Strongest first)
        results.sort(key=lambda x: x.get('rssi', -100), reverse=True)
        
        return json.dumps({"results": results})

    def bluetooth_clear(self):
        if self.tracker:
            self.tracker.clear_discovery_cache()
        return json.dumps({"status": "cleared"})

    def manage_satellites(self):
        satellites = self.config_mgr.load_satellites()
        now = time.time()
        for sid, info in satellites.items():
            # Add health stats if available
            stats = self.tracker.satellite_stats.get(sid, {})
            info['wifi_signal'] = stats.get('wifi_signal', '--')
            info['wifi_signal'] = stats.get('wifi_signal', '--')
            
            raw_uptime = stats.get('uptime', 0)
            info['uptime'] = raw_uptime
            
            try:
                up_sec = float(raw_uptime)
                if up_sec < 60:
                    info['uptime_fmt'] = f"{int(up_sec)}s"
                elif up_sec < 3600:
                    info['uptime_fmt'] = f"{int(up_sec/60)}m"
                elif up_sec < 86400:
                    info['uptime_fmt'] = f"{int(up_sec/3600)}h {int((up_sec%3600)/60)}m"
                else:
                    info['uptime_fmt'] = f"{int(up_sec/86400)}d {int((up_sec%86400)/3600)}h"
            except (ValueError, TypeError):
                info['uptime_fmt'] = "--"
            
            last = info.get('last_seen', 0)
            diff = int(now - last)
            if diff < 60:
                info['last_seen_fmt'] = f"Just now ({diff}s ago)"
            elif diff < 3600:
                info['last_seen_fmt'] = f"{diff//60}m ago"
            else:
                info['last_seen_fmt'] = f"{diff//3600}h ago"
                
        return render_template('satellites.html', satellites=satellites)

    def api_satellites(self):
        """API Endpoint for Real-time Satellite Stats"""
        satellites = self.config_mgr.load_satellites()
        now = time.time()
        results = {}
        
        for sid, info in satellites.items():
            # Get fresh stats from memory
            stats = self.tracker.satellite_stats.get(sid, {})
            
            # Format Uptime
            raw_uptime = stats.get('uptime', 0)
            uptime_fmt = "--"
            try:
                up_sec = float(raw_uptime)
                if up_sec < 60: uptime_fmt = f"{int(up_sec)}s"
                elif up_sec < 3600: uptime_fmt = f"{int(up_sec/60)}m"
                elif up_sec < 86400: uptime_fmt = f"{int(up_sec/3600)}h {int((up_sec%3600)/60)}m"
                else: uptime_fmt = f"{int(up_sec/86400)}d {int((up_sec%86400)/3600)}h"
            except: pass
            
            # Format Last Seen
            last = info.get('last_seen', 0)
            diff = int(now - last)
            if diff < 60: last_seen_fmt = f"Just now ({diff}s ago)"
            elif diff < 3600: last_seen_fmt = f"{diff//60}m ago"
            else: last_seen_fmt = f"{diff//3600}h ago"
            
            results[sid] = {
                'wifi_signal': stats.get('wifi_signal', '--'),
                'uptime_fmt': uptime_fmt,
                'last_seen_fmt': last_seen_fmt,
                'is_online': diff < 60 # Flag for UI highlighting
            }
            
        return json.dumps(results)

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
                # Allow data up to 10s old (Satellite keepalive is 5s)
                if sig_data and (now - sig_data['time']) < 10:
                    last_rssi = sig_data['rssi']
                    session['readings'].append(last_rssi)

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
             with open('/home/rpi/gatekeeper.log', 'r') as f:
                 lines = f.readlines()
                 # Filter out noisy werkzeug logs for the UI
                 filtered_lines = [line for line in lines if "[werkzeug]" not in line]
                 log_content = "".join(filtered_lines[-200:])
        except:
            log_content = "Log file not found or unreadable."
            
        return render_template('logs.html', logs=log_content)

    def restart_service(self):
        flash('Restart triggered (Not implemented in Thread mode yet)')
        return redirect(url_for('dashboard'))
