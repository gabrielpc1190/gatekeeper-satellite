# Gatekeeper NG: Robust Indoor Presence System

Gatekeeper NG is a high-precision, low-latency indoor presence tracking system designed for Home Assistant. It uses a **Hub + Satellite** architecture to detect devices (phones, watches, iBeacons) via Bluetooth LE and determine their location with room-level accuracy.

---

## 🏗️ System Architecture

- **Central Hub (Raspberry Pi)**: Processes all signal data, runs the Web Admin UI, and manages Home Assistant integration via MQTT Discovery.
- **Satellites (ESP32-based)**:
  - **ESP32-C3 (Xiao)**: Compact nodes using Seeed XIAO ESP32-C3 boards
  - **ESP32 WROOM-32**: Standard ESP32 development boards
  - Distributed nodes that scan for Bluetooth signals and report RSSI values to the Hub in real-time
- **MQTT Broker**: The communication backbone between satellites and the hub.

---

## 🛠️ Installation & Setup

### 1. Raspberry Pi (Hub) Setup
1. **Initial Dependencies**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-pip python3-dev bluetooth bluez bluez-tools libbluetooth-dev
   pip install flask paho-mqtt bleak
   ```
2. **Deploy Code**:
   Clone the repository and place the `gatekeeper_ng` folder in `/home/rpi/`.
3.  **Run Service**:
    You can run it manually or set up a systemd service (recommended):
    ```bash
    cd /home/rpi/gatekeeper_ng
    sudo python3 main.py
    ```

### 2. Satellite (ESP32) Flashing
All firmware configurations are located in `esphome_configs/`.
1. **Prepare Environment**:
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install esphome
   ```
2. **Flash USB**:
   ```bash
   # Replace satX.yaml with your specific config
   esphome run esphome_configs/esp32_sat.yaml --device /dev/ttyUSB0
   ```
3. **OTA Updates**: Once flashed, you can update Over-The-Air:
   ```bash
   esphome run esphome_configs/esp32_sat.yaml
   ```

---

## ⚖️ Calibration & Accuracy

Calibration is **critical** for distance estimation.
1. Navigate to **Satellites** in the Web UI.
2. Click **⚖️ Calibrate** for a satellite.
3. Place your device **1 meter** away and follow the instructions.
4. The system will calculate the `Ref RSSI at 1m` to normalize distance calculations.

---

## 📱 Web Admin & Advanced Features

Gatekeeper includes a modern, responsive Web UI at `http://<hub-ip>/`:

- **Dashboard**: Track devices, rooms, distances, and last seen times in real-time.
- **Bluetooth Scanner**:
    - **Live Discovery**: Scan for all nearby BLE and iBeacon devices.
    - **Multi-Select Satellite Filter**: Filter results to see only what specific satellites detect.
    - **Visual Highlighting**: Selected satellites' signals are highlighted (bold), while others are dimmed.
    - **Device Counter**: See the total number of devices currently filtered.
- **Device Management**: Add/Edit/Delete tracked devices (MAC or iBeacon UUID).

---

## 🏠 Home Assistant Integration

Gatekeeper uses **MQTT Discovery** to automatically create entities in Home Assistant.
Each device generates:
- `device_tracker`: Main presence entity.
- `sensor.room`: Current room name.
- `sensor.distance`: Estimated distance in meters.
- `sensor.rssi`: Signal strength.

---

## 📂 Project Structure

```
.
├── gatekeeper_ng/          # Core Python application
│   ├── app/                # Backend logic (Tracker, MQTT, Signals)
│   ├── admin/              # Flask Web Admin & Templates
│   └── config/             # Local configuration (JSON)
├── esphome_configs/        # YAML configurations for ESP32 satellites
└── README.md               # Unified manual & system overview
```

---

## 🐞 Troubleshooting & Logs

- **Logs**: View real-time logs in the Web UI under the **Logs** tab or via:
  ```bash
  tail -f /home/rpi/gatekeeper.log
  ```
- **MQTT**: Verify data flow with:
  ```bash
  mosquitto_sub -h <broker-ip> -u <user> -P <pass> -t 'gatekeeper/#' -v
  ```

---

## 📝 Changelog

### v1.0.2 - 2025-12-22
**Fase 1: Correcciones Críticas**
- ✅ **FIX**: Corregido TypeError en MQTT disconnect callback (Línea 148 de `mqtt_client.py`)
  - Ajustada firma de `_on_disconnect()` para compatibilidad con Paho MQTT v2.1.0
  - Sistema ahora realiza shutdown limpio sin errores
  
**Fase 2: Estandarización de Configuraciones ESPHome**
- ✅ **IMPROVE**: Unificados parámetros de BLE scan en `sat2.yaml`
  - Window scan: 200ms → 1100ms (100% cobertura)
- ✅ **IMPROVE**: Agregado throttling a `sat3.yaml`
  - Lógica de 3dB delta + 5s keepalive
  - Reducción estimada de ~80% en tráfico MQTT
- ✅ **IMPROVE**: Estandarizado `esp32_sat_2.yaml`
  - Restaurado `topic_prefix` para consistencia
  - Agregado throttling (3dB delta + 5s keepalive)

---
**Gatekeeper NG - High Precision Presence for the Modern Home.**

