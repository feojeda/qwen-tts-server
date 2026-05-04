#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export HF_HOME="${SCRIPT_DIR}/cache/hf"
export HF_HUB_ENABLE_HF_TRANSFER=1
export PYTHONPATH="${SCRIPT_DIR}"

if [ -d "${SCRIPT_DIR}/venv" ]; then
    PYTHON="${SCRIPT_DIR}/venv/bin/python"
elif [ -d "${SCRIPT_DIR}/.venv" ]; then
    PYTHON="${SCRIPT_DIR}/.venv/bin/python"
else
    echo "ERROR: Virtual environment not found."
    echo "Run setup first:  bash setup.sh"
    exit 1
fi

echo "=========================================="
echo "   Qwen3-TTS — Pre-download Models"
echo "=========================================="
echo ""
echo "Cache directory: ${HF_HOME}"
echo ""

exec "$PYTHON" "${SCRIPT_DIR}/scripts/pre_download.py" "$@"
