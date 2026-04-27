# Contributing to Qwen TTS Server

Thank you for your interest! This project started as a personal solution to run Qwen3-TTS on a 12 GB VRAM GPU (RTX 3060) using lazy loading and a VRAM pool. All improvements are welcome.

## Development Setup

```bash
git clone https://github.com/feojeda/qwen-tts-server.git
cd qwen-tts-server
python -m venv venv

# Windows
.\venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
.\venv\Scripts\pip install -r requirements.txt

# Linux / Mac
# pip install torch torchvision torchaudio
# pip install -r requirements.txt
```

Run tests before submitting:
```bash
pytest tests/ -v
```

## Branching & Pull Requests

We follow [Git Flow](AGENTS.md#git-workflow). All feature work branches from and merges back into `develop`.

| Type | Branch from | Merge to | Example |
|------|-------------|----------|---------|
| Feature | `develop` | `develop` | `feature/streaming-output` |
| Bugfix | `develop` | `develop` | `fix/vram-leak` |
| Hotfix | `main` | `main` + `develop` | `hotfix/crash-on-empty-audio` |
| Release | `develop` | `main` + `develop` | `release/v1.1.0` |

### PR Checklist

- [ ] Branch from latest `develop`
- [ ] `pytest tests/ -v` passes
- [ ] Code follows existing style (black-compatible, type hints where helpful)
- [ ] If you changed architecture/configs, update `AGENTS.md`
- [ ] If you changed user-facing behavior, update all 4 READMEs (`README.md`, `README.es.md`, `README.zh.md`, `README.ja.md`)

## Open Ideas (Help Wanted)

These are things we'd love to have but haven't built yet. Comment on the issue before starting to avoid duplicate work.

- [ ] **GitHub Actions CI** — run `pytest tests/ -v` on every PR
- [ ] **Streaming audio output** — chunked `audio/wav` or `audio/mp3` responses instead of waiting for full generation
- [ ] **INT8 quantization** — reduce peak VRAM from ~11 GB to ~3 GB so it runs on 8 GB cards
- [ ] **VRAM monitoring endpoint** — `GET /v1/system/vram` returning current usage and loaded models
- [ ] **MP3 / OGG output formats** — currently only WAV; adding `response_format: mp3` would be useful
- [ ] **Integration tests for voice clone** — currently skipped by default (`--run-integration`); expand coverage
- [ ] **Web UI** — minimal static HTML page to test endpoints without `curl`

## Reporting Bugs

Open an [Issue](https://github.com/feojeda/qwen-tts-server/issues) and include:

1. GPU model and VRAM
2. Python version (`python --version`)
3. PyTorch CUDA availability (`python -c "import torch; print(torch.cuda.is_available())"`)
4. Steps to reproduce
5. Expected vs actual behavior
6. Relevant logs (strip any personal info)

## Code of Conduct

Be respectful. Assume good intent. This is a side project maintained in spare time — patience is appreciated.

## Questions?

Open a [Discussion](https://github.com/feojeda/qwen-tts-server/discussions) or ping in an Issue. We reply when we can.
