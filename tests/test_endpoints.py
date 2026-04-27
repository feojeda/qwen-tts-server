"""Tests for HTTP endpoints (app/main.py routes)."""

import base64
import pickle


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


class TestModels:
    def test_list_models(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 3
        model_ids = [m["id"] for m in data["data"]]
        assert "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice" in model_ids


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
