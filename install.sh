#!/bin/bash
#
# Gatekeeper NG - Installation Script
# Version: 1.0
# Date: 2025-12-17
#
# This script installs Gatekeeper NG on a Raspberry Pi
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/home/rpi/gatekeeper_ng"
SERVICE_NAME="gatekeeper"
SERVICE_USER="root"  # Needs root for BLE scanning

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║         Gatekeeper NG Installation Script            ║"
    echo "║              Bluetooth Presence Detection             ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_error "Run as: bash install.sh"
        exit 1
    fi
}

check_platform() {
    print_step "Checking platform..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_step "Found Python $PYTHON_VERSION"
    
    if ! command -v bluetoothctl &> /dev/null; then
        print_warning "Bluetooth utilities not found, installing..."
        sudo apt-get update
        sudo apt-get install -y bluetooth bluez bluez-tools
    fi
}

install_dependencies() {
    print_step "Installing Python dependencies..."
    
    # Install system packages
    sudo apt-get update
    sudo apt-get install -y python3-pip python3-dev libbluetooth-dev
    
    # Install Python packages
    if [ -f "${INSTALL_DIR}/requirements.txt" ]; then
        sudo pip3 install -r "${INSTALL_DIR}/requirements.txt" --break-system-packages 2>/dev/null || \
        pip3 install -r "${INSTALL_DIR}/requirements.txt"
    else
        print_step "Installing core dependencies..."
        sudo pip3 install flask paho-mqtt bleak --break-system-packages 2>/dev/null || \
        pip3 install flask paho-mqtt bleak
    fi
}

stop_existing_service() {
    print_step "Stopping existing services..."
    
    # Stop systemd service if exists
    if systemctl is-active --quiet ${SERVICE_NAME}.service 2>/dev/null; then
        sudo systemctl stop ${SERVICE_NAME}.service
        print_step "Stopped systemd service"
    fi
    
    # Kill any running Python gatekeeper processes
    sudo pkill -9 -f "python.*gatekeeper.*main.py" 2>/dev/null || true
    sudo pkill -9 -f "python.*admin.py" 2>/dev/null || true
    sudo pkill -9 -f "python.*monitor" 2>/dev/null || true
    
    sleep 2
}

create_config() {
    print_step "Creating configuration files..."
    
    CONFIG_DIR="${INSTALL_DIR}/config"
    mkdir -p "${CONFIG_DIR}"
    
    # MQTT Configuration
    if [ ! -f "${CONFIG_DIR}/mqtt.json" ]; then
        print_step "Creating MQTT configuration..."
        cat > "${CONFIG_DIR}/mqtt.json" << 'EOF'
{
    "broker": "172.16.10.12",
    "port": 1883,
    "user": "gatekeeper_pi",
    "password": "gatekeeper_pi",
    "topic_prefix": "gatekeeper"
}
EOF
        print_step "Created mqtt.json"
    else
        print_step "mqtt.json already exists, skipping"
    fi
    
    # Devices Configuration (empty by default)
    if [ ! -f "${CONFIG_DIR}/devices.json" ]; then
        print_step "Creating devices configuration..."
        cat > "${CONFIG_DIR}/devices.json" << 'EOF'
[
]
EOF
        print_step "Created devices.json (add devices via web UI)"
    fi
    
    # Settings Configuration
    if [ ! -f "${CONFIG_DIR}/settings.json" ]; then
        print_step "Creating settings configuration..."
        cat > "${CONFIG_DIR}/settings.json" << 'EOF'
{
    "PREF_BEACON_EXPIRATION": "60",
    "PREF_DEVICE_TRACKER_REPORT": "true"
}
EOF
        print_step "Created settings.json"
    fi
    
    # Satellites Configuration (auto-populated)
    if [ ! -f "${CONFIG_DIR}/satellites.json" ]; then
        echo "{}" > "${CONFIG_DIR}/satellites.json"
        print_step "Created satellites.json (auto-populated)"
    fi
}

create_systemd_service() {
    print_step "Creating systemd service..."
    
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Gatekeeper NG - Bluetooth Presence Detection
After=network.target bluetooth.target
Wants=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# BLE scanning requires CAP_NET_ADMIN
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    print_step "Systemd service created"
}

configure_bluetooth() {
    print_step "Configuring Bluetooth..."
    
    # Enable Bluetooth
    sudo systemctl enable bluetooth
    sudo systemctl start bluetooth
    
    # Give user bluetooth permissions
    sudo usermod -aG bluetooth $(whoami) 2>/dev/null || true
    
    print_step "Bluetooth configured"
}

display_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Installation Complete!                      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}📁 Installation Directory:${NC} ${INSTALL_DIR}"
    echo -e "${BLUE}🌐 Web Dashboard:${NC} http://$(hostname -I | awk '{print $1}'):80/"
    echo -e "${BLUE}📝 Configuration:${NC} ${INSTALL_DIR}/config/"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Edit configuration: nano ${INSTALL_DIR}/config/mqtt.json"
    echo "  2. Start service: sudo systemctl start ${SERVICE_NAME}"
    echo "  3. Enable on boot: sudo systemctl enable ${SERVICE_NAME}"
    echo "  4. View logs: sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  5. Access dashboard: http://$(hostname -I | awk '{print $1}'):80/"
    echo ""
    echo -e "${YELLOW}Add devices via web UI:${NC}"
    echo "  http://$(hostname -I | awk '{print $1}'):80/devices"
    echo ""
    echo -e "${YELLOW}Assign satellites to rooms:${NC}"
    echo "  http://$(hostname -I | awk '{print $1}'):80/satellites"
    echo ""
}

prompt_start_service() {
    echo ""
    read -p "Do you want to start Gatekeeper now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Starting Gatekeeper service..."
        sudo systemctl start ${SERVICE_NAME}
        sleep 2
        
        if systemctl is-active --quiet ${SERVICE_NAME}; then
            print_step "✅ Service started successfully!"
            echo ""
            echo "View logs with: sudo journalctl -u ${SERVICE_NAME} -f"
        else
            print_error "Service failed to start. Check logs:"
            echo "sudo journalctl -u ${SERVICE_NAME} -n 50"
        fi
    else
        print_step "Service not started. Start manually with:"
        echo "  sudo systemctl start ${SERVICE_NAME}"
    fi
}

# Main installation flow
main() {
    print_header
    
    check_root
    check_platform
    
    print_step "Installation directory: ${INSTALL_DIR}"
    
    if [ ! -d "${INSTALL_DIR}" ]; then
        print_error "Installation directory not found: ${INSTALL_DIR}"
        print_error "Please copy gatekeeper_ng directory to ${INSTALL_DIR} first"
        exit 1
    fi
    
    stop_existing_service
    install_dependencies
    create_config
    configure_bluetooth
    create_systemd_service
    
    display_summary
    prompt_start_service
    
    echo ""
    print_step "Installation completed successfully! 🎉"
}

# Run main function
main "$@"
