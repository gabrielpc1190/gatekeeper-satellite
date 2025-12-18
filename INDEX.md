# Gatekeeper NG - Documentation Index

## 📚 Complete Documentation Set

This directory contains comprehensive documentation for the Gatekeeper NG presence detection system.

---

## Quick Links

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[README.md](README.md)** | Project overview & architecture | First-time setup, understanding system |
| **[DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md)** | Complete deployment history | Maintenance, troubleshooting, updates |
| **[FLASH_LOG.md](FLASH_LOG.md)** | Satellite flashing details | Satellite issues, re-flashing |
| **[ESPHOME_FLASH_GUIDE.md](ESPHOME_FLASH_GUIDE.md)** | ESPHome setup guide | First-time flashing, ESPHome issues |
| **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** | Technical architecture | Development, integration, monitoring |

---

## Document Summaries

### 📖 README.md
**What it covers**:
- System architecture and components
- How Gatekeeper works (overview)
- Home Assistant integration
- Basic troubleshooting
- Quick start guide

**Best for**: New users, project overview

---

### 🚀 DEPLOYMENT_LOG.md
**What it covers**:
- Complete deployment history (Dec 17, 2025)
- Code audit and bug fixes
- Satellite flashing process
- Server deployment steps
- Issues encountered and solutions
- Maintenance procedures
- System status verification

**Best for**: 
- DevOps / maintenance
- Troubleshooting production issues
- Understanding deployment history
- Updating/upgrading the system

**Key Sections**:
- Code Audit & Fixes (MQTT topic bug, tracker bug)
- Satellite Flashing (all 3 satellites, timings, results)
- Server Deployment (process, verification)
- Issues Encountered (disk space, PlatformIO, routes, MQTT)
- Maintenance Guide (restart, logs, config, MQTT monitoring)

---

### ⚡ FLASH_LOG.md
**What it covers**:
- Detailed satellite flashing log
- Compilation output for each satellite
- Connection details (IP, MAC, signal strength)
- Flash timings and durations
- Dashboard deployment resolution
- Final system status

**Best for**:
- Satellite-specific issues
- Re-flashing satellites
- Verifying satellite status
- Understanding flash process

**Key Sections**:
- Satellite 1 (9 min flash, first-time setup)
- Satellite 2 (4 min flash, cached toolchain)
- Satellite 3 (4 min flash, cached toolchain)
- Final deployment resolution
- Complete satellite status table

---

### 🔧 ESPHOME_FLASH_GUIDE.md
**What it covers**:
- ESPHome environment setup
- Installing dependencies
- Common error solutions
- Step-by-step flashing procedure
- Troubleshooting guide
- OTA update instructions

**Best for**:
- First-time ESPHome users
- Resolving flashing errors
- Environment setup
- Understanding ESPHome workflow

**Key Sections**:
- Environment Prerequisites
- Python Virtual Environment Setup
- Common Errors ("No space left", "uv failed", etc.)
- Flashing Commands
- OTA Updates
- Verification Methods

---

### 🏗️ SYSTEM_OVERVIEW.md
**What it covers**:
- Detailed architecture diagrams
- Component roles and responsibilities
- Data flow examples
- Configuration file formats
- Network topology
- Performance characteristics
- Security considerations
- Monitoring and alerts
- Integration with Home Assistant

**Best for**:
- Developers
- System integration
- Advanced troubleshooting
- Understanding internals
- Performance tuning

**Key Sections**:
- System Architecture (with diagram)
- Component Roles (Server, Satellites, MQTT)
- Data Flow Example (room-to-room movement)
- Configuration Files (detailed formats)
- Network Map
- Performance Metrics
- Backup & Recovery
- Home Assistant Integration

---

## Common Tasks

### 🔴 Emergency: Dashboard is Down
1. Check **[DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md)** → "Maintenance Guide" → "Restarting Service"
2. Verify service status:
   ```bash
   ssh rpi@172.16.9.20
   ps aux | grep python
   tail -50 ~/gatekeeper.log
   ```

### 🟡 Satellite Not Responding
1. Check **[FLASH_LOG.md](FLASH_LOG.md)** for satellite IP/MAC
2. Check **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** → "Monitoring" → "Health Checks"
3. Verify MQTT messages:
   ```bash
   mosquitto_sub -h 172.16.10.12 -u gatekeeper_pi -P gatekeeper_pi \
     -t 'gatekeeper/satellite/#' -v
   ```

### 🟢 Need to Re-Flash Satellite
1. Follow **[ESPHOME_FLASH_GUIDE.md](ESPHOME_FLASH_GUIDE.md)**
2. If OTA available:
   ```bash
   cd /root/.gemini/antigravity/scratch/gatekeeper_project
   source venv/bin/activate
   esphome run sat1.yaml  # Select OTA, enter satellite IP
   ```

### 🟢 Adding New Device
1. Web UI: http://172.16.9.20/devices → Add Device
2. Or see **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** → "Configuration Files" → `devices.json`

### 🟢 Assigning Satellite to Room
1. Web UI: http://172.16.9.20/satellites
2. Or edit `/home/rpi/gatekeeper_ng/config/satellites.json`

### 🟢 Updating Server Code
1. Follow **[DEPLOYMENT_LOG.md](DEPLOYMENT_LOG.md)** → "Maintenance Guide" → "Updating Configuration"
2. Or see **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** → "Upgrade Path"

---

## System Quick Reference

### Access Points
- **Web Dashboard**: http://172.16.9.20/
- **Satellite Management**: http://172.16.9.20/satellites
- **SSH**: `ssh rpi@172.16.9.20` (password: rpi)

### Satellites
| Name | IP | MAC | Room Assignment |
|------|-------------|------------------|-----------------|
| gatekeeper-xiao-1 | 172.16.9.10 | 94:A9:90:6B:E0:F4 | Via dashboard |
| gatekeeper-xiao-2 | 172.16.9.12 | 94:A9:90:6B:68:60 | Via dashboard |
| gatekeeper-xiao-3 | 172.16.9.13 | 94:A9:90:6B:61:78 | Via dashboard |

### MQTT Broker
- **Host**: 172.16.10.12
- **Port**: 1883
- **User**: gatekeeper_pi
- **Password**: gatekeeper_pi
- **Topic**: `gatekeeper/satellite/<satellite-id>/<mac>`

### Key Files on RPi
- **Config**: `/home/rpi/gatekeeper_ng/config/`
- **Logs**: `/home/rpi/gatekeeper.log`
- **Code**: `/home/rpi/gatekeeper_ng/`

---

## Document Change Log

| Date | Document | Change |
|------|----------|--------|
| 2025-12-17 | All | ✅ Initial documentation created |
| 2025-12-17 | DEPLOYMENT_LOG.md | ✅ Complete deployment documented |
| 2025-12-17 | FLASH_LOG.md | ✅ All 3 satellites logged |
| 2025-12-17 | README.md | ✅ Added deployment status & quick start |
| 2025-12-17 | SYSTEM_OVERVIEW.md | ✅ Created technical architecture doc |
| 2025-12-17 | INDEX.md | ✅ Created this index |

---

## Need Help?

1. **Start with the quick reference above** for basic info
2. **Check the appropriate document** based on your task
3. **Search within documents** using Ctrl+F for keywords
4. **Check logs** if something isn't working:
   ```bash
   ssh rpi@172.16.9.20
   tail -50 ~/gatekeeper.log
   ```

## Contributing to Documentation

If you make changes to the system:
1. Update the appropriate document
2. Update this INDEX.md if adding new docs
3. Update the Change Log above
4. Commit with clear message describing changes

---

**Project**: Gatekeeper NG  
**Last Updated**: 2025-12-17 14:21 UTC  
**Status**: ✅ Production - All Systems Operational
