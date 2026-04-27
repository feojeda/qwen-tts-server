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

**Modular FastAPI app** (`main.py` is a thin entrypoint; all logic lives in `app/`).
Three global `Qwen3TTSModel` instances managed manually:

```
main.py              # thin entrypoint (imports app.main)
app/
  __init__.py
  i18n.py            # OS language detection + translations (es/zh/ja/en)
  config.py          # env vars, VRAM auto-detection, model selection
  schemas.py         # Pydantic request/response models
  models.py          # model lifecycle, VRAM pool, prompt serialization
  main.py            # FastAPI app, lifespan, routes
```

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
# Unit tests (schemas, endpoints, no model loading — fast)
.\venv\Scripts\python.exe -m pytest tests\ -v

# Integration tests (require ~12 GB VRAM, several minutes each)
.\venv\Scripts\python.exe -m pytest tests\test_integration.py -v --run-integration
```

| Test suite | Files | Model loading | Speed | Runs in CI |
|-----------|-------|---------------|-------|-----------|
| **Unit** | `test_*.py` except `test_integration.py` | Mocked (no downloads) | ~0.5s | ✅ Yes |
| **Integration** | `test_integration.py` only | Real models from HuggingFace | ~5-15 min | ❌ No |

Integration tests are marked `@pytest.mark.integration` and are **skipped by default**. They load real Qwen3-TTS models, download weights on first run, and generate actual audio. Only run them locally when you want to verify end-to-end behavior with real hardware.

## Model Cache Location

By default, HuggingFace downloads models to the user's home directory (`~/.cache/huggingface/hub/` on Linux/Mac, `%USERPROFILE%\.cache\huggingface\hub\` on Windows). This project overrides the cache to the project folder so models stay on the same drive as the code.

| Variable | Default (overridden) | Project location |
|----------|---------------------|------------------|
| `HF_HOME` | `~/.cache/huggingface` | `./cache/hf/` |

**`start.bat`** and **`start.sh`** set this automatically. If you run `main.py` manually, set it yourself:

```powershell
# Windows
$env:HF_HOME="E:\qwentts\cache\hf"
.\venv\Scripts\python.exe main.py
```

```bash
# Linux/Mac
export HF_HOME="/path/to/qwen-tts-server/cache/hf"
./venv/bin/python main.py
```

The `cache/` directory is already in `.gitignore`.

## Docker

```bash
docker build -t qwen-tts-server .
docker run --gpus all -p 8000:8000 qwen-tts-server
```

Base image: `nvidia/cuda:12.6.0-runtime-ubuntu22.04`. Requires NVIDIA Container Toolkit for GPU passthrough.

## VRAM Auto-Detection

On startup, the server detects available VRAM and **automatically selects model sizes**:

| VRAM Available | Models Selected | Approx. Peak Usage |
|----------------|----------------|-------------------|
| **≥ 11 GB** | 1.7B for all three | ~11 GB peak |
| **7.5 – 10.9 GB** | 0.6B CustomVoice + Base, 1.7B VoiceDesign | ~7.5 GB peak |
| **5.5 – 7.4 GB** | 0.6B for all three | ~4 GB peak |
| **< 5.5 GB or CPU** | 0.6B for all three | ~4-5 GB RAM |

To override auto-detection, set the env vars manually:
```bash
QWEN_CUSTOM_VOICE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
QWEN_VOICE_DESIGN_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
QWEN_VOICE_CLONE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
```

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

## Git Workflow (Git Flow)

**`develop`** is the default branch. All feature work branches from and merges back into `develop`.

```
main       ●────────────────────────────────────●
            ↑                                    ↑
develop    ●────●────────────────────────●──────●
                ↑                        ↑
feature/foo    ●────●────●              ↑
                                     ↑
release/v1                          ●────●────●
```

### Branch rules

| Branch | Purpose | Base | Merge target |
|--------|---------|------|--------------|
| `main` | Production releases only | — | — |
| `develop` | Integration branch for all work | `main` | — |
| `feature/*` | New features, fixes, refactors | `develop` | `develop` |
| `release/v*` | Version release preparation | `develop` | `main` + `develop` |
| `hotfix/*` | Urgent production fixes | `main` | `main` + `develop` |

### Creating a feature branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/mi-nueva-feature
# ... work ...
git push -u origin feature/mi-nueva-feature
# Open PR targeting develop
```

### Creating a release

```bash
git checkout develop
git checkout -b release/v1.2.0
# ... bump version, update changelog, final QA ...
git push -u origin release/v1.2.0
# Open PR targeting main
# After merge, tag: git tag v1.2.0
# Then merge back to develop
```

### Important

- **Never push directly to `main` or `develop`**. Always use Pull Requests.
- **All PRs must target `develop`** (except release/hotfix PRs targeting `main`).
- **`main` should only contain tagged releases**.
