#!/usr/bin/env bash
# Veltrix Installer for Linux
# Installs or upgrades Veltrix on a Linux server.
#
# Usage:
#   sudo bash install-linux.sh          # Interactive install
#   sudo bash install-linux.sh --update # Update existing installation
#   sudo bash install-linux.sh --demo   # Install with demo data

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INSTALL_DIR="/opt/veltrix"
DATA_DIR="/opt/veltrix/data"
BACKUP_DIR="/opt/veltrix/backups"
LOG_DIR="/opt/veltrix/logs"
ENV_FILE="/etc/veltrix.env"
SERVICE_NAME="veltrix"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VELTRIX_USER="veltrix"
VELTRIX_GROUP="veltrix"
PYTHON_MIN="3.12"
REPO_URL="https://github.com/iPmartNetwork/Veltrix.git"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║          Veltrix — Intelligent Network Control   ║"
    echo "║                    Installer v0.2.0              ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (sudo)."
        exit 1
    fi
}

check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
            log_info "Python ${PYTHON_VERSION} detected."
            return 0
        fi
    fi
    log_error "Python 3.12 or newer is required."
    log_info "Install with: apt install python3.12 (Ubuntu/Debian)"
    log_info "Or: dnf install python3.12 (Fedora/RHEL)"
    exit 1
}

check_existing() {
    if [[ -d "$INSTALL_DIR" ]]; then
        return 0
    fi
    return 1
}

create_user() {
    if id "$VELTRIX_USER" &>/dev/null; then
        log_info "User '${VELTRIX_USER}' already exists."
    else
        log_info "Creating system user '${VELTRIX_USER}'..."
        groupadd --system "$VELTRIX_GROUP" 2>/dev/null || true
        useradd --system --gid "$VELTRIX_GROUP" --home "$INSTALL_DIR" --no-create-home --shell /usr/sbin/nologin "$VELTRIX_USER"
    fi
}

create_directories() {
    log_info "Creating directories..."
    mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$BACKUP_DIR" "$LOG_DIR"
    chown -R "${VELTRIX_USER}:${VELTRIX_GROUP}" "$INSTALL_DIR"
}

copy_files() {
    local source_dir="${1:-.}"
    log_info "Copying files to ${INSTALL_DIR}..."

    # Backup existing installation
    if [[ -d "${INSTALL_DIR}/outpanel" ]]; then
        log_info "Backing up existing installation..."
        cp -r "${INSTALL_DIR}/outpanel" "${INSTALL_DIR}/outpanel.bak.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
    fi

    cp -r "${source_dir}/outpanel" "$INSTALL_DIR/"
    cp -r "${source_dir}/web" "$INSTALL_DIR/"
    cp -r "${source_dir}/docs" "$INSTALL_DIR/" 2>/dev/null || true
    cp "${source_dir}/README.md" "$INSTALL_DIR/" 2>/dev/null || true
    cp "${source_dir}/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true

    chown -R "${VELTRIX_USER}:${VELTRIX_GROUP}" "$INSTALL_DIR"
}

create_env_file() {
    if [[ -f "$ENV_FILE" ]]; then
        log_info "Environment file already exists: ${ENV_FILE}"
        return
    fi

    log_info "Creating environment file: ${ENV_FILE}"
    local encryption_key=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    local api_token=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    cat > "$ENV_FILE" <<EOF
# Veltrix Configuration
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

OUTPANEL_HOST=0.0.0.0
OUTPANEL_PORT=8000
OUTPANEL_DB=${DATA_DIR}/veltrix.db
OUTPANEL_BACKUP_DIR=${BACKUP_DIR}
OUTPANEL_LOG_DIR=${LOG_DIR}
OUTPANEL_LOG_FILE=veltrix.log
OUTPANEL_LOG_FORMAT=json
OUTPANEL_MONITOR_INTERVAL=30

# Security
OUTPANEL_API_TOKEN=${api_token}
OUTPANEL_ENCRYPTION_KEY=${encryption_key}

# License (configure after purchase)
OUTPANEL_REQUIRE_LICENSE=0
OUTPANEL_LICENSE_SERVER_URL=
OUTPANEL_LICENSE_KEY=

# Worker
OUTPANEL_AUTO_DISABLE_THRESHOLD=5
OUTPANEL_AUTO_DISABLE_WINDOW=30

# Language: fa or en
OUTPANEL_LANGUAGE=fa
EOF

    chmod 600 "$ENV_FILE"
    chown root:${VELTRIX_GROUP} "$ENV_FILE"
    chmod 640 "$ENV_FILE"
    log_info "Generated API token and encryption key."
}

install_service() {
    log_info "Installing systemd service..."
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Veltrix — Intelligent Network Control
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${VELTRIX_USER}
Group=${VELTRIX_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 -m outpanel.app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=veltrix

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${DATA_DIR} ${BACKUP_DIR} ${LOG_DIR}
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    log_info "Service installed and enabled."
}

start_service() {
    log_info "Starting Veltrix..."
    systemctl restart "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Veltrix is running!"
    else
        log_error "Veltrix failed to start. Check: journalctl -u ${SERVICE_NAME} -n 20"
        exit 1
    fi
}

show_status() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN} ✓ Veltrix installed successfully!${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Dashboard:    ${CYAN}http://$(hostname -I | awk '{print $1}'):8000${NC}"
    echo -e "  Config:       ${ENV_FILE}"
    echo -e "  Data:         ${DATA_DIR}"
    echo -e "  Logs:         ${LOG_DIR}"
    echo -e "  Service:      systemctl status ${SERVICE_NAME}"
    echo ""
    echo -e "  ${YELLOW}First visit the dashboard to create the admin account.${NC}"
    echo ""
}

show_menu() {
    echo ""
    echo -e "${CYAN}Select an option:${NC}"
    echo "  1) Fresh install"
    echo "  2) Update existing installation"
    echo "  3) Install with demo data"
    echo "  4) Uninstall"
    echo "  5) Show status"
    echo "  6) Exit"
    echo ""
    read -p "Choice [1-6]: " choice
    echo ""

    case $choice in
        1) do_install ;;
        2) do_update ;;
        3) do_install_demo ;;
        4) do_uninstall ;;
        5) systemctl status "$SERVICE_NAME" 2>/dev/null || log_warn "Service not installed." ;;
        6) exit 0 ;;
        *) log_error "Invalid choice."; show_menu ;;
    esac
}

do_install() {
    check_python
    create_user
    create_directories
    copy_files "$(cd "$(dirname "$0")/.." && pwd)"
    create_env_file
    install_service
    start_service
    show_status
}

do_update() {
    if ! check_existing; then
        log_error "Veltrix is not installed. Use fresh install."
        exit 1
    fi
    check_python
    log_info "Updating Veltrix..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    copy_files "$(cd "$(dirname "$0")/.." && pwd)"
    systemctl daemon-reload
    start_service
    log_info "Update complete!"
}

do_install_demo() {
    do_install
    log_info "Seeding demo data..."
    sudo -u "$VELTRIX_USER" bash -c "cd ${INSTALL_DIR} && OUTPANEL_DEMO_MODE=1 python3 -c 'from outpanel.demo import seed_demo_data; print(seed_demo_data())'"
    log_info "Demo data created."
}

do_uninstall() {
    read -p "Are you sure you want to uninstall Veltrix? Data will be preserved. [y/N]: " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    log_info "Service removed. Data preserved in ${DATA_DIR}."
    log_info "To fully remove: rm -rf ${INSTALL_DIR}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print_banner
check_root

case "${1:-}" in
    --update) do_update ;;
    --demo) do_install_demo ;;
    --uninstall) do_uninstall ;;
    *) show_menu ;;
esac
