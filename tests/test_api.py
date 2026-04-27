"""
Tests for qwen-tts-server API endpoints.
Run with: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

# We need to import the FastAPI app instance.
# Since main.py runs uvicorn when __name__ == '__main__', we can import `app` directly.
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Basic endpoint tests (no model loading required)
# ---------------------------------------------------------------------------
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "models_loaded" in data


def test_list_models():
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 3
    model_ids = [m["id"] for m in data["data"]]
    assert "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice" in model_ids


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------
def test_create_speech_schema_invalid():
    """POST /v1/audio/speech with missing required fields should fail."""
    response = client.post("/v1/audio/speech", json={})
    assert response.status_code == 422


def test_voice_clone_prompt_schema_invalid():
    """POST /v1/audio/voice-clone/prompt with missing fields should fail."""
    response = client.post("/v1/audio/voice-clone/prompt", json={})
    assert response.status_code == 422


def test_generate_from_prompt_schema_invalid():
    """POST /v1/audio/voice-clone/generate with missing fields should fail."""
    response = client.post("/v1/audio/voice-clone/generate", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Content negotiation tests
# ---------------------------------------------------------------------------
def test_docs_endpoint():
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_json():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Qwen3-TTS API"


# ---------------------------------------------------------------------------
# Note on integration tests with real models:
# ---------------------------------------------------------------------------
# The following tests require GPU/CPU model loading and are skipped by default
# because they take several minutes and need ~12 GB VRAM.
#
# To run them, use: pytest tests/ -v --run-integration
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Requires model loading, run manually with --run-integration")
def test_speech_integration():
    """Integration test: generate speech with CustomVoice model."""
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


@pytest.mark.skip(reason="Requires model loading, run manually with --run-integration")
def test_voice_clone_prompt_integration():
    """Integration test: create voice clone prompt."""
    response = client.post("/v1/audio/voice-clone/prompt", json={
        "ref_audio": "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone.wav",
        "ref_text": "Okay. Yeah. I resent you. I love you. I respect you.",
        "x_vector_only_mode": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert "voice_clone_prompt_b64" in data
    assert len(data["voice_clone_prompt_b64"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
