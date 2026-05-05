"""Pytest fixtures shared across all test files."""

import os
import sys
from unittest.mock import MagicMock
import numpy as np
import pytest

# Ensure project root is on sys.path so 'import main' works regardless of
# how pytest is invoked (directly or via python -m pytest).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Use the same HF cache directory as start.sh so integration tests
# reuse already-downloaded models instead of re-downloading.
os.environ.setdefault("HF_HOME", os.path.join(ROOT, "cache", "hf"))

# Enable hf_transfer for parallel chunked downloads (2-5x faster).
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that load real AI models (slow, requires GPU or CPU patience)",
    )


def pytest_collection_modifyitems(config, items):
    skip_integration = pytest.mark.skip(
        reason="Integration test: run with --run-integration (requires model loading)"
    )
    for item in items:
        if "integration" in item.keywords:
            if not config.getoption("--run-integration"):
                item.add_marker(skip_integration)


# ---------------------------------------------------------------------------
# Mock Qwen3TTSModel globally BEFORE importing app/* modules — but ONLY when
# integration tests are NOT requested. When --run-integration is passed we
# leave qwen_tts untouched so the real model loads.
# ---------------------------------------------------------------------------
_integration_mode = False
for arg in sys.argv:
    if arg == "--run-integration":
        _integration_mode = True
        break

if not _integration_mode:
    _mock_model_cls = MagicMock()
    _mock_instance = MagicMock()
    _mock_instance.get_supported_speakers.return_value = ["Vivian", "Alex"]
    _mock_instance.get_supported_languages.return_value = ["English", "Spanish"]
    _mock_model_cls.from_pretrained.return_value = _mock_instance
    sys.modules["qwen_tts"] = MagicMock(Qwen3TTSModel=_mock_model_cls)
else:
    # Pre-download models with robust resume before integration tests run.
    # from_pretrained()'s built-in downloader can hang on large files;
    # snapshot_download uses hf_transfer + Range-resume and is reliable.
    print("[INTEGRATION] Pre-downloading models with resume support...")
    try:
        from huggingface_hub import snapshot_download
        from app.config import CUSTOM_VOICE_MODEL, VOICE_DESIGN_MODEL, VOICE_CLONE_MODEL
        for model_id in [CUSTOM_VOICE_MODEL, VOICE_DESIGN_MODEL, VOICE_CLONE_MODEL]:
            print(f"[INTEGRATION] Ensuring cached: {model_id}")
            snapshot_download(repo_id=model_id)
        print("[INTEGRATION] All models cached.")
    except Exception as e:
        print(f"[INTEGRATION] Pre-download warning: {e}")
        print("[INTEGRATION] Continuing anyway; from_pretrained() will attempt download.")

# Now safe to import the FastAPI app
from main import app as fastapi_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client():
    """Yield a TestClient with lifespan entered (model loaded)."""
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
def mock_wav():
    """Return a fake mono WAV array and sample rate."""
    return np.zeros(16000, dtype=np.float32), 16000


@pytest.fixture
def mock_model():
    """Return the mocked Qwen3TTSModel instance for configuring return values."""
    if not _integration_mode:
        return _mock_instance
    pytest.skip("mock_model fixture is only available in unit-test mode")
