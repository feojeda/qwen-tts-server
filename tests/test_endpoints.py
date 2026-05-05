"""Tests for HTTP endpoints (app/main.py routes)."""

import base64
import pickle
import pytest


class TestRoot:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "endpoints" in data
        assert "stateless_voice_clone_prompts" in data


class TestHealth:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "models_loaded" in data
        assert data["models_loaded"]["custom_voice"] is True


class TestMetrics:
    def test_metrics(self, client):
        response = client.get("/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "requests_total" in data
        assert "text_chars_total" in data
        assert "speech_tokens_total" in data
        assert "audio_seconds_total" in data
        assert "uptime_seconds" in data
        assert "models" in data


class TestModels:
    def test_list_models(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 3
        model_ids = [m["id"] for m in data["data"]]
        assert any("CustomVoice" in m for m in model_ids)
        assert any("VoiceDesign" in m for m in model_ids)
        assert any("Base" in m for m in model_ids)


class TestVoices:
    def test_list_voices(self, client):
        response = client.get("/v1/audio/voices")
        assert response.status_code == 200
        data = response.json()
        assert "voices" in data
        assert "languages" in data
        assert "Vivian" in data["voices"]


class TestDocs:
    def test_docs_endpoint(self, client):
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_json(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Qwen3-TTS API"


class TestSpeech:
    def test_create_speech_schema_invalid(self, client):
        response = client.post("/v1/audio/speech", json={})
        assert response.status_code == 422

    def test_create_speech_mocked(self, client, mock_wav, mock_model):
        wav, sr = mock_wav
        mock_model.generate_custom_voice.return_value = ([wav], sr)

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


class TestVoiceDesign:
    def test_schema_invalid(self, client):
        response = client.post("/v1/audio/voice-design", json={})
        assert response.status_code == 422

    def test_create_mocked(self, client, mock_wav, mock_model):
        wav, sr = mock_wav
        mock_model.generate_voice_design.return_value = ([wav], sr)

        response = client.post("/v1/audio/voice-design", json={
            "model": "qwen3-tts",
            "input": "Hello world",
            "instructions": "A calm female voice",
            "language": "English",
            "response_format": "wav",
        })
        assert response.status_code == 200
        assert len(response.content) > 0


class TestVoiceClone:
    @pytest.fixture(autouse=True)
    def _reset_mock(self, mock_model):
        mock_model.reset_mock()

    def test_schema_invalid(self, client):
        response = client.post("/v1/audio/voice-clone", json={})
        assert response.status_code == 422

    def test_create_mocked(self, client, mock_wav, mock_model):
        wav, sr = mock_wav
        mock_model.generate_voice_clone.return_value = ([wav], sr)

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
        # Verify default path (x_vector_only_mode=False) uses direct ref_audio/ref_text
        mock_model.generate_voice_clone.assert_called_once()
        call_kwargs = mock_model.generate_voice_clone.call_args.kwargs
        assert "ref_audio" in call_kwargs
        assert "voice_clone_prompt" not in call_kwargs

    def test_create_x_vector_only_mode(self, client, mock_wav, mock_model):
        wav, sr = mock_wav
        mock_model.generate_voice_clone.return_value = ([wav], sr)
        fake_prompt = [{"ref_spk_embedding": [0.1]}]
        mock_model.create_voice_clone_prompt.return_value = fake_prompt

        response = client.post("/v1/audio/voice-clone", json={
            "model": "qwen3-tts",
            "input": "Hello world",
            "ref_audio": "https://example.com/audio.wav",
            "ref_text": "Hello world",
            "language": "English",
            "response_format": "wav",
            "x_vector_only_mode": True,
        })
        assert response.status_code == 200
        assert len(response.content) > 0
        # Verify two-step path was used
        mock_model.create_voice_clone_prompt.assert_called_once_with(
            ref_audio="https://example.com/audio.wav",
            ref_text="Hello world",
            x_vector_only_mode=True,
        )
        # Check the last call to generate_voice_clone used voice_clone_prompt
        last_call = mock_model.generate_voice_clone.call_args
        assert "voice_clone_prompt" in last_call.kwargs
        assert last_call.kwargs["voice_clone_prompt"] == fake_prompt

    def test_create_x_vector_only_mode_without_ref_text(self, client, mock_wav, mock_model):
        """x_vector_only_mode=True should work without ref_text (timbre-only)."""
        wav, sr = mock_wav
        mock_model.generate_voice_clone.return_value = ([wav], sr)
        fake_prompt = [{"ref_spk_embedding": [0.1]}]
        mock_model.create_voice_clone_prompt.return_value = fake_prompt

        response = client.post("/v1/audio/voice-clone", json={
            "model": "qwen3-tts",
            "input": "Hello world",
            "ref_audio": "https://example.com/audio.wav",
            "language": "English",
            "response_format": "wav",
            "x_vector_only_mode": True,
        })
        assert response.status_code == 200
        assert len(response.content) > 0
        # Verify create_voice_clone_prompt was called with empty ref_text
        mock_model.create_voice_clone_prompt.assert_called_once_with(
            ref_audio="https://example.com/audio.wav",
            ref_text="",
            x_vector_only_mode=True,
        )


class TestVoiceClonePrompt:
    def test_schema_invalid(self, client):
        response = client.post("/v1/audio/voice-clone/prompt", json={})
        assert response.status_code == 422

    def test_create_mocked(self, client, mock_model):
        fake_prompt = {"embedding": [0.1, 0.2]}
        mock_model.create_voice_clone_prompt.return_value = fake_prompt

        response = client.post("/v1/audio/voice-clone/prompt", json={
            "ref_audio": "https://example.com/audio.wav",
            "ref_text": "Hello world",
            "x_vector_only_mode": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert "voice_clone_prompt_b64" in data
        # Verify roundtrip
        decoded = pickle.loads(base64.b64decode(data["voice_clone_prompt_b64"]))
        assert decoded == fake_prompt

    def test_create_x_vector_without_ref_text(self, client, mock_model):
        """Prompt endpoint should accept x_vector_only_mode without ref_text."""
        fake_prompt = {"embedding": [0.1, 0.2]}
        mock_model.create_voice_clone_prompt.return_value = fake_prompt

        response = client.post("/v1/audio/voice-clone/prompt", json={
            "ref_audio": "https://example.com/audio.wav",
            "x_vector_only_mode": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert "voice_clone_prompt_b64" in data
        # Verify the last call used empty ref_text
        last_call = mock_model.create_voice_clone_prompt.call_args
        assert last_call.kwargs["ref_audio"] == "https://example.com/audio.wav"
        assert last_call.kwargs["ref_text"] == ""
        assert last_call.kwargs["x_vector_only_mode"] is True


class TestGenerateFromPrompt:
    def test_schema_invalid(self, client):
        response = client.post("/v1/audio/voice-clone/generate", json={})
        assert response.status_code == 422

    def test_generate_mocked(self, client, mock_wav, mock_model):
        wav, sr = mock_wav
        mock_model.generate_voice_clone.return_value = ([wav], sr)

        fake_prompt = {"embedding": [0.1, 0.2]}
        mock_model.create_voice_clone_prompt.return_value = fake_prompt
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
