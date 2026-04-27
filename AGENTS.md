# Agent Notes for qwen-tts-server

## Quick Start (Windows)

```powershell
# 1. Install (one-time)
python -m venv venv
.\venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
.\venv\Scripts\pip install -r requirements.txt

# 2. Run
.\venv\Scripts\python.exe main.py        # server on :8000
# or: .\start.bat

# 3. Test (fast, no GPU needed)
.\venv\Scripts\python.exe -m pytest tests\ -v
```

## Architecture That Matters

**Single-file FastAPI app** (`main.py`, ~540 LOC). Three global `Qwen3TTSModel` instances managed manually:

| Model | Mode | VRAM | Endpoint |
|-------|------|------|----------|
| CustomVoice (1.7B) | **HOT** — always in GPU | ~5.5 GB | `/v1/audio/speech` |
| VoiceDesign (1.7B) | **LAZY** — loaded on demand | ~5.5 GB | `/v1/audio/voice-design` |
| Base/Clone (1.7B) | **LAZY** — loaded on demand | ~5.5 GB | `/v1/audio/voice-clone` |

**VRAM Pool rule:** VoiceDesign and Base/Clone are **mutually exclusive** on GPU. When one is requested while the other is loaded, the server unloads the incumbent first (`torch.cuda.empty_cache()`). CustomVoice never unloads.

**Threading:** A single `threading.Lock()` (`model_lock`) serializes all lazy load/unload operations. The internal helpers (`_do_load_*`, `_do_unload_*`) assume the lock is already held; the public helpers (`_get_voice_*`) acquire it. **Never nest `with model_lock:`** — caused a deadlock in an earlier version.

## Stateless Voice Clone Prompts

The server **never persists voice profiles** between requests.

- `POST /v1/audio/voice-clone/prompt` → returns `voice_clone_prompt_b64` (a base64-encoded `torch.save` blob)
- `POST /v1/audio/voice-clone/generate` → client sends back the same `voice_clone_prompt_b64`
- The client (not this server) is responsible for storing the blob in SQLite/Redis/etc.

There is **no prompt store**, **no disk cache for prompts**, and **no TTL management** in this codebase. If a previous version had `prompts_cache/` or in-memory dicts, that has been removed.

## Environment Variables

```bash
QWEN_TTS_HOST=0.0.0.0
QWEN_TTS_PORT=8000
QWEN_CUSTOM_VOICE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
QWEN_VOICE_DESIGN_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
QWEN_VOICE_CLONE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
QWEN_LAZY_TIMEOUT_SECONDS=300   # auto-unload idle lazy models
```

## Testing

```powershell
# Unit tests (schemas, endpoints, no model loading)
.\venv\Scripts\python.exe -m pytest tests\ -v

# Integration tests (require ~12 GB VRAM, several minutes each)
.\venv\Scripts\python.exe -m pytest tests\ -v --run-integration
```

Integration tests are marked `@pytest.mark.skip` by default because they trigger HuggingFace downloads and GPU model loads.

## Docker

```bash
docker build -t qwen-tts-server .
docker run --gpus all -p 8000:8000 qwen-tts-server
```

Base image: `nvidia/cuda:12.6.0-runtime-ubuntu22.04`. Requires NVIDIA Container Toolkit for GPU passthrough.

## Common Pitfalls

- **Do not run on < 12 GB VRAM** with the default 1.7B models. Use 0.6B variants via env vars if constrained.
- **First lazy load is slow** (~10-30s) because it downloads from HuggingFace if not cached. Subsequent loads are faster.
- **CPU mode works** but set `QWEN_TTS_DEVICE=cpu` and expect 10-30x slower generation.
- **The `voice_clone_prompt_b64` blobs are large** (~hundreds of KB to a few MB). Don't store them in session cookies or URL params.

## Tech Stack

- FastAPI + Pydantic v2
- Uvicorn (single worker by default — requests are serialized)
- PyTorch 2.11 + CUDA 12.6
- `qwen-tts` Python package (wraps HuggingFace Transformers)
- pytest + fastapi.testclient for tests
