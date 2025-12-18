# ESPHome Flashing Guide for Gatekeeper Satellites

## Problem Overview
ESPHome uses PlatformIO as its build system, which creates internal Python virtual environments (`penv`) to manage dependencies. On modern Linux distributions with Python 3.11+, the system Python is "externally managed" which can cause conflicts with PlatformIO's dependency installation process.

## Common Errors Encountered

### Error 1: "externally-managed-environment"
```
error: externally-managed-environment
× This environment is externally managed
```

### Error 2: "uv installation via pip failed"
```
Error: uv installation via pip failed with exit code 1
Error: Failed to install Python dependencies into penv
```

## Solution: Proper Virtual Environment Setup

### Step 1: Create a Dedicated Virtual Environment
```bash
cd /root/.gemini/antigravity/scratch/gatekeeper_project
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install ESPHome and Dependencies
```bash
pip install esphome
pip install uv  # PlatformIO's package installer
```

### Step 3: Clear PlatformIO's Cache (If Issues Persist)
PlatformIO maintains its own environment that may become corrupted:

```bash
# Clear PlatformIO's internal Python environment
rm -rf ~/.platformio/penv

# Optional: Full reset (removes all PlatformIO packages)
# rm -rf ~/.platformio
```

### Step 4: Remove System Python Protection (LXC/Container Only)
**WARNING: Only do this in containers/LXC, NOT on production systems**

```bash
# This allows PlatformIO's internal tooling to install packages
rm /usr/lib/python3.*/EXTERNALLY-MANAGED
```

### Step 5: Flash the Device
```bash
# Activate venv if not already active
source venv/bin/activate

# Flash the satellite
esphome run sat1.yaml --device /dev/ttyACM0
```

## Alternative: Use Docker (Recommended for Production)
ESPHome officially supports Docker which avoids all Python environment issues:

```bash
docker run --rm -v "${PWD}":/config --device=/dev/ttyACM0 \
  -it ghcr.io/esphome/esphome run sat1.yaml
```

## Troubleshooting

### Issue: Device Not Detected
```bash
# Check if device is connected
ls -l /dev/ttyACM*
ls -l /dev/ttyUSB*

# Add user to dialout group (may require logout)
sudo usermod -a -G dialout $USER
```

### Issue: Permission Denied on /dev/ttyACM0
```bash
# Temporary fix
sudo chmod 666 /dev/ttyACM0

# Permanent fix: udev rule
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", MODE="0666"' | \
  sudo tee /etc/udev/rules.d/99-esp32.rules
sudo udevadm control --reload-rules
```

### Issue: Compilation Takes Too Long
First compilation can take 10-15 minutes. Subsequent builds are much faster due to caching.

```bash
# Monitor progress with logs
esphome run sat1.yaml --device /dev/ttyACM0
```

### Issue: OTA Updates Not Working
After initial flash via USB, you can update Over-The-Air (faster):

```bash
# Update via WiFi (device must be on network)
esphome run sat1.yaml
```

## Environment Variables Reference

Useful environment variables for debugging:

```bash
# Allow system package installation (use with caution)
export PIP_BREAK_SYSTEM_PACKAGES=1

# Increase verbosity
export PLATFORMIO_LOG_LEVEL=DEBUG

# Use specific Python version
export PLATFORMIO_PIOENV_DIR=/path/to/custom/penv
```

## Quick Reference: Flash All Three Satellites

```bash
cd /root/.gemini/antigravity/scratch/gatekeeper_project
source venv/bin/activate

# Flash Satellite 1
esphome run sat1.yaml --device /dev/ttyACM0
# (Unplug device, plug next one)

# Flash Satellite 2
esphome run sat2.yaml --device /dev/ttyACM0
# (Unplug device, plug next one)

# Flash Satellite 3
esphome run sat3.yaml --device /dev/ttyACM0
```

## Post-Flash Verification

After flashing, verify satellites are working:

1. **Check WiFi Connection**: Satellites should connect to `GADI_IoT` network
2. **Monitor MQTT**: Use mosquitto_sub to watch for messages:
   ```bash
   mosquitto_sub -h 172.16.10.12 -u gatekeeper_pi -P gatekeeper_pi -t 'gatekeeper/satellite/#' -v
   ```
3. **Check Gatekeeper Dashboard**: Navigate to `http://172.16.9.20` → Satellites tab

## Resources
- [ESPHome Official Installation Docs](https://esphome.io/guides/installing_esphome.html)
- [PlatformIO Troubleshooting](https://docs.platformio.org/en/latest/faq.html)
- [ESP32-C3 Flashing Guide](https://esphome.io/devices/esp32.html)
