#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="qwen-tts-server"
BASE_DIR="/opt/${APP_NAME}"
CURRENT_LINK="${BASE_DIR}/current"

for f in /etc/nomad.d/.acl.env /etc/qwen-tts-server/consul.env; do
    if [ -f "${f}" ]; then
        set -a; source "${f}"; set +a
    fi
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*" >&2; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*" >&2; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

echo "=========================================="
echo "   Qwen3-TTS Server — Deploy via Nomad"
echo "=========================================="
echo ""

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        error "This script must be run as root (use sudo)."
        exit 1
    fi
}

check_nomad() {
    if ! command -v nomad &>/dev/null; then
        error "Nomad CLI not found. Install it first."
        exit 1
    fi

    if ! nomad server members 2>/dev/null | grep -q "alive"; then
        error "Nomad server is not running."
        error "Start it first: sudo systemctl start nomad"
        exit 1
    fi

    ok "Nomad is running."
}

ensure_raw_exec() {
    local nomad_config="/etc/nomad.d/nomad.hcl"

    if ! nomad node status -verbose -self 2>/dev/null | grep -q "raw_exec.*true"; then
        info "Enabling raw_exec driver in Nomad..."

        if [ ! -f "${nomad_config}" ]; then
            error "Nomad config not found at ${nomad_config}."
            exit 1
        fi

        if grep -q "driver.raw_exec.enable" "${nomad_config}"; then
            sed -i 's/"driver.raw_exec.enable"\s*=\s*"[01]"/"driver.raw_exec.enable" = "1"/' "${nomad_config}"
        elif grep -q "^client {" "${nomad_config}"; then
            sed -i '/^client {/a\\  options = {\n    "driver.raw_exec.enable" = "1"\n  }' "${nomad_config}"
        else
            echo -e '\nclient {\n  enabled = true\n  options = {\n    "driver.raw_exec.enable" = "1"\n  }\n}' >> "${nomad_config}"
        fi

        info "Restarting Nomad..."
        systemctl restart nomad
        sleep 3

        if nomad node status -verbose -self 2>/dev/null | grep -q "raw_exec.*true"; then
            ok "raw_exec driver enabled."
        else
            warn "Could not verify raw_exec. Job may fail."
        fi
    else
        ok "raw_exec driver already enabled."
    fi
}

check_source() {
    if [ ! -f "${SCRIPT_DIR}/main.py" ]; then
        error "main.py not found in ${SCRIPT_DIR}."
        error "Run this script from the qwen-tts-server project root."
        exit 1
    fi

    if [ ! -f "${SCRIPT_DIR}/requirements.txt" ]; then
        error "requirements.txt not found."
        exit 1
    fi
}

get_version() {
    if [ -d "${CURRENT_LINK}" ]; then
        local current_target
        current_target="$(readlink -f "${CURRENT_LINK}")"
        basename "${current_target}"
    else
        echo "none"
    fi
}

next_version() {
    local current
    current="$(get_version)"
    if [ "$current" = "none" ]; then
        echo "v001"
        return
    fi
    local num
    num="${current#v}"
    num=$((10#$num + 1))
    printf "v%03d" "${num}"
}

deploy_version() {
    local version="$1"
    local target_dir="${BASE_DIR}/releases/${version}"

    info "Creating release ${version}..."
    mkdir -p "${target_dir}"

    info "Copying application code..."
    cp "${SCRIPT_DIR}/main.py" "${target_dir}/"
    cp -r "${SCRIPT_DIR}/app" "${target_dir}/"
    cp "${SCRIPT_DIR}/requirements.txt" "${target_dir}/"
    mkdir -p "${target_dir}/scripts"

    local needs_venv=true
    if [ -d "${target_dir}/venv" ] && [ -x "${target_dir}/venv/bin/python" ]; then
        needs_venv=false
    fi

    if [ "$needs_venv" = true ]; then
        info "Creating virtual environment..."
        python3 -m venv "${target_dir}/venv"
        "${target_dir}/venv/bin/pip" install --upgrade pip --quiet
    fi

    info "Installing dependencies..."
    "${target_dir}/venv/bin/pip" install -r "${target_dir}/requirements.txt" --quiet

    ok "Release ${version} ready at ${target_dir}."
    echo "${target_dir}"
}

update_symlink() {
    local target_dir="$1"

    info "Updating current symlink..."
    ln -sfn "${target_dir}" "${CURRENT_LINK}"
    ok "Symlink updated: ${CURRENT_LINK} -> ${target_dir}"
}

setup_cache() {
    mkdir -p "${BASE_DIR}/cache"

    if [ ! -e "${BASE_DIR}/cache/hf" ]; then
        local source_cache="${SCRIPT_DIR}/cache/hf"
        if [ -d "${source_cache}" ] && [ "$(du -sb "${source_cache}" 2>/dev/null | cut -f1)" -gt 1048576 ]; then
            info "Linking to existing model cache (${source_cache})..."
            ln -s "${source_cache}" "${BASE_DIR}/cache/hf"
        else
            mkdir -p "${BASE_DIR}/cache/hf"
            info "Model cache created (empty — models will download on first start)."
        fi
    fi

    ok "Cache: ${BASE_DIR}/cache/hf"
}

setup_env() {
    if [ ! -f "${BASE_DIR}/env.vars" ]; then
        info "Creating default env.vars..."
        cp "${SCRIPT_DIR}/scripts/env.vars" "${BASE_DIR}/env.vars"
        ok "Config: ${BASE_DIR}/env.vars"
    else
        ok "Config exists: ${BASE_DIR}/env.vars (not overwritten)"
    fi
}

ensure_model_cache() {
    if [ ! -d "${BASE_DIR}/cache/hf" ] || [ -z "$(ls -A "${BASE_DIR}/cache/hf}" 2>/dev/null)" ]; then
        info "Pre-downloading models (first deploy only)..."
        HF_HOME="${BASE_DIR}/cache/hf" \
        PYTHONPATH="${CURRENT_LINK}" \
        "${CURRENT_LINK}/venv/bin/python" "${CURRENT_LINK}/scripts/pre_download.py" || {
            warn "Model pre-download failed. Models will download on first request."
        }
    else
        ok "Model cache exists."
    fi
}

deploy_nomad_job() {
    local nomad_job="${SCRIPT_DIR}/scripts/qwen-tts.nomad"
    local env_file="${BASE_DIR}/env.vars"

    if [ ! -f "${nomad_job}" ]; then
        error "Nomad job file not found: ${nomad_job}"
        exit 1
    fi

    local tmp_job
    tmp_job="$(mktemp)"
    cp "${nomad_job}" "${tmp_job}"

    if [ -f "${env_file}" ]; then
        info "Injecting env.vars into Nomad job..."
        local env_block=""
        while IFS='=' read -r key value; do
            key="$(echo "${key}" | xargs)"
            value="$(echo "${value}" | xargs)"
            if [[ -n "${key}" && ! "${key}" =~ ^# ]]; then
                env_block+="        ${key} = \"${value}\"\n"
            fi
        done < "${env_file}"

        if [ -n "${env_block}" ]; then
            sed -i "/^      env {/,/^      }/c\\      env {\n        HF_HOME                   = \"/opt/qwen-tts-server/cache/hf\"\n        HF_HUB_ENABLE_HF_TRANSFER = \"1\"\n        PYTHONPATH                = \"/opt/qwen-tts-server/current\"\n${env_block}      }" "${tmp_job}"
        fi
    fi

    info "Deploying to Nomad..."
    nomad job run "${tmp_job}"
    rm -f "${tmp_job}"
    ok "Nomad job submitted."
}

cleanup_old_releases() {
    local keep="${KEEP_RELEASES:-3}"
    local count
    count=$(ls -1d "${BASE_DIR}"/releases/v* 2>/dev/null | wc -l)

    if [ "$count" -le "$keep" ]; then
        return
    fi

    info "Cleaning up old releases (keeping last ${keep})..."
    ls -1d "${BASE_DIR}"/releases/v* | sort | head -n -"${keep}" | while read -r old_release; do
        if [ "$(readlink -f "${CURRENT_LINK}")" != "${old_release}" ]; then
            info "Removing old release: $(basename "${old_release}")"
            rm -rf "${old_release}"
        fi
    done
    ok "Cleanup done."
}

print_summary() {
    local version
    version="$(get_version)"

    echo ""
    echo "=========================================="
    echo "   Deploy Complete!"
    echo "=========================================="
    echo ""
    echo "  Version:       ${version}"
    echo "  Install dir:   ${CURRENT_LINK}"
    echo "  Cache:         ${BASE_DIR}/cache/hf"
    echo "  Port:          8000"
    echo "  API docs:      http://localhost:8000/docs"
    echo ""
    echo "  Nomad:"
    echo "    nomad job status ${APP_NAME}"
    echo "    nomad job restart ${APP_NAME}"
    echo "    nomad job stop ${APP_NAME}"
    echo "    nomad job revert ${APP_NAME} <version>"
    echo ""
    echo "  Consul:"
    echo "    UI:  http://localhost:8500"
    echo "    API: curl http://localhost:8500/v1/agent/service/${APP_NAME}-1"
    echo ""
    echo "  Logs:"
    echo "    nomad logs -f <alloc-id>"
    echo "    nomad logs -f -stderr <alloc-id>"
    echo ""
}

check_root
check_nomad
ensure_raw_exec
check_source

VERSION="$(next_version)"
info "Deploying version ${VERSION}..."
echo ""

setup_cache
setup_env
TARGET_DIR="$(deploy_version "${VERSION}")"
update_symlink "${TARGET_DIR}"
ensure_model_cache
deploy_nomad_job
cleanup_old_releases
print_summary
