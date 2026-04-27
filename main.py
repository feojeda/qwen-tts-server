"""
Qwen3-TTS API Server - STATELESS

Thin entrypoint. All logic lives in the app/ package.

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

from app.main import app  # noqa: F401
from app.config import HOST, PORT

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
