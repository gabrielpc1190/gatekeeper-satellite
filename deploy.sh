#!/bin/bash
#
# Gatekeeper NG - Quick Deploy Script
# Version: 1.0
#
# Deploys Gatekeeper NG to remote Raspberry Pi via SSH
#

set -e

# Configuration
RPi_USER="rpi"
RPi_HOST=""
RPi_PASS=""
REMOTE_DIR="/home/rpi/gatekeeper_ng"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║          Gatekeeper NG Deploy Script                  ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Get deployment info
get_deployment_info() {
    if [ -z "$RPi_HOST" ]; then
        read -p "Raspberry Pi IP address [172.16.9.20]: " RPi_HOST
        RPi_HOST=${RPi_HOST:-172.16.9.20}
    fi
    
    if [ -z "$RPi_PASS" ]; then
        read -sp "Raspberry Pi password [rpi]: " RPi_PASS
        echo ""
        RPi_PASS=${RPi_PASS:-rpi}
    fi
}

# Check if sshpass is installed
check_sshpass() {
    if ! command -v sshpass &> /dev/null; then
        print_error "sshpass is not installed"
        echo "Install with: sudo apt-get install sshpass"
        exit 1
    fi
}

# Create tarball
create_tarball() {
    print_step "Creating deployment package..."
    
    if [ ! -d "gatekeeper_ng" ]; then
        print_error "gatekeeper_ng directory not found"
        exit 1
    fi
    
    tar -czf gatekeeper_ng_deploy.tar.gz \
        --exclude='gatekeeper_ng/__pycache__' \
        --exclude='gatekeeper_ng/*/__pycache__' \
        --exclude='gatekeeper_ng/**/__pycache__' \
        --exclude='gatekeeper_ng/config/*.json' \
        gatekeeper_ng/
    
    print_step "Package created: gatekeeper_ng_deploy.tar.gz"
}

# Stop service
stop_service() {
    print_step "Stopping existing service on ${RPi_HOST}..."
    
    sshpass -p "$RPi_PASS" ssh -o StrictHostKeyChecking=no ${RPi_USER}@${RPi_HOST} \
        "sudo systemctl stop gatekeeper 2>/dev/null || true; \
         sudo pkill -9 -f 'python.*gatekeeper' 2>/dev/null || true"
    
    print_step "Service stopped"
}

# Backup config
backup_config() {
    print_step "Backing up configuration..."
    
    sshpass -p "$RPi_PASS" ssh -o StrictHostKeyChecking=no ${RPi_USER}@${RPi_HOST} \
        "if [ -d ${REMOTE_DIR}/config ]; then \
            cp -r ${REMOTE_DIR}/config ${REMOTE_DIR}/config.backup.\$(date +%Y%m%d_%H%M%S); \
            echo 'Config backed up'; \
         else \
            echo 'No config to backup'; \
         fi"
}

# Upload code
upload_code() {
    print_step "Uploading code to ${RPi_HOST}..."
    
    sshpass -p "$RPi_PASS" scp gatekeeper_ng_deploy.tar.gz ${RPi_USER}@${RPi_HOST}:~/
    
    print_step "Extracting code..."
    
    sshpass -p "$RPi_PASS" ssh -o StrictHostKeyChecking=no ${RPi_USER}@${RPi_HOST} \
        "rm -rf ${REMOTE_DIR}_new && \
         mkdir -p ${REMOTE_DIR}_new && \
         tar -xzf ~/gatekeeper_ng_deploy.tar.gz -C ${REMOTE_DIR}_new && \
         if [ -d ${REMOTE_DIR}/config ]; then \
            cp -r ${REMOTE_DIR}/config ${REMOTE_DIR}_new/gatekeeper_ng/; \
         fi && \
         rm -rf ${REMOTE_DIR}_old && \
         mv ${REMOTE_DIR} ${REMOTE_DIR}_old 2>/dev/null || true && \
         mv ${REMOTE_DIR}_new/gatekeeper_ng ${REMOTE_DIR} && \
         rm -rf ${REMOTE_DIR}_new ~/gatekeeper_ng_deploy.tar.gz"
    
    print_step "Code deployed"
}

# Install/update service
install_service() {
    print_step "Installing/updating service..."
    
    sshpass -p "$RPi_PASS" ssh -o StrictHostKeyChecking=no ${RPi_USER}@${RPi_HOST} \
        "cd ${REMOTE_DIR} && bash install.sh" || true
}

# Start service
start_service() {
    print_step "Starting service..."
    
    sshpass -p "$RPi_PASS" ssh -o StrictHostKeyChecking=no ${RPi_USER}@${RPi_HOST} \
        "sudo systemctl daemon-reload && \
         sudo systemctl start gatekeeper && \
         sleep 2"
    
    # Check status
    if sshpass -p "$RPi_PASS" ssh -o StrictHostKeyChecking=no ${RPi_USER}@${RPi_HOST} \
        "systemctl is-active --quiet gatekeeper"; then
        print_step "✅ Service started successfully"
    else
        print_error "Service failed to start. Check logs:"
        echo "  ssh ${RPi_USER}@${RPi_HOST}"
        echo "  sudo journalctl -u gatekeeper -n 50"
    fi
}

# Verify deployment
verify_deployment() {
    print_step "Verifying deployment..."
    
    # Check web server
    if curl -s -f "http://${RPi_HOST}/" > /dev/null 2>&1; then
        print_step "✅ Web dashboard accessible"
    else
        print_error "Web dashboard not accessible"
    fi
    
    # Check satellites page
    if curl -s -f "http://${RPi_HOST}/satellites" > /dev/null 2>&1; then
        print_step "✅ Satellites page accessible"
    else
        print_error "Satellites page not accessible"
    fi
}

# Display summary
display_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         Deployment Complete!                          ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}📍 Target:${NC} ${RPi_USER}@${RPi_HOST}"
    echo -e "${BLUE}📁 Directory:${NC} ${REMOTE_DIR}"
    echo -e "${BLUE}🌐 Dashboard:${NC} http://${RPi_HOST}/"
    echo -e "${BLUE}🛰️  Satellites:${NC} http://${RPi_HOST}/satellites"
    echo ""
    echo -e "${YELLOW}Useful Commands:${NC}"
    echo "  View logs:     ssh ${RPi_USER}@${RPi_HOST} sudo journalctl -u gatekeeper -f"
    echo "  Restart:       ssh ${RPi_USER}@${RPi_HOST} sudo systemctl restart gatekeeper"
    echo "  Status:        ssh ${RPi_USER}@${RPi_HOST} sudo systemctl status gatekeeper"
    echo "  Configure:     ssh ${RPi_USER}@${RPi_HOST} cd ${REMOTE_DIR} && bash configure.sh"
    echo ""
}

# Cleanup
cleanup() {
    if [ -f "gatekeeper_ng_deploy.tar.gz" ]; then
        rm gatekeeper_ng_deploy.tar.gz
        print_step "Cleaned up local tarball"
    fi
}

# Main deployment flow
main() {
    print_header
    
    check_sshpass
    get_deployment_info
    
    create_tarball
    stop_service
    backup_config
    upload_code
    # install_service  # Commented out - manual installation required first time
    start_service
    verify_deployment
    
    display_summary
    cleanup
    
    echo -e "${GREEN}Deployment completed! 🎉${NC}"
}

# Handle Ctrl+C
trap cleanup EXIT

# Run
main "$@"
