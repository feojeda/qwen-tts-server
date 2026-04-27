# Qwen TTS Server

REST API for [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) with multi-model support, VRAM lazy loading, and stateless voice clone prompts.

> **Leer en español:** [README.es.md](README.es.md)

## Features

- **3 models in a single server:**
  - `CustomVoice` (1.7B) — Predefined voices, always on GPU
  - `VoiceDesign` (1.7B) — Voice design by description, lazy loaded
  - `Base/Clone` (1.7B) — Voice cloning, lazy loaded
- **Lazy Loading + VRAM Pool:** Only CustomVoice stays on GPU. VoiceDesign and Base/Clone share VRAM and load on demand.
- **Stateless Voice Clone Prompts:** Server holds no state. Prompts are serialized to base64 and stored by the client.
- **OpenAI-compatible:** Endpoints under `/v1/audio/speech`, `/v1/models`, etc.
- **Auto-unload:** Lazy models unload automatically after inactivity.

## Requirements

- Python 3.12+
- CUDA 12.6+ (for GPU)
- ~12 GB VRAM (RTX 3060 or better recommended)

## Installation

```bash
git clone <repo-url>
cd qwen-tts-server
python -m venv venv

# Windows
.\venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
.\venv\Scripts\pip install -r requirements.txt

# Linux/Mac
# pip install torch torchvision torchaudio
# pip install -r requirements.txt
```

## Usage

```bash
# Start server
.\venv\Scripts\python.exe main.py

# Or on Linux/Mac
# python main.py
```

Server listens on `http://0.0.0.0:8000` by default.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/speech` | `POST` | TTS with predefined voice (OpenAI-compatible) |
| `/v1/audio/voice-design` | `POST` | Voice design by description |
| `/v1/audio/voice-clone` | `POST` | Voice cloning with reference audio |
| `/v1/audio/voice-clone/prompt` | `POST` | Calculate reusable prompt (returns base64) |
| `/v1/audio/voice-clone/generate` | `POST` | Generate audio from base64 prompt |
| `/v1/models` | `GET` | List loaded models |
| `/v1/audio/voices` | `GET` | List available voices |
| `/health` | `GET` | Health check |
| `/docs` | `GET` | Interactive documentation (Swagger UI) |

## Examples

### TTS with predefined voice

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hello world",
    "voice": "Vivian",
    "language": "English",
    "response_format": "wav"
  }' \
  --output speech.wav
```

### Voice Clone (stateless)

**1. Create prompt:**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "ref_audio": "https://example.com/my_voice.wav",
    "ref_text": "Exact transcript of the reference audio"
  }'
```

Save `voice_clone_prompt_b64` from the response.

**2. Generate audio:**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hello, this is my cloned voice",
    "voice_clone_prompt_b64": "<the-saved-base64>",
    "response_format": "wav"
  }' \
  --output clone.wav
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QWEN_TTS_HOST` | `0.0.0.0` | Listen host |
| `QWEN_TTS_PORT` | `8000` | Port |
| `QWEN_CUSTOM_VOICE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | CustomVoice model |
| `QWEN_VOICE_DESIGN_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | VoiceDesign model |
| `QWEN_VOICE_CLONE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Base/Clone model |
| `QWEN_LAZY_TIMEOUT_SECONDS` | `300` | Seconds before auto-unload |

## VRAM Architecture

```
CustomVoice (1.7B)  -> GPU HOT   (~5.5 GB, always)
VoiceDesign (1.7B)  -> GPU LAZY  (~5.5 GB, exclusive)
Base/Clone  (1.7B)  -> GPU LAZY  (~5.5 GB, exclusive)
```

VoiceDesign and Base/Clone are **never loaded simultaneously**.

## Testing

```bash
# Unit tests (fast, no model loading)
pytest tests/ -v

# Integration tests (slow, require GPU)
pytest tests/ -v --run-integration
```

## Docker

```bash
# Build
docker build -t qwen-tts-server .

# Run with GPU
docker run --gpus all -p 8000:8000 qwen-tts-server

# Run CPU-only
docker run -p 8000:8000 -e QWEN_TTS_DEVICE=cpu qwen-tts-server
```

Base image: `nvidia/cuda:12.6.0-runtime-ubuntu22.04`. Requires NVIDIA Container Toolkit for GPU passthrough.

## License

Apache 2.0 (same as Qwen3-TTS)
