#!/bin/bash
set -euo pipefail

APP_NAME="qwen-tts-server"
BASE_DIR="/opt/${APP_NAME}"
CURRENT_LINK="${BASE_DIR}/current"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*" >&2; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*" >&2; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root (use sudo)."
    exit 1
fi

echo "=========================================="
echo "   Qwen3-TTS Server — Rollback"
echo "=========================================="
echo ""

if [ ! -d "${BASE_DIR}/releases" ]; then
    error "No releases found at ${BASE_DIR}/releases."
    exit 1
fi

echo "Available releases:"
echo ""
current_target=""
if [ -L "${CURRENT_LINK}" ]; then
    current_target="$(readlink -f "${CURRENT_LINK}")"
fi

releases=()
index=0
while IFS= read -r release; do
    releases+=("${release}")
    if [ "${release}" = "${current_target}" ]; then
        echo "  [${index}] $(basename "${release}")  <-- current"
    else
        echo "  [${index}] $(basename "${release}")"
    fi
    index=$((index + 1))
done < <(ls -1d "${BASE_DIR}"/releases/v* 2>/dev/null | sort)

if [ ${#releases[@]} -eq 0 ]; then
    error "No releases found."
    exit 1
fi

echo ""
read -rp "Select release to rollback to [0-$(( ${#releases[@]} - 1 ))]: " choice

if ! [[ "${choice}" =~ ^[0-9]+$ ]] || [ "${choice}" -ge ${#releases[@]} ]; then
    error "Invalid selection."
    exit 1
fi

selected="${releases[${choice}]}"

if [ "${selected}" = "${current_target}" ]; then
    error "Already on this version."
    exit 1
fi

info "Rolling back to $(basename "${selected}")..."

ln -sfn "${selected}" "${CURRENT_LINK}"
ok "Symlink: ${CURRENT_LINK} -> ${selected}"

if command -v nomad &>/dev/null && nomad server members 2>/dev/null | grep -q "alive"; then
    info "Restarting Nomad job to pick up rollback..."
    nomad job restart "${APP_NAME}" 2>/dev/null || {
        warn "Could not restart via Nomad. Job may not be running."
        info "Deploy when ready: sudo bash scripts/deploy.sh"
    }
    ok "Nomad job restarted."
else
    warn "Nomad not running. Start it and run: sudo bash scripts/deploy.sh"
fi

echo ""
ok "Rollback complete. Active version: $(basename "${selected}")"
echo ""
