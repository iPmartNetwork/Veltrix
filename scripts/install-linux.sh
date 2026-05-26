#!/usr/bin/env bash
#
# ╔══════════════════════════════════════════════════════════════╗
# ║              Veltrix — Intelligent Network Control           ║
# ║                   Linux Installer v0.3.0                     ║
# ╚══════════════════════════════════════════════════════════════╝
#
# One-line install:
#   bash <(curl -fsSL https://raw.githubusercontent.com/iPmartNetwork/Veltrix/master/scripts/install-linux.sh)
#
# Usage:
#   sudo bash install-linux.sh              Interactive menu
#   sudo bash install-linux.sh --install    Fresh install (non-interactive)
#   sudo bash install-linux.sh --update     Update existing installation
#   sudo bash install-linux.sh --demo       Install with demo data
#   sudo bash install-linux.sh --uninstall  Remove Veltrix service
#   sudo bash install-linux.sh --status     Show service status
#
# Mirror:
#   Uses iPmartNetwork mirror (https://mirror.ipmartnet.work) by default
#   for faster package downloads. Disable with: USE_IPMART_MIRROR=0
#
# Supported OS: Ubuntu 22.04+, Debian 12+, CentOS 9+, Fedora 38+, AlmaLinux 9+
# Requirements: Python 3.12+, systemd, curl or wget
#

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

readonly VERSION="0.3.0"
readonly INSTALL_DIR="/opt/veltrix"
readonly DATA_DIR="${INSTALL_DIR}/data"
readonly BACKUP_DIR="${INSTALL_DIR}/backups"
readonly LOG_DIR="${INSTALL_DIR}/logs"
readonly ENV_FILE="/etc/veltrix.env"
readonly SERVICE_NAME="veltrix"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
readonly VELTRIX_USER="veltrix"
readonly VELTRIX_GROUP="veltrix"
readonly REPO_URL="https://github.com/iPmartNetwork/Veltrix.git"
readonly MIN_PYTHON_MAJOR=3
readonly MIN_PYTHON_MINOR=12
readonly DEFAULT_PORT=8000

# iPmartNetwork Mirror (faster package downloads for Iranian servers)
readonly MIRROR_BASE="https://mirror.ipmartnet.work"
readonly MIRROR_APT="${MIRROR_BASE}/ubuntu/jammy"
readonly MIRROR_PIP="${MIRROR_BASE}/pypi/simple/"
readonly MIRROR_NPM="${MIRROR_BASE}/npm/"
readonly USE_MIRROR=${USE_IPMART_MIRROR:-1}  # Set to 0 to disable mirror

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly NC='\033[0m'

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

print_banner() {
    clear 2>/dev/null || true
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "    ╔═══════════════════════════════════════════════════════╗"
    echo "    ║                                                       ║"
    echo "    ║         ██╗   ██╗███████╗██╗  ████████╗██████╗ ██╗  ██╗ ║"
    echo "    ║         ██║   ██║██╔════╝██║  ╚══██╔══╝██╔══██╗╚██╗██╔╝ ║"
    echo "    ║         ██║   ██║█████╗  ██║     ██║   ██████╔╝ ╚███╔╝  ║"
    echo "    ║         ╚██╗ ██╔╝██╔══╝  ██║     ██║   ██╔══██╗ ██╔██╗  ║"
    echo "    ║          ╚████╔╝ ███████╗███████╗██║   ██║  ██║██╔╝ ██╗ ║"
    echo "    ║           ╚═══╝  ╚══════╝╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ║"
    echo "    ║                                                       ║"
    echo "    ║           Intelligent Network Control  v${VERSION}         ║"
    echo "    ║                                                       ║"
    echo "    ╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

log_info()    { echo -e "  ${GREEN}●${NC} $1"; }
log_success() { echo -e "  ${GREEN}✓${NC} $1"; }
log_warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; }
log_error()   { echo -e "  ${RED}✗${NC} $1"; }
log_step()    { echo -e "\n  ${CYAN}${BOLD}▸ $1${NC}"; }

separator() {
    echo -e "  ${DIM}─────────────────────────────────────────────────────${NC}"
}

# ---------------------------------------------------------------------------
# Prerequisite Checks
# ---------------------------------------------------------------------------

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root."
        echo -e "  ${DIM}Run with: sudo bash $0${NC}"
        exit 1
    fi
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_NAME="${ID}"
        OS_VERSION="${VERSION_ID}"
        OS_PRETTY="${PRETTY_NAME}"
    else
        OS_NAME="unknown"
        OS_VERSION="0"
        OS_PRETTY="Unknown Linux"
    fi
    log_info "Operating System: ${OS_PRETTY}"
}

check_architecture() {
    local arch
    arch=$(uname -m)
    if [[ "$arch" != "x86_64" && "$arch" != "aarch64" ]]; then
        log_warn "Architecture '${arch}' is not officially tested. Proceeding anyway."
    fi
    log_info "Architecture: ${arch}"
}

check_systemd() {
    if ! command -v systemctl &>/dev/null; then
        log_error "systemd is required but not found."
        log_info "Veltrix requires systemd for service management."
        exit 1
    fi
    log_success "systemd available"
}

check_network_tools() {
    if command -v curl &>/dev/null; then
        log_success "curl available"
    elif command -v wget &>/dev/null; then
        log_success "wget available"
    else
        log_warn "Neither curl nor wget found. Installing curl..."
        install_package "curl"
    fi
}

check_python() {
    local python_cmd=""

    # Try python3.12 first, then python3
    for cmd in python3.12 python3; do
        if command -v "$cmd" &>/dev/null; then
            if $cmd -c "import sys; exit(0 if sys.version_info >= (${MIN_PYTHON_MAJOR}, ${MIN_PYTHON_MINOR}) else 1)" 2>/dev/null; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [[ -n "$python_cmd" ]]; then
        local version
        version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
        log_success "Python ${version} (${python_cmd})"
        PYTHON_BIN=$(command -v "$python_cmd")
        return 0
    fi

    log_warn "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ not found."
    echo ""
    read -p "  Install Python automatically? [Y/n]: " install_python
    if [[ "${install_python:-y}" =~ ^[Yy]$ ]]; then
        install_python_auto
    else
        log_error "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required."
        echo ""
        echo -e "  ${DIM}Manual install options:${NC}"
        echo -e "  ${DIM}  Ubuntu/Debian: sudo apt install python3.12${NC}"
        echo -e "  ${DIM}  Fedora/RHEL:   sudo dnf install python3.12${NC}"
        echo -e "  ${DIM}  From source:   https://www.python.org/downloads/${NC}"
        exit 1
    fi
}

install_python_auto() {
    log_step "Installing Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}"

    # Configure iPmartNetwork mirror for faster downloads
    if [[ "$USE_MIRROR" == "1" ]]; then
        log_info "Using iPmartNetwork mirror for packages..."
        configure_apt_mirror
    fi

    case "$OS_NAME" in
        ubuntu|debian|linuxmint)
            apt-get update -qq
            apt-get install -y -qq software-properties-common
            add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
            apt-get update -qq
            apt-get install -y -qq python3.12 python3.12-venv 2>/dev/null || \
                apt-get install -y -qq python3 2>/dev/null
            ;;
        fedora|centos|rhel|almalinux|rocky)
            dnf install -y -q python3.12 2>/dev/null || \
                dnf install -y -q python3 2>/dev/null
            ;;
        arch|manjaro)
            pacman -Sy --noconfirm python 2>/dev/null
            ;;
        *)
            log_error "Cannot auto-install Python on ${OS_NAME}."
            log_info "Please install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ manually."
            exit 1
            ;;
    esac

    # Configure pip to use iPmartNetwork mirror
    if [[ "$USE_MIRROR" == "1" ]]; then
        configure_pip_mirror
    fi

    # Verify installation
    check_python_silent || {
        log_error "Python installation failed."
        exit 1
    }
    log_success "Python installed successfully"
}

configure_apt_mirror() {
    # Set iPmartNetwork APT mirror for Ubuntu/Debian
    if [[ "$OS_NAME" == "ubuntu" || "$OS_NAME" == "debian" ]]; then
        local codename
        codename=$(lsb_release -cs 2>/dev/null || echo "jammy")
        local mirror_url="${MIRROR_BASE}/ubuntu/${codename}"

        log_info "Configuring APT mirror: ${mirror_url}"

        # Backup original sources
        cp /etc/apt/sources.list /etc/apt/sources.list.bak.veltrix 2>/dev/null || true

        # Add iPmart mirror as additional source (don't replace existing)
        cat > /etc/apt/sources.list.d/ipmartnetwork.list <<EOF
deb [trusted=yes] ${mirror_url} ${codename} main restricted universe multiverse
EOF
        log_success "APT mirror configured"
    fi
}

configure_pip_mirror() {
    # Configure pip to use iPmartNetwork PyPI mirror
    local pip_conf_dir="/etc/pip"
    mkdir -p "$pip_conf_dir"

    cat > "${pip_conf_dir}/pip.conf" <<EOF
[global]
index-url = ${MIRROR_PIP}
trusted-host = mirror.ipmartnet.work
timeout = 30
EOF

    # Also set for the veltrix user
    local user_pip_dir="${INSTALL_DIR}/.config/pip"
    mkdir -p "$user_pip_dir"
    cat > "${user_pip_dir}/pip.conf" <<EOF
[global]
index-url = ${MIRROR_PIP}
trusted-host = mirror.ipmartnet.work
timeout = 30
EOF

    log_success "pip mirror configured: ${MIRROR_PIP}"
}

check_python_silent() {
    for cmd in python3.12 python3; do
        if command -v "$cmd" &>/dev/null; then
            if $cmd -c "import sys; exit(0 if sys.version_info >= (${MIN_PYTHON_MAJOR}, ${MIN_PYTHON_MINOR}) else 1)" 2>/dev/null; then
                PYTHON_BIN=$(command -v "$cmd")
                return 0
            fi
        fi
    done
    return 1
}

install_package() {
    local pkg="$1"
    case "$OS_NAME" in
        ubuntu|debian|linuxmint) apt-get install -y -qq "$pkg" ;;
        fedora|centos|rhel|almalinux|rocky) dnf install -y -q "$pkg" ;;
        arch|manjaro) pacman -Sy --noconfirm "$pkg" ;;
        *) log_warn "Cannot install ${pkg} automatically." ;;
    esac
}

check_disk_space() {
    local available
    available=$(df -m /opt 2>/dev/null | awk 'NR==2 {print $4}')
    if [[ -n "$available" && "$available" -lt 200 ]]; then
        log_warn "Low disk space: ${available}MB available in /opt (minimum 200MB recommended)"
    fi
}

check_port() {
    if ss -tlnp 2>/dev/null | grep -q ":${DEFAULT_PORT} " ; then
        log_warn "Port ${DEFAULT_PORT} is already in use."
        log_info "You can change the port in ${ENV_FILE} after installation."
    fi
}

run_prerequisites() {
    log_step "Checking prerequisites"
    separator
    detect_os
    check_architecture
    check_systemd
    check_network_tools
    if [[ "$USE_MIRROR" == "1" ]]; then
        log_info "iPmartNetwork Mirror: ${CYAN}enabled${NC} (${MIRROR_BASE})"
    else
        log_info "iPmartNetwork Mirror: disabled (using default repos)"
    fi
    check_python
    check_disk_space
    check_port
    separator
    echo ""
    log_success "All prerequisites satisfied"
    echo ""
}

# ---------------------------------------------------------------------------
# Installation Functions
# ---------------------------------------------------------------------------

create_user() {
    log_step "Creating system user"
    if id "$VELTRIX_USER" &>/dev/null; then
        log_info "User '${VELTRIX_USER}' already exists."
    else
        groupadd --system "$VELTRIX_GROUP" 2>/dev/null || true
        useradd --system --gid "$VELTRIX_GROUP" --home "$INSTALL_DIR" \
                --no-create-home --shell /usr/sbin/nologin "$VELTRIX_USER"
        log_success "Created system user '${VELTRIX_USER}'"
    fi
}

create_directories() {
    log_step "Creating directories"
    mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$BACKUP_DIR" "$LOG_DIR"
    chown -R "${VELTRIX_USER}:${VELTRIX_GROUP}" "$INSTALL_DIR"
    log_success "Directories created"
    log_info "  Install: ${INSTALL_DIR}"
    log_info "  Data:    ${DATA_DIR}"
    log_info "  Backups: ${BACKUP_DIR}"
    log_info "  Logs:    ${LOG_DIR}"
}

copy_files() {
    log_step "Deploying application files"
    local source_dir="${1:-.}"

    # Backup existing code
    if [[ -d "${INSTALL_DIR}/outpanel" ]]; then
        local backup_name="outpanel.bak.$(date +%Y%m%d%H%M%S)"
        cp -r "${INSTALL_DIR}/outpanel" "${INSTALL_DIR}/${backup_name}" 2>/dev/null || true
        log_info "Previous version backed up as ${backup_name}"
    fi

    # Copy application
    cp -r "${source_dir}/outpanel" "$INSTALL_DIR/"
    cp -r "${source_dir}/web" "$INSTALL_DIR/"
    cp -r "${source_dir}/docs" "$INSTALL_DIR/" 2>/dev/null || true
    cp "${source_dir}/README.md" "$INSTALL_DIR/" 2>/dev/null || true
    cp "${source_dir}/README_FA.md" "$INSTALL_DIR/" 2>/dev/null || true
    cp "${source_dir}/CHANGELOG.md" "$INSTALL_DIR/" 2>/dev/null || true
    cp "${source_dir}/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true

    chown -R "${VELTRIX_USER}:${VELTRIX_GROUP}" "$INSTALL_DIR"
    log_success "Application deployed to ${INSTALL_DIR}"
}

create_env_file() {
    log_step "Configuring environment"

    if [[ -f "$ENV_FILE" ]]; then
        log_info "Configuration file exists: ${ENV_FILE}"
        log_info "Existing configuration preserved."
        return
    fi

    local encryption_key api_token
    encryption_key=$($PYTHON_BIN -c "import secrets; print(secrets.token_hex(32))")
    api_token=$($PYTHON_BIN -c "import secrets; print(secrets.token_urlsafe(32))")

    cat > "$ENV_FILE" <<EOF
# ═══════════════════════════════════════════════════════════
# Veltrix Configuration
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Version: ${VERSION}
# ═══════════════════════════════════════════════════════════

# ─── Server ───────────────────────────────────────────────
OUTPANEL_HOST=0.0.0.0
OUTPANEL_PORT=${DEFAULT_PORT}
OUTPANEL_DB=${DATA_DIR}/veltrix.db
OUTPANEL_BACKUP_DIR=${BACKUP_DIR}
OUTPANEL_MONITOR_INTERVAL=30

# ─── Logging ─────────────────────────────────────────────
OUTPANEL_LOG_DIR=${LOG_DIR}
OUTPANEL_LOG_FILE=veltrix.log
OUTPANEL_LOG_FORMAT=json
OUTPANEL_LOG_LEVEL=INFO

# ─── Security ────────────────────────────────────────────
OUTPANEL_API_TOKEN=${api_token}
OUTPANEL_ENCRYPTION_KEY=${encryption_key}

# ─── License ─────────────────────────────────────────────
OUTPANEL_REQUIRE_LICENSE=0
OUTPANEL_LICENSE_SERVER_URL=
OUTPANEL_LICENSE_KEY=
OUTPANEL_SERVER_PUBLIC_IP=

# ─── Worker ──────────────────────────────────────────────
OUTPANEL_AUTO_DISABLE_THRESHOLD=5
OUTPANEL_AUTO_DISABLE_WINDOW=30
OUTPANEL_REPORT_HOUR=8
OUTPANEL_REPORT_DAY=0

# ─── Interface ───────────────────────────────────────────
OUTPANEL_LANGUAGE=fa
EOF

    chmod 640 "$ENV_FILE"
    chown root:${VELTRIX_GROUP} "$ENV_FILE"

    log_success "Configuration created: ${ENV_FILE}"
    log_info "API Token and Encryption Key auto-generated"
}

install_service() {
    log_step "Installing systemd service"

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Veltrix — Intelligent Network Control
Documentation=https://github.com/iPmartNetwork/Veltrix
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${VELTRIX_USER}
Group=${VELTRIX_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_BIN} -m outpanel.app
Restart=always
RestartSec=5
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=veltrix

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${DATA_DIR} ${BACKUP_DIR} ${LOG_DIR}
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" --quiet
    log_success "Service installed and enabled"
}

start_service() {
    log_step "Starting Veltrix"
    systemctl restart "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "Veltrix is running"
    else
        log_error "Veltrix failed to start"
        echo ""
        echo -e "  ${DIM}Debug with: journalctl -u ${SERVICE_NAME} -n 30${NC}"
        exit 1
    fi
}

show_completion() {
    local server_ip
    server_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_SERVER_IP")

    echo ""
    echo -e "  ${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}${BOLD}  ✓  Veltrix v${VERSION} installed successfully!${NC}"
    echo -e "  ${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Dashboard${NC}        http://${server_ip}:${DEFAULT_PORT}"
    echo -e "  ${BOLD}Configuration${NC}    ${ENV_FILE}"
    echo -e "  ${BOLD}Database${NC}         ${DATA_DIR}/veltrix.db"
    echo -e "  ${BOLD}Logs${NC}             ${LOG_DIR}/veltrix.log"
    echo -e "  ${BOLD}Service${NC}          systemctl status ${SERVICE_NAME}"
    echo ""
    separator
    echo ""
    echo -e "  ${YELLOW}→ Open the dashboard and create your admin account.${NC}"
    echo -e "  ${DIM}→ Edit ${ENV_FILE} to customize settings.${NC}"
    echo -e "  ${DIM}→ View logs: journalctl -u ${SERVICE_NAME} -f${NC}"
    if [[ "$USE_MIRROR" == "1" ]]; then
        echo -e "  ${DIM}→ Mirror: ${MIRROR_BASE} (pip + apt)${NC}"
    fi
    echo -e "  ${DIM}→ Docs: https://ipmartnet.work/docs${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# Menu & Actions
# ---------------------------------------------------------------------------

show_menu() {
    echo -e "  ${BOLD}Select an action:${NC}"
    echo ""
    echo -e "    ${CYAN}1${NC})  Install Veltrix (fresh)"
    echo -e "    ${CYAN}2${NC})  Update existing installation"
    echo -e "    ${CYAN}3${NC})  Install with demo data"
    echo -e "    ${CYAN}4${NC})  Show service status"
    echo -e "    ${CYAN}5${NC})  Uninstall"
    echo -e "    ${CYAN}0${NC})  Exit"
    echo ""
    read -p "  Choice [0-5]: " choice
    echo ""

    case "${choice}" in
        1) do_install ;;
        2) do_update ;;
        3) do_install_demo ;;
        4) do_status ;;
        5) do_uninstall ;;
        0) echo "  Bye."; exit 0 ;;
        *) log_error "Invalid choice."; echo ""; show_menu ;;
    esac
}

do_install() {
    run_prerequisites
    create_user
    create_directories
    copy_files "$(cd "$(dirname "$0")/.." && pwd)"
    create_env_file
    install_service
    start_service
    show_completion
}

do_update() {
    log_step "Updating Veltrix"

    if [[ ! -d "$INSTALL_DIR/outpanel" ]]; then
        log_error "Veltrix is not installed at ${INSTALL_DIR}."
        log_info "Use fresh install instead."
        exit 1
    fi

    check_python_silent || {
        log_error "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ not found."
        exit 1
    }

    local old_version="unknown"
    if [[ -f "${INSTALL_DIR}/outpanel/__init__.py" ]]; then
        old_version=$($PYTHON_BIN -c "
import sys; sys.path.insert(0, '${INSTALL_DIR}')
from outpanel import __version__; print(__version__)
" 2>/dev/null || echo "unknown")
    fi

    log_info "Current version: ${old_version}"
    log_info "New version: ${VERSION}"

    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    copy_files "$(cd "$(dirname "$0")/.." && pwd)"
    systemctl daemon-reload
    start_service

    echo ""
    log_success "Update complete: ${old_version} → ${VERSION}"
    log_info "Database migrations will run automatically on startup."
    echo ""
}

do_install_demo() {
    do_install
    log_step "Seeding demo data"
    sudo -u "$VELTRIX_USER" bash -c "
        cd ${INSTALL_DIR}
        OUTPANEL_DB=${DATA_DIR}/veltrix.db ${PYTHON_BIN} -c '
from outpanel.demo import seed_demo_data
result = seed_demo_data()
print(f\"  Servers: {result.get(\"servers\", 0)}\")
print(f\"  Outbounds: {result.get(\"outbounds\", 0)}\")
print(f\"  Metrics: {result.get(\"metrics\", 0)}\")
'
    " 2>/dev/null || log_warn "Demo seed had issues (non-critical)"
    log_success "Demo data created"
    echo ""
}

do_status() {
    echo ""
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_success "Veltrix is ${GREEN}running${NC}"
    else
        log_warn "Veltrix is ${RED}stopped${NC}"
    fi
    echo ""
    systemctl status "$SERVICE_NAME" --no-pager 2>/dev/null || log_warn "Service not installed."
    echo ""
}

do_uninstall() {
    echo ""
    log_warn "This will remove the Veltrix service."
    log_info "Your data in ${DATA_DIR} will be preserved."
    echo ""
    read -p "  Continue? [y/N]: " confirm
    if [[ "${confirm:-n}" != "y" && "${confirm:-n}" != "Y" ]]; then
        log_info "Cancelled."
        exit 0
    fi

    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload

    echo ""
    log_success "Service removed."
    log_info "Data preserved: ${DATA_DIR}"
    log_info "Config preserved: ${ENV_FILE}"
    log_info "To fully remove: rm -rf ${INSTALL_DIR} ${ENV_FILE}"
    echo ""
}

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

print_banner
check_root

case "${1:-}" in
    --install)   do_install ;;
    --update)    do_update ;;
    --demo)      do_install_demo ;;
    --uninstall) do_uninstall ;;
    --status)    do_status ;;
    --help|-h)
        echo "  Usage: sudo bash $0 [--install|--update|--demo|--uninstall|--status]"
        echo ""
        echo "  Without arguments, shows an interactive menu."
        exit 0
        ;;
    *)  show_menu ;;
esac
