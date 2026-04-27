"""
Qwen3-TTS API Server - STATELESS

Estrategia de memoria (RTX 3060 12GB):
  - CustomVoice (1.7B)  -> SIEMPRE cargado en GPU (hot)
  - VoiceDesign (1.7B)  -> LAZY en GPU, excluyente con Base
  - Base/Clone  (1.7B)  -> LAZY en GPU, excluyente con VoiceDesign

Voice Clone Prompts (STATELESS):
  - El servidor NUNCA guarda estado entre requests
  - POST /v1/audio/voice-clone/prompt    -> calcula y devuelve el prompt serializado (base64)
  - POST /v1/audio/voice-clone/generate  -> recibe el prompt serializado, genera audio, libera todo
  - El CLIENTE es responsable de guardar y reenviar el prompt

Variables de entorno:
  QWEN_TTS_HOST              -- host (default: 0.0.0.0)
  QWEN_TTS_PORT              -- port (default: 8000)
  QWEN_CUSTOM_VOICE_MODEL    -- modelo custom voice (default: 1.7B)
  QWEN_VOICE_DESIGN_MODEL    -- modelo voice design (default: 1.7B)
  QWEN_VOICE_CLONE_MODEL     -- modelo base/clone (default: 1.7B)
  QWEN_LAZY_TIMEOUT_SECONDS  -- segundos para auto-unload (default: 300 = 5 min)
"""

import io
import os
import time
import base64
import threading
from typing import Optional, List, Any
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from qwen_tts import Qwen3TTSModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = os.getenv("QWEN_TTS_HOST", "0.0.0.0")
PORT = int(os.getenv("QWEN_TTS_PORT", "8000"))

CUSTOM_VOICE_MODEL = os.getenv("QWEN_CUSTOM_VOICE_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
VOICE_DESIGN_MODEL = os.getenv("QWEN_VOICE_DESIGN_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")
VOICE_CLONE_MODEL  = os.getenv("QWEN_VOICE_CLONE_MODEL",  "Qwen/Qwen3-TTS-12Hz-1.7B-Base")

LAZY_TIMEOUT = int(os.getenv("QWEN_LAZY_TIMEOUT_SECONDS", "300"))  # 5 minutos

DEVICE_GPU = "cuda:0"

# ---------------------------------------------------------------------------
# Model state (solo modelos, nada de prompts)
# ---------------------------------------------------------------------------
custom_voice_model: Optional[Qwen3TTSModel] = None
voice_design_model: Optional[Qwen3TTSModel] = None
voice_clone_model: Optional[Qwen3TTSModel] = None

last_used = {
    "voice_design": 0.0,
    "voice_clone": 0.0,
}

model_lock = threading.Lock()
shutdown_flag = threading.Event()


# ---------------------------------------------------------------------------
# Prompt serialization helpers (stateless)
# ---------------------------------------------------------------------------
def _serialize_prompt(items: Any) -> str:
    """Serializa un voice_clone_prompt a string base64."""
    buf = io.BytesIO()
    torch.save(items, buf)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _deserialize_prompt(b64_string: str) -> Any:
    """Desserializa un voice_clone_prompt desde string base64."""
    raw = base64.b64decode(b64_string.encode("utf-8"))
    buf = io.BytesIO(raw)
    return torch.load(buf, weights_only=False)


# ---------------------------------------------------------------------------
# Model lifecycle helpers (INTERNAL - must be called with model_lock held)
# ---------------------------------------------------------------------------
def _do_unload_voice_design():
    global voice_design_model
    if voice_design_model is not None:
        print("[LAZY] Descargando VoiceDesign para liberar VRAM...")
        del voice_design_model
        voice_design_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[LAZY] VoiceDesign descargado.")


def _do_unload_voice_clone():
    global voice_clone_model
    if voice_clone_model is not None:
        print("[LAZY] Descargando Base/Clone para liberar VRAM...")
        del voice_clone_model
        voice_clone_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[LAZY] Base/Clone descargado.")


def _do_load_voice_design() -> Qwen3TTSModel:
    global voice_design_model
    if voice_clone_model is not None:
        _do_unload_voice_clone()
    print(f"[LAZY] Cargando VoiceDesign: {VOICE_DESIGN_MODEL} en {DEVICE_GPU} ...")
    voice_design_model = Qwen3TTSModel.from_pretrained(
        VOICE_DESIGN_MODEL,
        device_map=DEVICE_GPU,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    last_used["voice_design"] = time.time()
    print("[LAZY] VoiceDesign cargado.")
    return voice_design_model


def _do_load_voice_clone() -> Qwen3TTSModel:
    global voice_clone_model
    if voice_design_model is not None:
        _do_unload_voice_design()
    print(f"[LAZY] Cargando Base/Clone: {VOICE_CLONE_MODEL} en {DEVICE_GPU} ...")
    voice_clone_model = Qwen3TTSModel.from_pretrained(
        VOICE_CLONE_MODEL,
        device_map=DEVICE_GPU,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    last_used["voice_clone"] = time.time()
    print("[LAZY] Base/Clone cargado.")
    return voice_clone_model


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def _get_voice_design() -> Qwen3TTSModel:
    global voice_design_model
    with model_lock:
        if voice_design_model is None:
            return _do_load_voice_design()
        else:
            last_used["voice_design"] = time.time()
            return voice_design_model


def _get_voice_clone() -> Qwen3TTSModel:
    global voice_clone_model
    with model_lock:
        if voice_clone_model is None:
            return _do_load_voice_clone()
        else:
            last_used["voice_clone"] = time.time()
            return voice_clone_model


def _auto_unload_worker():
    while not shutdown_flag.is_set():
        shutdown_flag.wait(60)
        if shutdown_flag.is_set():
            break
        now = time.time()
        with model_lock:
            if voice_design_model is not None:
                idle = now - last_used["voice_design"]
                if idle > LAZY_TIMEOUT:
                    print(f"[AUTO] VoiceDesign inactivo por {idle:.0f}s. Liberando...")
                    _do_unload_voice_design()
            if voice_clone_model is not None:
                idle = now - last_used["voice_clone"]
                if idle > LAZY_TIMEOUT:
                    print(f"[AUTO] Base/Clone inactivo por {idle:.0f}s. Liberando...")
                    _do_unload_voice_clone()


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global custom_voice_model

    print(f"[INIT] Cargando CustomVoice (hot): {CUSTOM_VOICE_MODEL} en {DEVICE_GPU}")
    custom_voice_model = Qwen3TTSModel.from_pretrained(
        CUSTOM_VOICE_MODEL,
        device_map=DEVICE_GPU,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    print("[INIT] CustomVoice listo.")

    print("[INIT] VoiceDesign y Base/Clone configurados para lazy loading.")

    watcher = threading.Thread(target=_auto_unload_worker, daemon=True)
    watcher.start()
    print(f"[INIT] Auto-unload watcher activo (timeout: {LAZY_TIMEOUT}s)")

    yield

    print("[SHUTDOWN] Deteniendo servidor...")
    shutdown_flag.set()
    with model_lock:
        _do_unload_voice_design()
        _do_unload_voice_clone()


app = FastAPI(
    title="Qwen3-TTS API",
    description="Multi-model Qwen3-TTS server con lazy loading, VRAM pool y voice clone prompts stateless.",
    version="3.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
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
    ref_text: Optional[str] = Field(None, description="Transcript of the reference audio.")


# -- Voice Clone Prompt schemas (stateless) --
class CreateVoiceClonePromptRequest(BaseModel):
    ref_audio: str = Field(..., description="Reference audio file path, URL, or base64 string.")
    ref_text: str = Field(..., description="Transcript of the reference audio.")
    x_vector_only_mode: bool = Field(False, description="If true, only speaker embedding is used (faster, lower quality).")


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
            "custom_voice": {"model": CUSTOM_VOICE_MODEL, "device": DEVICE_GPU, "load": "hot (always)"},
            "voice_design": {"model": VOICE_DESIGN_MODEL, "device": DEVICE_GPU, "load": f"lazy (auto-unload after {LAZY_TIMEOUT}s, excluyente con clone)"},
            "voice_clone":  {"model": VOICE_CLONE_MODEL,  "device": DEVICE_GPU, "load": f"lazy (auto-unload after {LAZY_TIMEOUT}s, excluyente con design)"},
        },
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
            "custom_voice": custom_voice_model is not None,
            "voice_design": voice_design_model is not None,
            "voice_clone": voice_clone_model is not None,
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
    if custom_voice_model is None:
        raise HTTPException(503, "CustomVoice model not loaded yet.")
    try:
        speakers = custom_voice_model.get_supported_speakers()
        languages = custom_voice_model.get_supported_languages()
        return {"voices": speakers, "languages": languages}
    except Exception as e:
        raise HTTPException(500, f"Error listing voices: {e}")


# ---------------------------------------------------------------------------
# Speech / Voice-Design / Voice-Clone (standard)
# ---------------------------------------------------------------------------
@app.post("/v1/audio/speech")
def create_speech(body: CreateSpeechRequest):
    if custom_voice_model is None:
        raise HTTPException(503, "CustomVoice model not loaded yet.")
    try:
        start = time.time()
        wavs, sr = custom_voice_model.generate_custom_voice(
            text=body.input,
            language=body.language or "Auto",
            speaker=body.voice,
            instruct=body.instructions or "",
        )
        elapsed = time.time() - start
        print(f"[INFO] CustomVoice generated in {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=speech.{body.response_format}"
            },
        )
    except Exception as e:
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
        print(f"[INFO] VoiceDesign generated in {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=voice_design.{body.response_format}"
            },
        )
    except Exception as e:
        raise HTTPException(500, f"Voice design failed: {e}")


@app.post("/v1/audio/voice-clone")
def create_voice_clone(body: VoiceCloneRequest):
    try:
        mdl = _get_voice_clone()
        start = time.time()
        wavs, sr = mdl.generate_voice_clone(
            text=body.input,
            language=body.language or "Auto",
            ref_audio=body.ref_audio,
            ref_text=body.ref_text or "",
        )
        elapsed = time.time() - start
        print(f"[INFO] VoiceClone generated in {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=voice_clone.{body.response_format}"
            },
        )
    except Exception as e:
        import traceback
        print("[ERROR] Voice clone traceback:")
        traceback.print_exc()
        raise HTTPException(500, f"Voice clone failed: {e}")


# ---------------------------------------------------------------------------
# Voice Clone Prompts (STATELESS)
# ---------------------------------------------------------------------------
@app.post("/v1/audio/voice-clone/prompt")
def create_voice_clone_prompt(body: CreateVoiceClonePromptRequest):
    """
    Calcula un voice clone prompt y lo devuelve serializado en base64.
    El SERVIDOR NO GUARDA NADA. El cliente debe almacenar voice_clone_prompt_b64.
    """
    try:
        mdl = _get_voice_clone()
        start = time.time()
        print("[PROMPT] Calculando voice clone prompt...")
        prompt_items = mdl.create_voice_clone_prompt(
            ref_audio=body.ref_audio,
            ref_text=body.ref_text,
            x_vector_only_mode=body.x_vector_only_mode,
        )
        elapsed = time.time() - start
        print(f"[PROMPT] Prompt calculado en {elapsed:.2f}s")

        b64_prompt = _serialize_prompt(prompt_items)
        return VoiceClonePromptResponse(voice_clone_prompt_b64=b64_prompt)
    except Exception as e:
        import traceback
        print("[ERROR] Create voice clone prompt traceback:")
        traceback.print_exc()
        raise HTTPException(500, f"Failed to create voice clone prompt: {e}")


@app.post("/v1/audio/voice-clone/generate")
def generate_voice_clone_from_prompt(body: GenerateVoiceCloneFromPromptRequest):
    """
    Genera audio usando un voice clone prompt serializado (base64).
    El prompt se desserializa en memoria, se usa, y se libera inmediatamente.
    """
    try:
        print("[PROMPT] Desserializando voice clone prompt...")
        prompt_items = _deserialize_prompt(body.voice_clone_prompt_b64)

        mdl = _get_voice_clone()
        start = time.time()
        wavs, sr = mdl.generate_voice_clone(
            text=body.input,
            language=body.language or "Auto",
            voice_clone_prompt=prompt_items,
        )
        elapsed = time.time() - start
        print(f"[INFO] VoiceClone (from prompt) generated in {elapsed:.2f}s")

        wav = wavs[0]
        audio_bytes, mime_type = _audio_to_bytes(wav, sr, body.response_format)

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=voice_clone.{body.response_format}"
            },
        )
    except Exception as e:
        import traceback
        print("[ERROR] Generate from prompt traceback:")
        traceback.print_exc()
        raise HTTPException(500, f"Voice clone generation from prompt failed: {e}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
