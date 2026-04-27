"""Pytest fixtures shared across all test files."""

import sys
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Mock Qwen3TTSModel globally before any test imports app/* modules.
# This prevents HuggingFace downloads during test collection & execution.
# ---------------------------------------------------------------------------
_mock_model_cls = MagicMock()
_mock_instance = MagicMock()
_mock_instance.get_supported_speakers.return_value = ["Vivian", "Alex"]
_mock_instance.get_supported_languages.return_value = ["English", "Spanish"]
_mock_model_cls.from_pretrained.return_value = _mock_instance

sys.modules["qwen_tts"] = MagicMock(Qwen3TTSModel=_mock_model_cls)

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
    return _mock_instance
