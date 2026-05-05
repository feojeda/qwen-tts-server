"""Tests for Pydantic request/response schemas (app/schemas.py)."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    CreateSpeechRequest,
    VoiceDesignRequest,
    VoiceCloneRequest,
    CreateVoiceClonePromptRequest,
    GenerateVoiceCloneFromPromptRequest,
)


class TestCreateSpeechRequest:
    def test_valid(self):
        req = CreateSpeechRequest(
            model="qwen3-tts",
            input="Hello world",
            voice="Vivian",
            language="English",
            response_format="wav",
        )
        assert req.input == "Hello world"
        assert req.voice == "Vivian"
        assert req.speed == 1.0
        assert req.response_format == "wav"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreateSpeechRequest()

    def test_speed_out_of_range(self):
        with pytest.raises(ValidationError):
            CreateSpeechRequest(
                model="qwen3-tts",
                input="Hello",
                speed=5.0,  # max is 4.0
            )


class TestVoiceDesignRequest:
    def test_valid(self):
        req = VoiceDesignRequest(
            model="qwen3-tts",
            input="Hello",
            instructions="A calm female voice",
            response_format="wav",
        )
        assert req.instructions == "A calm female voice"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            VoiceDesignRequest()


class TestVoiceCloneRequest:
    def test_valid(self):
        req = VoiceCloneRequest(
            model="qwen3-tts",
            input="Hello",
            ref_audio="https://example.com/audio.wav",
            ref_text="Hello",
            response_format="wav",
        )
        assert req.ref_audio == "https://example.com/audio.wav"
        assert req.x_vector_only_mode is False

    def test_x_vector_only_mode(self):
        req = VoiceCloneRequest(
            model="qwen3-tts",
            input="Hello",
            ref_audio="https://example.com/audio.wav",
            ref_text="Hello",
            x_vector_only_mode=True,
        )
        assert req.x_vector_only_mode is True

    def test_x_vector_only_mode_without_ref_text(self):
        req = VoiceCloneRequest(
            model="qwen3-tts",
            input="Hello",
            ref_audio="https://example.com/audio.wav",
            x_vector_only_mode=True,
        )
        assert req.x_vector_only_mode is True
        assert req.ref_text is None

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            VoiceCloneRequest()


class TestCreateVoiceClonePromptRequest:
    def test_valid(self):
        req = CreateVoiceClonePromptRequest(
            ref_audio="https://example.com/audio.wav",
            ref_text="Hello",
        )
        assert req.x_vector_only_mode is False

    def test_x_vector_only_mode_without_ref_text(self):
        req = CreateVoiceClonePromptRequest(
            ref_audio="https://example.com/audio.wav",
            x_vector_only_mode=True,
        )
        assert req.x_vector_only_mode is True
        assert req.ref_text is None

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            CreateVoiceClonePromptRequest()


class TestGenerateVoiceCloneFromPromptRequest:
    def test_valid(self):
        req = GenerateVoiceCloneFromPromptRequest(
            model="qwen3-tts",
            input="Hello",
            voice_clone_prompt_b64="Zm9v",
            response_format="wav",
        )
        assert req.voice_clone_prompt_b64 == "Zm9v"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            GenerateVoiceCloneFromPromptRequest()
