"""Integration tests — load real Qwen3-TTS models and generate actual audio.

These tests are SKIPPED by default. To run them locally:

    python -m pytest tests/test_integration.py -v --run-integration

Requirements:
  - ~12 GB VRAM for 1.7B models (or ~6 GB for 0.6B models on CPU)
  - First run downloads ~3.4 GB from HuggingFace (cached afterwards)
  - Patience: first run can take 10-20 min depending on connection speed
"""

import pytest

# A short reference audio + transcript provided by the Qwen3-TTS project.
REF_AUDIO_URL = (
    "https://qianwen-res.oss-cn-beijing.aliyuncs.com/"
    "Qwen3-TTS-Repo/clone.wav"
)
REF_TEXT = "Okay. Yeah. I resent you. I love you. I respect you."


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------
@pytest.mark.integration
class TestCustomVoiceIntegration:
    def test_generate_speech(self, client):
        """Generate real audio with CustomVoice."""
        response = client.post("/v1/audio/speech", json={
            "model": "qwen3-tts",
            "input": "Hello, this is a real integration test.",
            "voice": "Vivian",
            "language": "English",
            "response_format": "wav",
        })
        assert response.status_code == 200
        assert len(response.content) > 0
        assert response.headers["content-type"] == "audio/wav"

    def test_list_real_voices(self, client):
        """List voices from the actually loaded model."""
        response = client.get("/v1/audio/voices")
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert "languages" in data
        assert len(data["voices"]) > 0


@pytest.mark.integration
class TestVoiceCloneIntegration:
    def test_create_and_generate_prompt(self, client):
        """Create a voice clone prompt from reference audio, then generate speech."""
        # 1. Create prompt
        prompt_resp = client.post("/v1/audio/voice-clone/prompt", json={
            "ref_audio": REF_AUDIO_URL,
            "ref_text": REF_TEXT,
            "x_vector_only_mode": False,
        })
        assert prompt_resp.status_code == 200
        data = prompt_resp.json()
        assert "voice_clone_prompt_b64" in data
        assert len(data["voice_clone_prompt_b64"]) > 100
        b64_prompt = data["voice_clone_prompt_b64"]

        # 2. Generate from prompt
        gen_resp = client.post("/v1/audio/voice-clone/generate", json={
            "model": "qwen3-tts",
            "input": "This is my cloned voice speaking.",
            "voice_clone_prompt_b64": b64_prompt,
            "language": "English",
            "response_format": "wav",
        })
        assert gen_resp.status_code == 200
        assert len(gen_resp.content) > 0

    def test_generate_direct(self, client):
        """Direct voice clone without pre-computing a prompt."""
        resp = client.post("/v1/audio/voice-clone", json={
            "model": "qwen3-tts",
            "input": "Direct voice clone test.",
            "ref_audio": REF_AUDIO_URL,
            "ref_text": REF_TEXT,
            "language": "English",
            "response_format": "wav",
        })
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_generate_direct_x_vector_only(self, client):
        """Direct voice clone with x_vector_only_mode (timbre-only, no ref_text)."""
        resp = client.post("/v1/audio/voice-clone", json={
            "model": "qwen3-tts",
            "input": "Direct voice clone with timbre only.",
            "ref_audio": REF_AUDIO_URL,
            "language": "English",
            "response_format": "wav",
            "x_vector_only_mode": True,
        })
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_create_and_generate_prompt_x_vector_only(self, client):
        """Create timbre-only prompt without ref_text, then generate speech."""
        # 1. Create prompt without ref_text
        prompt_resp = client.post("/v1/audio/voice-clone/prompt", json={
            "ref_audio": REF_AUDIO_URL,
            "x_vector_only_mode": True,
        })
        assert prompt_resp.status_code == 200
        data = prompt_resp.json()
        assert "voice_clone_prompt_b64" in data
        assert len(data["voice_clone_prompt_b64"]) > 100
        b64_prompt = data["voice_clone_prompt_b64"]

        # 2. Generate from prompt
        gen_resp = client.post("/v1/audio/voice-clone/generate", json={
            "model": "qwen3-tts",
            "input": "This is my cloned voice speaking in timbre-only mode.",
            "voice_clone_prompt_b64": b64_prompt,
            "language": "English",
            "response_format": "wav",
        })
        assert gen_resp.status_code == 200
        assert len(gen_resp.content) > 0


@pytest.mark.integration
class TestVoiceDesignIntegration:
    def test_generate_voice_design(self, client):
        """Generate audio with VoiceDesign (lazy model load)."""
        resp = client.post("/v1/audio/voice-design", json={
            "model": "qwen3-tts",
            "input": "Voice design integration test.",
            "instructions": "A calm, friendly female voice",
            "language": "English",
            "response_format": "wav",
        })
        assert resp.status_code == 200
        assert len(resp.content) > 0


@pytest.mark.integration
class TestHealthIntegration:
    def test_health_shows_loaded_models(self, client):
        """Health endpoint reflects actually loaded models."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["models_loaded"]["custom_voice"] is True
