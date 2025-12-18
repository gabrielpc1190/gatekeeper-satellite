# Gatekeeper NG: Robust Indoor Presence System

Gatekeeper NG is a high-precision, low-latency indoor presence tracking system designed for Home Assistant. It uses long-range Bluetooth (BLE) and iBeacon technology to detect people (via phones or wearables) with room-level accuracy.

## 🚀 Key Features

- **Polymorphic Tracking**: Supports both legacy Bluetooth MAC addresses and modern iBeacon UUIDs (ideal for iPhones with rotating MACs).
- **Robust Zoning Engine**: 
  - **Median Filtering**: Eliminates signal spikes and outliers.
  - **EMA Smoothing**: Provides stable RSSI curves.
  - **Hysteresis (>3dB)**: Prevents "flickering" between adjacent rooms.
  - **Temporal Debounce (3s)**: Requires a stable signal before confirming a room change.
- **Web Interface**: Full-featured dashboard for device management, satellite assignment, and real-time Bluetooth scanning.
- **Interactive Calibration**: Built-in 10-second sampling routine to calibrate each sensor's reference RSSI (Measured Power at 1m).
- **Hot-Reloading**: Update device names or add new sensors without restarting the core service.

---

## 🏗️ System Architecture

Gatekeeper follows a **Central Hub + Satellite** architecture:

1.  **Central Hub (Raspberry Pi)**: Runs the main Python backend, Flask Admin UI, and MQTT bridge.
2.  **Satellites (Seeed Studio XIAO ESP32-C3)**: Distributed sensors that scan for BLE/iBeacons and report raw data to the hub via MQTT.
3.  **Home Assistant**: Receives room-level location updates via MQTT Discovery.

---

## 🛠️ Setup & Installation

### 1. Requirements
- Raspberry Pi (Hub)
- ESP32-C3 nodes (Satellites)
- MQTT Broker (Mosquitto)
- Home Assistant

### 2. Satellite Firmware
Flash the satellites using the provided ESPHome YAML configurations. Ensure each satellite has a unique name (e.g., `gatekeeper-xiao-1`).

### 3. Backend Deployment
```bash
git clone https://github.com/user/gatekeeper-ng.git
cd gatekeeper-ng
pip install -r requirements.txt
python3 main.py
```

---

## ⚖️ Calibration (Crucial for Accuracy)

To get the best results, you MUST calibrate each satellite:
1. Navigate to the **Satellites** tab in the Web UI.
2. Click **⚖️ Calibrate** next to a sensor.
3. Place your phone exactly **1 meter** from the sensor.
4. Run the 10-second sample.
5. Save the result.

The system will use this value to normalize signals, ensuring that a sensor at 4m always reports a "weaker" signal than one at 2m, regardless of antenna differences.

---

## 🐞 Known Issues & Challenges

- **iPhone Backgrounding**: Some iPhones aggressively sleep their iBeacon broadcast when the screen is off. Enabling "Background Monitoring" in the HA Companion App is required.
- **Signal Absorption**: Human bodies and water tanks can absorb up to 10-15dB of signal, occasionally causing "false negatives" if the sensor is blocked.
- **Initial Discovery**: New satellites appear as `Unassigned` and require a manual room name assignment in the UI.

---

## 🗺️ Roadmap & Future Improvements

- [ ] **Native WCL Algorithm**: Re-introduce Weighted Centroid Localization for 2D/3D floor plan positioning.
- [ ] **Automatic Hysteresis**: Self-adjusting margins based on environmental noise floor.
- [ ] **Multi-Hub Mesh**: Synchronization between multiple Gatekeeper hubs for very large buildings.
- [ ] **Mobile App**: Dedicated lightweight app to replace iBeacon simulation for more stable broadcasting.

---

**Developed for Advanced Agentic Coding Projects.**
