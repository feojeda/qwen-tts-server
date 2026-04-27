#!/bin/bash

# Set HuggingFace cache to project folder instead of ~/.cache
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HF_HOME="${SCRIPT_DIR}/cache/hf"
export TRANSFORMERS_CACHE="${HF_HOME}"

echo "=========================================="
echo "   Qwen3-TTS API Server"
echo "=========================================="
echo ""
echo "IMPORTANT: This server downloads AI models on first run."
echo "- CustomVoice (1.7B): ~3.4 GB download on first startup"
echo "- VoiceDesign (1.7B): ~3.4 GB download on first use"
echo "- Base/Clone  (1.7B): ~3.4 GB download on first use"
echo ""
echo "Models are cached in: ${HF_HOME}"
echo "After first download, startup is instant."
echo ""
read -p "Press Enter to start the server..."
echo ""
echo "Starting server..."

# Check if venv exists
if [ -d "venv" ]; then
    ./venv/bin/python main.py
elif [ -d ".venv" ]; then
    ./.venv/bin/python main.py
else
    echo "Virtual environment not found. Please create one first:"
    echo "  python -m venv venv"
    echo "  ./venv/bin/pip install -r requirements.txt"
    exit 1
fi
