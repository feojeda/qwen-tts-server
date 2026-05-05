"""FastAPI application and HTTP endpoints."""

import io
import time
import threading
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.i18n import _t
from app.config import (
    HOST,
    PORT,
    CUSTOM_VOICE_MODEL,
    VOICE_DESIGN_MODEL,
    VOICE_CLONE_MODEL,
    LAZY_TIMEOUT,
    VRAM_GB,
)
from app.schemas import (
    CreateSpeechRequest,
    VoiceDesignRequest,
    VoiceCloneRequest,
    CreateVoiceClonePromptRequest,
    VoiceClonePromptResponse,
    GenerateVoiceCloneFromPromptRequest,
    ModelInfo,
    ModelList,
)
from app.metrics import metrics
from app import models as app_models
from app.models import (
    last_used,
    load_custom_voice,
    shutdown_models,
    _get_voice_design,
    _get_voice_clone,
    _auto_unload_worker,
    _serialize_prompt,
    _deserialize_prompt,
)


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # VRAM report
    if VRAM_GB > 0:
        print(f"[INIT] {_t('gpu_detected')}: {torch.cuda.get_device_name(0)}")
        print(f"[INIT] {_t('vram_total')}: {VRAM_GB:.1f} GB")
        if VRAM_GB < 11.0:
            print(f"[INIT] {_t('vram_insufficient')}")
            print(f"[INIT] {_t('force_17b')}")
    else:
        print(f"[INIT] {_t('no_cuda')}")
        print(f"[INIT] {_t('cpu_models')}")
        print(f"[INIT] {_t('check_cuda')}")

    print(f"[INIT] {_t('selected_models')}:")
    print(f"[INIT]   {_t('customvoice')}:  {CUSTOM_VOICE_MODEL}")
    print(f"[INIT]   {_t('voicedesign')}:  {VOICE_DESIGN_MODEL}")
    print(f"[INIT]   {_t('voiceclone')}:   {VOICE_CLONE_MODEL}")

    load_custom_voice()

    print(f"[INIT] VoiceDesign + Base/Clone {_t('lazy_loading')}.")

    watcher = threading.Thread(target=_auto_unload_worker, daemon=True)
    watcher.start()
    print(f"[INIT] {_t('auto_unload_active')}: {LAZY_TIMEOUT}s)")

    yield

    print(f"[SHUTDOWN] {_t('shutdown')}...")
    shutdown_models()


app = FastAPI(
    title="Qwen3-TTS API",
    description="Multi-model Qwen3-TTS server con lazy loading, VRAM pool y voice clone prompts stateless.",
    version="3.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _speech_tokens_from_audio(wav: np.ndarray, sr: int) -> int:
    """Approximate speech tokens from audio duration.

    Qwen3-TTS-Tokenizer-12Hz → 12.5 tokens/second
    Qwen3-TTS-Tokenizer-25Hz → 25 tokens/second
    """
    duration = len(wav) / sr
    # Default to 12.5 Hz; all currently deployed models are 12Hz variants.
    return int(duration * 12.5)


def _audio_to_bytes(wav: np.ndarray, sr: int, fmt: str) -> tuple[bytes, str]:
    fmt = fmt.lower()
    mime_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "pcm": "audio/L16",
    }
    mime = mime_map.get(fmt, "audio/wav")

    sf_format = "WAV"
    if fmt == "flac":
        sf_format = "FLAC"
    elif fmt in ("opus", "ogg"):
        sf_format = "OGG"

    buf = io.BytesIO()
    sf.write(buf, wav, sr, format=sf_format)
    buf.seek(0)
    return buf.read(), mime


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "message": "Qwen3-TTS API is running",
        "strategy": {
            "custom_voice": {"model": CUSTOM_VOICE_MODEL, "device": "cuda:0", "load": "hot (always)"},
            "voice_design": {"model": VOICE_DESIGN_MODEL, "device": "cuda:0", "load": f"lazy (auto-unload after {LAZY_TIMEOUT}s, excluyente con clone)"},
            "voice_clone":  {"model": VOICE_CLONE_MODEL,  "device": "cuda:0", "load": f"lazy (auto-unload after {LAZY_TIMEOUT}s, excluyente con design)"},
        },
        "endpoints": [
            "POST /v1/audio/speech",
            "POST /v1/audio/voice-design",
            "POST /v1/audio/voice-clone",
            "POST /v1/audio/voice-clone/prompt",
            "POST /v1/audio/voice-clone/generate",
            "GET  /v1/models",
            "GET  /v1/audio/voices",
            "GET  /v1/metrics",
            "GET  /health",
            "GET  /docs",
        ],
        "stateless_voice_clone_prompts": {
            "description": "El servidor NO guarda estado. El cliente debe almacenar voice_clone_prompt_b64.",
            "endpoints": [
                "POST /v1/audio/voice-clone/prompt    -> devuelve prompt serializado (base64)",
                "POST /v1/audio/voice-clone/generate  -> recibe prompt b64, genera audio, libera todo",
            ],
        },
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": {
            "custom_voice": app_models.custom_voice_model is not None,
            "voice_design": app_models.voice_design_model is not None,
            "voice_clone": app_models.voice_clone_model is not None,
        },
        "last_used": {
            "voice_design": last_used["voice_design"],
            "voice_clone": last_used["voice_clone"],
        },
    }


@app.get("/v1/models")
def list_models():
    return ModelList(data=[
        ModelInfo(id=CUSTOM_VOICE_MODEL),
        ModelInfo(id=VOICE_DESIGN_MODEL),
        ModelInfo(id=VOICE_CLONE_MODEL),
    ])


@app.get("/v1/audio/voices")
def list_voices():
    if app_models.custom_voice_model is None:
        raise HTTPException(503, f"CustomVoice {_t('not_loaded')}")
    try:
        speakers = app_models.custom_voice_model.get_supported_speakers()
        languages = app_models.custom_voice_model.get_supported_languages()
        return {"voices": speakers, "languages": languages}
    except Exception as e:
        raise HTTPException(500, f"{_t('error_voices')}: {e}")


@app.post("/v1/audio/speech")
def create_speech(body: CreateSpeechRequest):
    if app_models.custom_voice_model is None:
        raise HTTPException(503, f"CustomVoice {_t('not_loaded')}")
    try:
        start = time.time()
        wavs, sr = app_models.custom_voice_model.generate_custom_voice(
            text=body.input,
            language=body.language or "Auto",
            speaker=body.voice,
            instruct=body.instructions or "",
        )
        elapsed = time.time() - start
        print(f"[INFO] {_t('customvoice_gen')} {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)
        metrics.record(text_input=body.input, audio_duration_seconds=len(wav)/sr, speech_tokens=_speech_tokens_from_audio(wav, sr))

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=speech.{body.response_format}"
            },
        )
    except Exception as e:
        metrics.record(text_input=body.input, audio_duration_seconds=0.0, speech_tokens=0, error=True)
        raise HTTPException(500, f"TTS generation failed: {e}")


@app.post("/v1/audio/voice-design")
def create_voice_design(body: VoiceDesignRequest):
    try:
        mdl = _get_voice_design()
        start = time.time()
        wavs, sr = mdl.generate_voice_design(
            text=body.input,
            language=body.language or "Auto",
            instruct=body.instructions,
        )
        elapsed = time.time() - start
        print(f"[INFO] {_t('voicedesign_gen')} {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)
        metrics.record(text_input=body.input, audio_duration_seconds=len(wav)/sr, speech_tokens=_speech_tokens_from_audio(wav, sr))

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=voice_design.{body.response_format}"
            },
        )
    except Exception as e:
        metrics.record(text_input=body.input, audio_duration_seconds=0.0, speech_tokens=0, error=True)
        raise HTTPException(500, f"Voice design failed: {e}")


@app.post("/v1/audio/voice-clone")
def create_voice_clone(body: VoiceCloneRequest):
    try:
        mdl = _get_voice_clone()
        start = time.time()

        if body.x_vector_only_mode:
            # Two-step: create prompt with timbre only, then generate
            print("[INFO] x_vector_only_mode=True — using timbre-only clone")
            prompt_items = mdl.create_voice_clone_prompt(
                ref_audio=body.ref_audio,
                ref_text=body.ref_text or "",
                x_vector_only_mode=True,
            )
            wavs, sr = mdl.generate_voice_clone(
                text=body.input,
                language=body.language or "Auto",
                voice_clone_prompt=prompt_items,
            )
        else:
            # Original behavior (timbre + prosody from reference)
            wavs, sr = mdl.generate_voice_clone(
                text=body.input,
                language=body.language or "Auto",
                ref_audio=body.ref_audio,
                ref_text=body.ref_text or "",
            )

        elapsed = time.time() - start
        print(f"[INFO] {_t('voiceclone_gen')} {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)
        metrics.record(text_input=body.input, audio_duration_seconds=len(wav)/sr, speech_tokens=_speech_tokens_from_audio(wav, sr))

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=voice_clone.{body.response_format}"
            },
        )
    except Exception as e:
        import traceback
        metrics.record(text_input=body.input, audio_duration_seconds=0.0, speech_tokens=0, error=True)
        print(f"[ERROR] {_t('error_clone')}:")
        traceback.print_exc()
        raise HTTPException(500, f"Voice clone failed: {e}")


@app.post("/v1/audio/voice-clone/prompt")
def create_voice_clone_prompt(body: CreateVoiceClonePromptRequest):
    """
    Calcula un voice clone prompt y lo devuelve serializado en base64.
    El SERVIDOR NO GUARDA NADA. El cliente debe almacenar voice_clone_prompt_b64.
    """
    try:
        mdl = _get_voice_clone()
        start = time.time()
        print(f"[PROMPT] {_t('calculating_prompt')}...")
        prompt_items = mdl.create_voice_clone_prompt(
            ref_audio=body.ref_audio,
            ref_text=body.ref_text or "",
            x_vector_only_mode=body.x_vector_only_mode,
        )
        elapsed = time.time() - start
        print(f"[PROMPT] {_t('prompt_calculated')} {elapsed:.2f}s")

        b64_prompt = _serialize_prompt(prompt_items)
        return VoiceClonePromptResponse(voice_clone_prompt_b64=b64_prompt)
    except Exception as e:
        import traceback
        print(f"[ERROR] {_t('error_prompt')}:")
        traceback.print_exc()
        raise HTTPException(500, f"Failed to create voice clone prompt: {e}")


@app.post("/v1/audio/voice-clone/generate")
def generate_voice_clone_from_prompt(body: GenerateVoiceCloneFromPromptRequest):
    """
    Genera audio usando un voice clone prompt serializado (base64).
    El prompt se desserializa en memoria, se usa, y se libera inmediatamente.
    """
    try:
        print(f"[PROMPT] {_t('prompt_serialized')}...")
        prompt_items = _deserialize_prompt(body.voice_clone_prompt_b64)

        mdl = _get_voice_clone()
        start = time.time()
        wavs, sr = mdl.generate_voice_clone(
            text=body.input,
            language=body.language or "Auto",
            voice_clone_prompt=prompt_items,
        )
        elapsed = time.time() - start
        print(f"[INFO] {_t('voiceclone_from_prompt')} {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)
        metrics.record(text_input=body.input, audio_duration_seconds=len(wav)/sr, speech_tokens=_speech_tokens_from_audio(wav, sr))

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=voice_clone.{body.response_format}"
            },
        )
    except Exception as e:
        import traceback
        metrics.record(text_input=body.input, audio_duration_seconds=0.0, speech_tokens=0, error=True)
        print(f"[ERROR] {_t('error_generate')}:")
        traceback.print_exc()
        raise HTTPException(500, f"Voice clone generation from prompt failed: {e}")


@app.get("/v1/metrics")
def get_metrics():
    """Return server usage metrics (tokens processed, requests served, etc.)."""
    return metrics.snapshot()
