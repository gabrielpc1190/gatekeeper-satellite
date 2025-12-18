# Gatekeeper NG - Installation Guide

## 📦 Installation Methods

There are three ways to install Gatekeeper NG on your Raspberry Pi:

1. **Automated Installation** (Recommended)
2. **Remote Deployment** (For updates)
3. **Manual Installation** (For advanced users)

---

## Method 1: Automated Installation (Recommended)

### Prerequisites
- Raspberry Pi with Raspberry Pi OS
- Internet connection
- SSH access or direct terminal access

### Steps

1. **Transfer files to Raspberry Pi**:
   ```bash
   # On your local machine
   scp -r gatekeeper_ng install.sh configure.sh rpi@172.16.9.20:~/
   ```

2. **SSH into Raspberry Pi**:
   ```bash
   ssh rpi@172.16.9.20
   ```

3. **Make scripts executable**:
   ```bash
   chmod +x install.sh configure.sh
   ```

4. **Run installation script**:
   ```bash
   bash install.sh
   ```

5. **Configure the system**:
   ```bash
   bash configure.sh
   ```
   
   The wizard will guide you through:
   - MQTT broker settings
   - Adding tracked devices
   - System preferences

6. **Start the service**:
   ```bash
   sudo systemctl start gatekeeper
   sudo systemctl enable gatekeeper  # Enable on boot
   ```

7. **Verify installation**:
   ```bash
   sudo systemctl status gatekeeper
   ```
   
   Access dashboard: `http://172.16.9.20/`

---

## Method 2: Remote Deployment

Perfect for updating an existing installation.

### Prerequisites
- `sshpass` installed on local machine
- SSH access to Raspberry Pi

### Steps

1. **On your local machine**, run:
   ```bash
   chmod +x deploy.sh
   bash deploy.sh
   ```

2. **Enter when prompted**:
   - Raspberry Pi IP address
   - Password

3. **Script will automatically**:
   - Stop running service
   - Backup configuration
   - Upload new code
   - Restart service

---

## Method 3: Manual Installation

### 1. Copy Files
```bash
scp -r gatekeeper_ng rpi@172.16.9.20:/home/rpi/
ssh rpi@172.16.9.20
```

### 2. Install Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev bluetooth bluez bluez-tools libbluetooth-dev
sudo pip3 install flask paho-mqtt bleak --break-system-packages
```

### 3. Create Configuration

**MQTT (`/home/rpi/gatekeeper_ng/config/mqtt.json`)**:
```json
{
    "broker": "172.16.10.12",
    "port": 1883,
    "user": "gatekeeper_pi",
    "password": "gatekeeper_pi",
    "topic_prefix": "gatekeeper"
}
```

**Devices (`/home/rpi/gatekeeper_ng/config/devices.json`)**:
```json
[
    {
        "mac": "AA:BB:CC:DD:EE:FF",
        "alias": "My-Phone",
        "type": "Phone"
    }
]
```

**Settings (`/home/rpi/gatekeeper_ng/config/settings.json`)**:
```json
{
    "PREF_BEACON_EXPIRATION": "60",
    "PREF_DEVICE_TRACKER_REPORT": "true"
}
```

### 4. Create Systemd Service

Create `/etc/systemd/system/gatekeeper.service`:
```ini
[Unit]
Description=Gatekeeper NG - Bluetooth Presence Detection
After=network.target bluetooth.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/rpi/gatekeeper_ng
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 /home/rpi/gatekeeper_ng/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW

[Install]
WantedBy=multi-user.target
```

### 5. Enable and Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable gatekeeper
sudo systemctl start gatekeeper
```

---

## Post-Installation

### 1. Verify Service Status
```bash
sudo systemctl status gatekeeper
```

Expected output:
```
● gatekeeper.service - Gatekeeper NG
   Active: active (running) since...
```

### 2. View Logs
```bash
# Real-time logs
sudo journalctl -u gatekeeper -f

# Last 50 lines
sudo journalctl -u gatekeeper -n 50
```

### 3. Access Web Dashboard
Open browser: `http://172.16.9.20/`

### 4. Add Devices
- Go to http://172.16.9.20/devices
- Click "Add Device"
- Enter MAC address and name

### 5. Configure Satellites
- Flash satellites using ESPHome (see `ESPHOME_FLASH_GUIDE.md`)
- Go to http://172.16.9.20/satellites
- Assign each satellite to a room

---

## Troubleshooting

### Service Won't Start

**Check logs**:
```bash
sudo journalctl -u gatekeeper -n 50 --no-pager
```

**Common issues**:
1. **Port 80 in use**:
   ```bash
   sudo netstat -tlnp | grep :80
   sudo kill -9 <PID>
   ```

2. **MQTT connection failed**:
   - Verify broker IP in `/home/rpi/gatekeeper_ng/config/mqtt.json`
   - Test connection:
     ```bash
     mosquitto_pub -h 172.16.10.12 -u gatekeeper_pi -P gatekeeper_pi -t test -m test
     ```

3. **Bluetooth errors**:
   ```bash
   sudo systemctl status bluetooth
   sudo systemctl restart bluetooth
   ```

### Dashboard Not Loading

1. **Check if service is running**:
   ```bash
   systemctl is-active gatekeeper
   ```

2. **Check Flask is listening**:
   ```bash
   sudo netstat -tlnp | grep :80
   ```

3. **Try accessing locally**:
   ```bash
   curl http://localhost/
   ```

### Satellites Not Appearing

1. **Verify MQTT topic**:
   ```bash
   mosquitto_sub -h 172.16.10.12 -u gatekeeper_pi -P gatekeeper_pi \
     -t 'gatekeeper/satellite/#' -v
   ```

2. **Check satellite firmware**:
   - Verify `mqtt_broker` in `satX.yaml` is correct
   - Verify satellites are online (ping their IPs)

3. **Check Gatekeeper logs**:
   ```bash
   sudo journalctl -u gatekeeper -f | grep -i satellite
   ```

### Home Assistant Not Detecting

1. **Check MQTT Discovery**:
   ```bash
   mosquitto_sub -h 172.16.10.12 -u gatekeeper_pi -P gatekeeper_pi \
     -t 'homeassistant/device_tracker/#' -v
   ```

2. **Restart Gatekeeper** to re-send discovery:
   ```bash
   sudo systemctl restart gatekeeper
   ```

3. **Wait 5-10 minutes** for Home Assistant to process

---

## Updating Gatekeeper

### Option 1: Using Deploy Script
```bash
# On local machine
bash deploy.sh
```

### Option 2: Manual Update
```bash
ssh rpi@172.16.9.20
cd ~

# Backup config
cp -r gatekeeper_ng/config ~/config_backup

# Stop service
sudo systemctl stop gatekeeper

# Upload new code (from local machine)
scp -r gatekeeper_ng rpi@172.16.9.20:~/gatekeeper_ng_new

# Replace code (on RPi)
rm -rf gatekeeper_ng_old
mv gatekeeper_ng gatekeeper_ng_old
mv gatekeeper_ng_new gatekeeper_ng

# Restore config
cp -r ~/config_backup gatekeeper_ng/config

# Restart
sudo systemctl start gatekeeper
```

---

## Uninstalling

```bash
# Stop and disable service
sudo systemctl stop gatekeeper
sudo systemctl disable gatekeeper

# Remove service file
sudo rm /etc/systemd/system/gatekeeper.service
sudo systemctl daemon-reload

# Remove code
rm -rf /home/rpi/gatekeeper_ng

# Remove dependencies (optional)
sudo pip3 uninstall flask paho-mqtt bleak
```

---

## Configuration Files Reference

### Directory Structure
```
/home/rpi/gatekeeper_ng/
├── main.py                 # Entry point
├── app/                    # Core application
│   ├── core.py
│   ├── tracker.py
│   ├── mqtt_client.py
│   ├── ble_scanner.py
│   └── config_mgr.py
├── admin/                  # Web interface
│   ├── server.py
│   └── templates/
└── config/                 # Configuration (gitignored)
    ├── mqtt.json          # MQTT broker settings
    ├── devices.json       # Tracked devices
    ├── satellites.json    # Satellite assignments
    └── settings.json      # System preferences
```

### Configuration Files

**mqtt.json**:
```json
{
    "broker": "IP_ADDRESS",
    "port": 1883,
    "user": "username",
    "password": "password",
    "topic_prefix": "gatekeeper"
}
```

**devices.json**:
```json
[
    {
        "mac": "AA:BB:CC:DD:EE:FF",
        "alias": "Device-Name",
        "type": "Phone|Laptop|Watch|Tablet|Other"
    }
]
```

**satellites.json** (auto-populated):
```json
{
    "gatekeeper-xiao-1": {
        "name": "gatekeeper-xiao-1",
        "room": "Living Room",
        "last_seen": 1702819200
    }
}
```

**settings.json**:
```json
{
    "PREF_BEACON_EXPIRATION": "60",
    "PREF_DEVICE_TRACKER_REPORT": "true"
}
```

---

## Service Management

### Start/Stop/Restart
```bash
sudo systemctl start gatekeeper
sudo systemctl stop gatekeeper
sudo systemctl restart gatekeeper
```

### Enable/Disable Auto-start
```bash
sudo systemctl enable gatekeeper   # Start on boot
sudo systemctl disable gatekeeper  # Don't start on boot
```

### View Status
```bash
sudo systemctl status gatekeeper
```

### View Logs
```bash
# Real-time
sudo journalctl -u gatekeeper -f

# Last N lines
sudo journalctl -u gatekeeper -n 100

# Since boot
sudo journalctl -u gatekeeper -b

# Today's logs
sudo journalctl -u gatekeeper --since today
```

---

## Performance Tuning

### Reduce Logging
Edit `/etc/systemd/system/gatekeeper.service`:
```ini
# Change:
StandardOutput=journal
StandardError=journal

# To:
StandardOutput=null
StandardError=journal
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart gatekeeper`

### Adjust Timeout
Edit `/home/rpi/gatekeeper_ng/config/settings.json`:
```json
{
    "PREF_BEACON_EXPIRATION": "30"  // Lower = faster away detection
}
```

### Increase Scan Freq (Satellites)
Edit satellite YAML files and reflash:
```yaml
esp32_ble_tracker:
  scan_parameters:
    interval: 1100ms  # Lower = more frequent (higher battery/CPU)
```

---

## Getting Help

- **Documentation**: See `INDEX.md` for all docs
- **Common Issues**: Check `DEPLOYMENT_LOG.md`
- **Architecture**: See `SYSTEM_OVERVIEW.md`
- **Satellite Flashing**: See `ESPHOME_FLASH_GUIDE.md`

**Log Files**:
- Service: `sudo journalctl -u gatekeeper -f`
- Manual run: `~/gatekeeper.log` (if run manually)

---

**Installation Status**: Ready to deploy  
**Last Updated**: 2025-12-18
