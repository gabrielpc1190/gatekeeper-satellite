#!/bin/bash
#
# Gatekeeper NG - Configuration Wizard
# Version: 1.0
#
# Interactive configuration tool for Gatekeeper NG
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CONFIG_DIR="/home/rpi/gatekeeper_ng/config"

print_header() {
    clear
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║      Gatekeeper NG Configuration Wizard               ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

configure_mqtt() {
    echo -e "${GREEN}MQTT Broker Configuration${NC}"
    echo ""
    
    # Load existing config if available
    if [ -f "${CONFIG_DIR}/mqtt.json" ]; then
        CURRENT_BROKER=$(jq -r '.broker' "${CONFIG_DIR}/mqtt.json" 2>/dev/null || echo "")
        CURRENT_PORT=$(jq -r '.port' "${CONFIG_DIR}/mqtt.json" 2>/dev/null || echo "")
        CURRENT_USER=$(jq -r '.user' "${CONFIG_DIR}/mqtt.json" 2>/dev/null || echo "")
    fi
    
    read -p "MQTT Broker IP [${CURRENT_BROKER:-172.16.10.12}]: " BROKER
    BROKER=${BROKER:-${CURRENT_BROKER:-172.16.10.12}}
    
    read -p "MQTT Port [${CURRENT_PORT:-1883}]: " PORT
    PORT=${PORT:-${CURRENT_PORT:-1883}}
    
    read -p "MQTT Username [${CURRENT_USER:-gatekeeper_pi}]: " USER
    USER=${USER:-${CURRENT_USER:-gatekeeper_pi}}
    
    read -sp "MQTT Password: " PASSWORD
    echo ""
    
    if [ -z "$PASSWORD" ] && [ -f "${CONFIG_DIR}/mqtt.json" ]; then
        PASSWORD=$(jq -r '.password' "${CONFIG_DIR}/mqtt.json" 2>/dev/null || echo "gatekeeper_pi")
    fi
    PASSWORD=${PASSWORD:-gatekeeper_pi}
    
    read -p "Topic Prefix [gatekeeper]: " PREFIX
    PREFIX=${PREFIX:-gatekeeper}
    
    # Create config
    cat > "${CONFIG_DIR}/mqtt.json" << EOF
{
    "broker": "${BROKER}",
    "port": ${PORT},
    "user": "${USER}",
    "password": "${PASSWORD}",
    "topic_prefix": "${PREFIX}"
}
EOF
    
    echo -e "${GREEN}✓ MQTT configuration saved${NC}"
}

add_device() {
    echo -e "${GREEN}Add Bluetooth Device${NC}"
    echo ""
    
    read -p "Device MAC Address (format: AA:BB:CC:DD:EE:FF): " MAC
    MAC=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')
    
    if ! [[ $MAC =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]]; then
        echo -e "${YELLOW}Invalid MAC address format${NC}"
        return
    fi
    
    read -p "Device Alias (e.g., John-iPhone): " ALIAS
    
    echo "Device Type:"
    echo "  1) Phone"
    echo "  2) Laptop"
    echo "  3) Watch"
    echo "  4) Tablet"
    echo "  5) Other"
    read -p "Select type [1]: " TYPE_NUM
    TYPE_NUM=${TYPE_NUM:-1}
    
    case $TYPE_NUM in
        1) TYPE="Phone" ;;
        2) TYPE="Laptop" ;;
        3) TYPE="Watch" ;;
        4) TYPE="Tablet" ;;
        5) TYPE="Other" ;;
        *) TYPE="Phone" ;;
    esac
    
    # Load existing devices
    if [ -f "${CONFIG_DIR}/devices.json" ]; then
        DEVICES=$(cat "${CONFIG_DIR}/devices.json")
    else
        DEVICES="[]"
    fi
    
    # Add new device
    NEW_DEVICE=$(cat << EOF
{
    "mac": "${MAC}",
    "alias": "${ALIAS}",
    "type": "${TYPE}"
}
EOF
)
    
    DEVICES=$(echo "$DEVICES" | jq ". += [${NEW_DEVICE}]")
    echo "$DEVICES" | jq '.' > "${CONFIG_DIR}/devices.json"
    
    echo -e "${GREEN}✓ Device added: ${ALIAS} (${MAC})${NC}"
}

list_devices() {
    echo -e "${GREEN}Configured Devices${NC}"
    echo ""
    
    if [ ! -f "${CONFIG_DIR}/devices.json" ]; then
        echo "No devices configured"
        return
    fi
    
    DEVICE_COUNT=$(jq 'length' "${CONFIG_DIR}/devices.json")
    
    if [ "$DEVICE_COUNT" -eq 0 ]; then
        echo "No devices configured"
        return
    fi
    
    jq -r '.[] | "  • \(.alias) (\(.type)) - \(.mac)"' "${CONFIG_DIR}/devices.json"
    echo ""
    echo "Total devices: $DEVICE_COUNT"
}

remove_device() {
    list_devices
    echo ""
    read -p "Enter MAC address to remove: " MAC
    MAC=$(echo "$MAC" | tr '[:lower:]' '[:upper:]')
    
    if [ -f "${CONFIG_DIR}/devices.json" ]; then
        DEVICES=$(jq "del(.[] | select(.mac == \"${MAC}\"))" "${CONFIG_DIR}/devices.json")
        echo "$DEVICES" | jq '.' > "${CONFIG_DIR}/devices.json"
        echo -e "${GREEN}✓ Device removed${NC}"
    fi
}

configure_settings() {
    echo -e "${GREEN}System Settings${NC}"
    echo ""
    
    read -p "Timeout interval (seconds) [60]: " TIMEOUT
    TIMEOUT=${TIMEOUT:-60}
    
    read -p "Enable Home Assistant device tracker? (y/n) [y]: " HA_ENABLE
    HA_ENABLE=${HA_ENABLE:-y}
    
    if [[ $HA_ENABLE =~ ^[Yy]$ ]]; then
        HA_REPORT="true"
    else
        HA_REPORT="false"
    fi
    
    cat > "${CONFIG_DIR}/settings.json" << EOF
{
    "PREF_BEACON_EXPIRATION": "${TIMEOUT}",
    "PREF_DEVICE_TRACKER_REPORT": "${HA_REPORT}"
}
EOF
    
    echo -e "${GREEN}✓ Settings saved${NC}"
}

test_mqtt() {
    echo -e "${GREEN}Testing MQTT Connection${NC}"
    echo ""
    
    if [ ! -f "${CONFIG_DIR}/mqtt.json" ]; then
        echo -e "${YELLOW}MQTT not configured${NC}"
        return
    fi
    
    BROKER=$(jq -r '.broker' "${CONFIG_DIR}/mqtt.json")
    PORT=$(jq -r '.port' "${CONFIG_DIR}/mqtt.json")
    USER=$(jq -r '.user' "${CONFIG_DIR}/mqtt.json")
    PASS=$(jq -r '.password' "${CONFIG_DIR}/mqtt.json")
    
    echo "Testing connection to ${BROKER}:${PORT}..."
    
    if command -v mosquitto_pub &> /dev/null; then
        if mosquitto_pub -h "$BROKER" -p "$PORT" -u "$USER" -P "$PASS" \
           -t "gatekeeper/test" -m "test" 2>/dev/null; then
            echo -e "${GREEN}✓ MQTT connection successful${NC}"
        else
            echo -e "${YELLOW}✗ MQTT connection failed${NC}"
        fi
    else
        echo -e "${YELLOW}mosquitto-clients not installed, skipping test${NC}"
    fi
}

main_menu() {
    while true; do
        print_header
        echo ""
        echo "  1) Configure MQTT Broker"
        echo "  2) Add Device"
        echo "  3) List Devices"
        echo "  4) Remove Device"
        echo "  5) Configure Settings"
        echo "  6) Test MQTT Connection"
        echo "  7) Exit"
        echo ""
        read -p "Select option: " OPTION
        
        case $OPTION in
            1) configure_mqtt; read -p "Press Enter to continue..." ;;
            2) add_device; read -p "Press Enter to continue..." ;;
            3) list_devices; read -p "Press Enter to continue..." ;;
            4) remove_device; read -p "Press Enter to continue..." ;;
            5) configure_settings; read -p "Press Enter to continue..." ;;
            6) test_mqtt; read -p "Press Enter to continue..." ;;
            7) exit 0 ;;
            *) echo "Invalid option" ;;
        esac
    done
}

# Check for jq
if ! command -v jq &> /dev/null; then
    echo "Installing jq..."
    sudo apt-get update && sudo apt-get install -y jq
fi

# Create config directory if needed
mkdir -p "${CONFIG_DIR}"

# Run main menu
main_menu
