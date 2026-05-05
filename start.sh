#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export HF_HOME="${SCRIPT_DIR}/cache/hf"
export HF_HUB_ENABLE_HF_TRANSFER=1
export PYTHONPATH="${SCRIPT_DIR}"

MIN_DISK_GB_MODELS=10

echo "=========================================="
echo "   Qwen3-TTS API Server"
echo "=========================================="
echo ""
echo "Models cached in: ${HF_HOME}"
if [ -n "${HF_ENDPOINT}" ]; then
    echo "Mirror endpoint: ${HF_ENDPOINT}"
fi
echo ""

if [ -d "${SCRIPT_DIR}/venv" ]; then
    PYTHON="${SCRIPT_DIR}/venv/bin/python"
elif [ -d "${SCRIPT_DIR}/.venv" ]; then
    PYTHON="${SCRIPT_DIR}/.venv/bin/python"
else
    echo "ERROR: Virtual environment not found."
    echo "Run setup first:  bash setup.sh"
    exit 1
fi

avail_kb=$(df -k "$SCRIPT_DIR" 2>/dev/null | tail -1 | awk '{print $4}')
if [ -n "$avail_kb" ]; then
    avail_gb=$(python3 -c "print(round(${avail_kb} / 1024 / 1024))")
    if [ "$avail_gb" -lt "$MIN_DISK_GB_MODELS" ]; then
        echo "ERROR: Insufficient disk space for AI models."
        echo "  Available: ${avail_gb} GB"
        echo "  Required:  ~${MIN_DISK_GB_MODELS} GB"
        echo ""
        echo "Models are cached in: ${HF_HOME}"
        echo "Free up space or move HF_HOME to another drive."
        exit 1
    fi
    echo "Disk space: ${avail_gb} GB available"
fi

echo ""
echo "Checking models..."
"$PYTHON" "${SCRIPT_DIR}/scripts/pre_download.py" || {
    echo ""
    echo "ERROR: Model download failed. Check your connection and retry."
    exit 1
}

echo ""
echo "Starting server..."
exec "$PYTHON" "${SCRIPT_DIR}/main.py"
