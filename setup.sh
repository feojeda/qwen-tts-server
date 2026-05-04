#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

echo "=========================================="
echo "   Qwen3-TTS API Server — Setup"
echo "=========================================="
echo ""

MIN_PY_MAJOR=3
MIN_PY_MINOR=10

MIN_DISK_GB_SETUP=5

check_disk_space() {
    local path="$1"
    local min_gb="$2"
    local label="$3"
    local avail_kb
    avail_kb=$(df -k "$path" 2>/dev/null | tail -1 | awk '{print $4}')
    if [ -z "$avail_kb" ]; then
        warn "Could not check disk space for ${label}."
        return
    fi
    local avail_gb
    avail_gb=$(python3 -c "print(${avail_kb} / 1024 / 1024)")
    if python3 -c "exit(0 if ${avail_gb} < ${min_gb} else 1)"; then
        error "Insufficient disk space for ${label}."
        error "  Available: ${avail_gb%.*} GB"
        error "  Required:  ~${min_gb} GB"
        exit 1
    fi
    ok "${avail_gb%.*} GB available for ${label}."
}

detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v brew &>/dev/null; then
        echo "brew"
    else
        echo "unknown"
    fi
}

runas_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo &>/dev/null; then
        sudo "$@"
    else
        error "No sudo access. Please run this script as root or install sudo."
        exit 1
    fi
}

if ! command -v python3 &>/dev/null; then
    error "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ is required but not found."
    error ""
    error "Install it with:"
    error "  Debian/Ubuntu:  sudo apt install python3 python3-venv"
    error "  Fedora/RHEL:    sudo dnf install python3"
    error "  Arch Linux:     sudo pacman -S python"
    error "  macOS:          brew install python@3.12"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt "$MIN_PY_MAJOR" ] || { [ "$PY_MAJOR" -eq "$MIN_PY_MAJOR" ] && [ "$PY_MINOR" -lt "$MIN_PY_MINOR" ]; }; then
    error "Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ required (found ${PY_VERSION})."
    error "Please upgrade Python and re-run setup."
    exit 1
fi

ok "Python ${PY_VERSION} detected"

ensure_sox() {
    if command -v sox &>/dev/null; then
        return 0
    fi

    warn "sox not found. Required by librosa for audio processing."
    local pkg_manager
    pkg_manager=$(detect_pkg_manager)

    case "$pkg_manager" in
        apt)
            info "Installing sox via apt..."
            runas_root apt-get install -y -qq sox
            ;;
        dnf)
            info "Installing sox via dnf..."
            runas_root dnf install -y sox
            ;;
        pacman)
            info "Installing sox via pacman..."
            runas_root pacman -Sy --noconfirm sox
            ;;
        brew)
            info "Installing sox via Homebrew..."
            brew install sox
            ;;
        *)
            error "Cannot auto-install sox on this system."
            error "Please install it manually and re-run setup."
            exit 1
            ;;
    esac

    if ! command -v sox &>/dev/null; then
        error "sox installation failed. Install it manually and re-run setup."
        exit 1
    fi

    ok "sox installed."
}

ensure_sox

ensure_venv_module() {
    if python3 -c "import ensurepip" &>/dev/null; then
        return 0
    fi

    warn "python3-venv module not found."
    local pkg_manager
    pkg_manager=$(detect_pkg_manager)

    case "$pkg_manager" in
        apt)
            local pkg="python3.${PY_MINOR}-venv"
            info "Installing ${pkg} via apt..."
            runas_root apt-get update -qq
            runas_root apt-get install -y -qq "$pkg"
            ;;
        dnf)
            info "Installing python3-venv via dnf..."
            runas_root dnf install -y python3-venv
            ;;
        pacman)
            error "Arch Linux — venv is bundled with python. Something is wrong with your Python installation."
            exit 1
            ;;
        brew)
            error "macOS — venv is bundled with Homebrew's python. Something is wrong with your Python installation."
            exit 1
            ;;
        *)
            error "Cannot auto-install python3-venv on this system."
            error "Please install it manually and re-run setup."
            exit 1
            ;;
    esac

    if ! python3 -c "import ensurepip" &>/dev/null; then
        error "Installation failed. Install python3-venv manually and re-run setup."
        exit 1
    fi

    ok "python3-venv installed."
}

ensure_venv_module

check_disk_space "$SCRIPT_DIR" "$MIN_DISK_GB_SETUP" "venv + dependencies"

VENV_PYTHON="${SCRIPT_DIR}/${VENV_DIR}/bin/python3"
VENV_PIP="${SCRIPT_DIR}/${VENV_DIR}/bin/pip"

if [ -d "$VENV_DIR" ] && [ -x "$VENV_PYTHON" ] && [ -x "$VENV_PIP" ]; then
    info "Virtual environment '${VENV_DIR}' already exists — reusing it."
else
    if [ -d "$VENV_DIR" ]; then
        warn "Virtual environment '${VENV_DIR}' is incomplete — recreating it."
        rm -rf "$VENV_DIR"
    else
        info "Creating virtual environment '${VENV_DIR}'..."
    fi
    python3 -m venv "$VENV_DIR"
    ok "Virtual environment created."
fi

PIP="$VENV_PIP"

info "Upgrading pip..."
"$PIP" install --upgrade pip --quiet

info "Installing dependencies from requirements.txt..."
"$PIP" install -r "${SCRIPT_DIR}/requirements.txt"

ok "All dependencies installed."
echo ""
echo "=========================================="
echo "   Setup complete!"
echo "=========================================="
echo ""
echo "  Run the server with:"
echo "    bash start.sh"
echo ""
