# ------------------------------------------------------------------------------
# Qwen TTS Server - Dockerfile
# ------------------------------------------------------------------------------
# Build:
#   docker build -t qwen-tts-server .
#
# Run (requires NVIDIA Container Toolkit):
#   docker run --gpus all -p 8000:8000 qwen-tts-server
#
# Run without GPU (CPU-only, slower):
#   docker run -p 8000:8000 -e QWEN_TTS_DEVICE=cpu qwen-tts-server
# ------------------------------------------------------------------------------

FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04

LABEL maintainer="Qwen TTS Developer"
LABEL description="Qwen3-TTS REST API Server with CUDA 12.6 support"

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3-pip \
    python3.12-venv \
    libsndfile1 \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install PyTorch with CUDA 12.6
RUN pip3 install --no-cache-dir \
    torch==2.11.0 \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cu126

# Copy requirements first (for layer caching)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY start.bat .
COPY README.md .

# Create cache directories for HuggingFace
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python3", "main.py"]
