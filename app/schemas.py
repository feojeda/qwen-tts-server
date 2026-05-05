"""Pydantic request / response schemas."""

from typing import Optional, List
from pydantic import BaseModel, Field


class CreateSpeechRequest(BaseModel):
    """OpenAI-compatible request body for /v1/audio/speech"""
    model: str = Field(..., description="ID of the model to use.")
    input: str = Field(..., description="The text to generate audio for.")
    voice: str = Field("Vivian", description="The voice to use. Maps to Qwen speaker names.")
    instructions: Optional[str] = Field(None, description="Optional natural-language instructions for style control.")
    response_format: str = Field("mp3", description="Audio format: mp3, opus, aac, flac, wav, pcm.")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speed multiplier. Not supported by Qwen-TTS; ignored.")
    language: Optional[str] = Field("Auto", description="Language code. Pass 'Auto' for auto-detection.")


class VoiceDesignRequest(BaseModel):
    """Request body for /v1/audio/voice-design"""
    model: str = Field(..., description="ID of the model to use.")
    input: str = Field(..., description="The text to generate audio for.")
    instructions: str = Field(..., description="Natural language description of the desired voice.")
    response_format: str = Field("mp3", description="Audio format: mp3, opus, aac, flac, wav, pcm.")
    language: Optional[str] = Field("Auto", description="Language code.")


class VoiceCloneRequest(BaseModel):
    """Request body for /v1/audio/voice-clone"""
    model: str = Field(..., description="ID of the model to use.")
    input: str = Field(..., description="The text to generate audio for.")
    voice: Optional[str] = Field(None, description="Optional voice ID. Ignored for Base model.")
    instructions: Optional[str] = Field(None, description="Optional instructions. Ignored for Base model.")
    response_format: str = Field("mp3", description="Audio format.")
    language: Optional[str] = Field("Auto", description="Language code.")
    ref_audio: str = Field(..., description="Reference audio file path, URL, or base64 string.")
    ref_text: Optional[str] = Field(None, description="Transcript of the reference audio. Required when x_vector_only_mode=False.")
    x_vector_only_mode: bool = Field(False, description="If true, only speaker timbre is cloned. The model uses its own native prosody and phonetics for the target language, which improves cross-lingual pronunciation quality.")


class CreateVoiceClonePromptRequest(BaseModel):
    ref_audio: str = Field(..., description="Reference audio file path, URL, or base64 string.")
    ref_text: Optional[str] = Field(None, description="Transcript of the reference audio. Required when x_vector_only_mode=False.")
    x_vector_only_mode: bool = Field(False, description="If true, only speaker timbre is cloned. The model uses its own native prosody and phonetics for the target language, which improves cross-lingual pronunciation quality.")


class VoiceClonePromptResponse(BaseModel):
    voice_clone_prompt_b64: str = Field(..., description="Base64-encoded serialized voice clone prompt. The client must store this and send it back for generation.")
    message: str = "Voice clone prompt created successfully. Store voice_clone_prompt_b64 and send it in future /v1/audio/voice-clone/generate requests."


class GenerateVoiceCloneFromPromptRequest(BaseModel):
    model: str = Field(..., description="ID of the model to use.")
    input: str = Field(..., description="The text to generate audio for.")
    voice_clone_prompt_b64: str = Field(..., description="Base64-encoded voice clone prompt obtained from /v1/audio/voice-clone/prompt.")
    response_format: str = Field("mp3", description="Audio format.")
    language: Optional[str] = Field("Auto", description="Language code.")


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "qwen"


class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelInfo]
