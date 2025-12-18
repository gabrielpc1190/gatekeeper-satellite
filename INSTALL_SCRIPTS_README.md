# 🚀 Gatekeeper NG - Installation Scripts

Quick reference for installing and deploying Gatekeeper NG.

---

## 📦 Installation Scripts

### `install.sh` - Main Installation Script
**Purpose**: Automated installation on Raspberry Pi  
**Run on**: Raspberry Pi (via SSH or direct)

```bash
# Transfer to RPi
scp -r gatekeeper_ng install.sh rpi@172.16.9.20:~/

# SSH to RPi
ssh rpi@172.16.9.20

# Run installation
chmod +x install.sh
bash install.sh
```

**What it does**:
- ✅ Checks platform and dependencies
- ✅ Installs Python packages
- ✅ Creates systemd service
- ✅ Configures Bluetooth
- ✅ Sets up directory structure
- ✅ Prompts to start service

---

### `configure.sh` - Interactive Configuration Wizard
**Purpose**: Easy configuration management  
**Run on**: Raspberry Pi

```bash
chmod +x configure.sh
bash configure.sh
```

**Features**:
- **MQTT Configuration**: Set broker IP, port, credentials
- **Device Management**: Add/remove/list tracked devices
- **System Settings**: Timeout, Home Assistant integration
- **Connection Testing**: Verify MQTT connectivity

**Menu Options**:
1. Configure MQTT Broker
2. Add Device (with MAC validation)
3. List Devices
4. Remove Device
5. Configure Settings
6. Test MQTT Connection
7. Exit

---

### `deploy.sh` - Remote Deployment Script
**Purpose**: Push updates from local machine to RPi  
**Run on**: Local development machine

```bash
chmod +x deploy.sh
bash deploy.sh
```

**What it does**:
1. Creates deployment package (tar.gz)
2. Stops running service on RPi
3. Backs up existing configuration
4. Uploads new code via SCP
5. Restores configuration
6. Restarts service
7. Verifies deployment

**Interactive prompts**:
- Raspberry Pi IP address
- SSH password

---

## 🎯 Quick Start

### Option 1: Fresh Install

```bash
# 1. Clone/download project
cd /path/to/gatekeeper_project

# 2. Transfer to RPi
scp -r gatekeeper_ng install.sh configure.sh rpi@172.16.9.20:~/

# 3. SSH to RPi
ssh rpi@172.16.9.20

# 4. Install
bash install.sh

# 5. Configure
bash configure.sh

# 6. Start service
sudo systemctl start gatekeeper
sudo systemctl enable gatekeeper

# 7. Access dashboard
# Open browser: http://172.16.9.20/
```

### Option 2: Remote Deploy (for updates)

```bash
# 1. On local machine
cd /path/to/gatekeeper_project

# 2. Deploy
bash deploy.sh

# 3. Enter RPi IP and password when prompted
```

---

## 📋 Prerequisites

### On Raspberry Pi:
- Raspberry Pi OS (Debian-based)
- Python 3.7+
- Bluetooth hardware
- SSH access (for remote deployment)
- Internet connection

### On Local Machine (for deploy.sh):
- `sshpass` installed
  ```bash
  # Ubuntu/Debian
  sudo apt-get install sshpass
  
  # macOS
  brew install hudochenkov/sshpass/sshpass
  ```

---

## �� Configuration Files

After installation, configuration files are created in:
```
/home/rpi/gatekeeper_ng/config/
├── mqtt.json          # MQTT broker settings
├── devices.json       # Tracked devices
├── satellites.json    # Satellite assignments (auto)
└── settings.json      # System preferences
```

### Example Configurations

**mqtt.json**:
```json
{
    "broker": "172.16.10.12",
    "port": 1883,
    "user": "gatekeeper_pi",
    "password": "gatekeeper_pi",
    "topic_prefix": "gatekeeper"
}
```

**devices.json** (managed via web UI or configure.sh):
```json
[
    {
        "mac": "AA:BB:CC:DD:EE:FF",
        "alias": "My-iPhone",
        "type": "Phone"
    }
]
```

---

## 🔧 Post-Installation

### Verify Installation
```bash
# Check service status
sudo systemctl status gatekeeper

# View logs
sudo journalctl -u gatekeeper -f

# Test web interface
curl http://localhost/
```

### Access Points
- **Dashboard**: http://172.16.9.20/
- **Devices**: http://172.16.9.20/devices
- **Satellites**: http://172.16.9.20/satellites
- **MQTT Config**: http://172.16.9.20/mqtt
- **Settings**: http://172.16.9.20/preferences

---

## 🐛 Troubleshooting

### Installation Failed

**Check logs**:
```bash
# During installation
tail -50 ~/install.log

# After service start
sudo journalctl -u gatekeeper -n 50
```

**Common Issues**:

1. **Python packages failed**:
   ```bash
   sudo pip3 install flask paho-mqtt bleak --break-system-packages
   ```

2. **Bluetooth permission denied**:
   ```bash
   sudo systemctl restart bluetooth
   sudo usermod -aG bluetooth rpi
   ```

3. **Port 80 in use**:
   ```bash
   sudo netstat -tlnp | grep :80
   sudo kill -9 <PID>
   ```

### Deployment Failed

1. **SSH connection refused**:
   - Verify RPi IP address
   - Check SSH is enabled: `sudo systemctl status ssh`

2. **Permission denied**:
   - Verify SSH password
   - Check user has sudo rights

3. **sshpass not found**:
   ```bash
   sudo apt-get install sshpass
   ```

---

## 📚 Additional Documentation

- **Complete Installation Guide**: See [INSTALL_GUIDE.md](INSTALL_GUIDE.md)
- **System Architecture**: See [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)
- **Deployment History**: See [DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md)
- **All Documentation**: See [INDEX.md](INDEX.md)

---

## 🔄 Updating Gatekeeper

### Method 1: Remote Deploy (Easiest)
```bash
bash deploy.sh
```

### Method 2: Manual
```bash
# On RPi
sudo systemctl stop gatekeeper
cd ~/gatekeeper_ng
git pull  # or manual file copy
sudo systemctl start gatekeeper
```

---

## 🗑️ Uninstalling

```bash
# Stop and disable
sudo systemctl stop gatekeeper
sudo systemctl disable gatekeeper

# Remove service
sudo rm /etc/systemd/system/gatekeeper.service
sudo systemctl daemon-reload

# Remove code
rm -rf /home/rpi/gatekeeper_ng

# (Optional) Remove dependencies
sudo pip3 uninstall flask paho-mqtt bleak
```

---

## 📝 Service Management

```bash
# Start
sudo systemctl start gatekeeper

# Stop
sudo systemctl stop gatekeeper

# Restart
sudo systemctl restart gatekeeper

# View status
sudo systemctl status gatekeeper

# Enable auto-start
sudo systemctl enable gatekeeper

# Disable auto-start
sudo systemctl disable gatekeeper

# View logs (real-time)
sudo journalctl -u gatekeeper -f

# View last 100 lines
sudo journalctl -u gatekeeper -n 100
```

---

## ⚙️ Advanced Configuration

### Change Web Port

Edit `/etc/systemd/system/gatekeeper.service`:
```ini
[Service]
Environment="GATEKEEPER_PORT=8080"
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gatekeeper
```

### Run as Non-Root User

**Note**: BLE scanning requires elevated privileges. Use at your own risk.

Edit `/etc/systemd/system/gatekeeper.service`:
```ini
[Service]
User=rpi
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
```

---

## 🎯 Quick Commands Reference

| Task | Command |
|------|---------|
| Install | `bash install.sh` |
| Configure | `bash configure.sh` |
| Deploy | `bash deploy.sh` |
| Start | `sudo systemctl start gatekeeper` |
| Stop | `sudo systemctl stop gatekeeper` |
| Restart | `sudo systemctl restart gatekeeper` |
| Status | `sudo systemctl status gatekeeper` |
| Logs | `sudo journalctl -u gatekeeper -f` |
| Dashboard | http://172.16.9.20/ |

---

**Created**: 2025-12-18  
**Version**: 1.0  
**Status**: Production Ready ✅
