"""
Tests for qwen-tts-server API endpoints.
Run with: pytest tests/ -v

Unit tests only — no model downloading, no GPU required.
"""

import io
import base64
import pickle
import pytest
from unittest.mock import MagicMock, patch
import numpy as np

# ---------------------------------------------------------------------------
# Mock Qwen3TTSModel BEFORE importing the app to prevent lifespan from
# downloading models during TestClient startup.
# ---------------------------------------------------------------------------
_mock_model_cls = MagicMock()
_mock_instance = MagicMock()
_mock_instance.get_supported_speakers.return_value = ["Vivian", "Alex"]
_mock_instance.get_supported_languages.return_value = ["English", "Spanish"]
_mock_model_cls.from_pretrained.return_value = _mock_instance

with patch.dict("sys.modules", {"qwen_tts": MagicMock(Qwen3TTSModel=_mock_model_cls)}):
    from main import app as fastapi_app
    import app.models



from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Yield a TestClient with lifespan entered (model loaded)."""
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
def mock_wav():
    """Return a fake mono WAV array."""
    return np.zeros(16000, dtype=np.float32), 16000


# ---------------------------------------------------------------------------
# Basic endpoints
# ---------------------------------------------------------------------------
def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data
    assert "stateless_voice_clone_prompts" in data


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "models_loaded" in data
    assert data["models_loaded"]["custom_voice"] is True


def test_list_models(client):
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 3
    model_ids = [m["id"] for m in data["data"]]
    assert "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice" in model_ids


def test_list_voices(client):
    response = client.get("/v1/audio/voices")
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert "languages" in data
    assert "Vivian" in data["voices"]


# ---------------------------------------------------------------------------
# Schema validation (Pydantic should reject missing required fields)
# ---------------------------------------------------------------------------
def test_create_speech_schema_invalid(client):
    response = client.post("/v1/audio/speech", json={})
    assert response.status_code == 422


def test_voice_design_schema_invalid(client):
    response = client.post("/v1/audio/voice-design", json={})
    assert response.status_code == 422


def test_voice_clone_schema_invalid(client):
    response = client.post("/v1/audio/voice-clone", json={})
    assert response.status_code == 422


def test_voice_clone_prompt_schema_invalid(client):
    response = client.post("/v1/audio/voice-clone/prompt", json={})
    assert response.status_code == 422


def test_generate_from_prompt_schema_invalid(client):
    response = client.post("/v1/audio/voice-clone/generate", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Docs / OpenAPI
# ---------------------------------------------------------------------------
def test_docs_endpoint(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_json(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Qwen3-TTS API"


# ---------------------------------------------------------------------------
# Speech generation (mocked)
# ---------------------------------------------------------------------------
def test_create_speech_mocked(client, mock_wav):
    wav, sr = mock_wav
    _mock_instance.generate_custom_voice.return_value = ([wav], sr)

    response = client.post("/v1/audio/speech", json={
        "model": "qwen3-tts",
        "input": "Hello world",
        "voice": "Vivian",
        "language": "English",
        "response_format": "wav",
    })
    assert response.status_code == 200
    assert len(response.content) > 0
    assert response.headers["content-type"] == "audio/wav"


# ---------------------------------------------------------------------------
# Voice design (mocked)
# ---------------------------------------------------------------------------
def test_create_voice_design_mocked(client, mock_wav):
    wav, sr = mock_wav
    _mock_instance.generate_voice_design.return_value = ([wav], sr)

    response = client.post("/v1/audio/voice-design", json={
        "model": "qwen3-tts",
        "input": "Hello world",
        "instructions": "A calm female voice",
        "language": "English",
        "response_format": "wav",
    })
    assert response.status_code == 200
    assert len(response.content) > 0


# ---------------------------------------------------------------------------
# Voice clone (mocked)
# ---------------------------------------------------------------------------
def test_create_voice_clone_mocked(client, mock_wav):
    wav, sr = mock_wav
    _mock_instance.generate_voice_clone.return_value = ([wav], sr)

    response = client.post("/v1/audio/voice-clone", json={
        "model": "qwen3-tts",
        "input": "Hello world",
        "ref_audio": "https://example.com/audio.wav",
        "ref_text": "Hello world",
        "language": "English",
        "response_format": "wav",
    })
    assert response.status_code == 200
    assert len(response.content) > 0


# ---------------------------------------------------------------------------
# Voice clone prompt (mocked)
# ---------------------------------------------------------------------------
def test_create_voice_clone_prompt_mocked(client):
    fake_prompt = {"embedding": [0.1, 0.2]}
    _mock_instance.create_voice_clone_prompt.return_value = fake_prompt

    response = client.post("/v1/audio/voice-clone/prompt", json={
        "ref_audio": "https://example.com/audio.wav",
        "ref_text": "Hello world",
        "x_vector_only_mode": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert "voice_clone_prompt_b64" in data
    assert len(data["voice_clone_prompt_b64"]) > 0
    # Verify roundtrip: the b64 should decode back to the fake prompt
    decoded = pickle.loads(base64.b64decode(data["voice_clone_prompt_b64"]))
    assert decoded == fake_prompt


# ---------------------------------------------------------------------------
# Generate from prompt (mocked)
# ---------------------------------------------------------------------------
def test_generate_voice_clone_from_prompt_mocked(client, mock_wav):
    wav, sr = mock_wav
    _mock_instance.generate_voice_clone.return_value = ([wav], sr)

    # First get a valid prompt via the prompt endpoint
    fake_prompt = {"embedding": [0.1, 0.2]}
    _mock_instance.create_voice_clone_prompt.return_value = fake_prompt
    prompt_response = client.post("/v1/audio/voice-clone/prompt", json={
        "ref_audio": "https://example.com/audio.wav",
        "ref_text": "Hello world",
    })
    b64_prompt = prompt_response.json()["voice_clone_prompt_b64"]

    response = client.post("/v1/audio/voice-clone/generate", json={
        "model": "qwen3-tts",
        "input": "Hello world",
        "voice_clone_prompt_b64": b64_prompt,
        "language": "English",
        "response_format": "wav",
    })
    assert response.status_code == 200
    assert len(response.content) > 0
