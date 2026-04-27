# Qwen TTS Server

API REST para [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) con soporte para múltiples modelos, lazy loading de VRAM y voice clone prompts stateless.

## ¿Por qué este proyecto?

Creé esto porque quería correr **Qwen3-TTS en local** en mi PC gamer con una **RTX 3060 (12 GB VRAM)**. El problema: cargar los tres modelos de 1.7B simultáneamente requiere **~16.5 GB de VRAM**, lo cual simplemente no entra. Mi solución fue un **pool de VRAM con lazy loading**: solo un modelo permanece caliente en la GPU, mientras que los otros se cargan bajo demanda y comparten el mismo espacio de VRAM. Este enfoque funciona perfectamente para cualquiera con una tarjeta de **12 GB VRAM** (RTX 3060, 4060, etc.) o incluso en **CPU con RAM equivalente** — sin necesidad de upgradear la GPU.

## Características

- **3 modelos en un solo servidor:**
  - `CustomVoice` (1.7B) - Voces predefinidas, siempre en GPU
  - `VoiceDesign` (1.7B) - Diseño de voz por descripción, lazy load
  - `Base/Clone` (1.7B) - Clonación de voz, lazy load
- **Lazy Loading + VRAM Pool:** Solo CustomVoice permanece en GPU. VoiceDesign y Base/Clone comparten VRAM y se cargan bajo demanda.
- **Voice Clone Prompts (Stateless):** El servidor no guarda estado. Los prompts se serializan en base64 y el cliente los almacena.
- **Compatible con OpenAI:** Endpoints bajo `/v1/audio/speech`, `/v1/models`, etc.
- **Auto-unload:** Los modelos lazy se descargan automáticamente tras inactividad.

## Requisitos

- Python 3.12+
- CUDA 12.6+ (para GPU)
- ~12 GB VRAM (RTX 3060 o superior recomendado)

## Instalación

```bash
git clone <repo-url>
cd qwen-tts-server
python -m venv venv

# Windows
.\venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
.\venv\Scripts\pip install -r requirements.txt

# Linux/Mac
# pip install torch torchvision torchaudio
# pip install -r requirements.txt
```

## Uso

```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh
```

O manualmente:
```bash
# Windows
.\venv\Scripts\python.exe main.py

# Linux/Mac
./venv/bin/python main.py
```

El servidor escucha en `http://0.0.0.0:8000` por defecto.

> **La primera ejecución descargará ~3.4 GB** (modelo CustomVoice) desde HuggingFace. Las siguientes arrancan instantáneamente. Los otros modelos se descargan al usarlos por primera vez.

## Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/v1/audio/speech` | `POST` | TTS con voz predefinida (OpenAI-compatible) |
| `/v1/audio/voice-design` | `POST` | Diseño de voz por descripción |
| `/v1/audio/voice-clone` | `POST` | Clonación de voz con audio de referencia |
| `/v1/audio/voice-clone/prompt` | `POST` | Calcula prompt reusable (devuelve base64) |
| `/v1/audio/voice-clone/generate` | `POST` | Genera audio desde prompt base64 |
| `/v1/models` | `GET` | Lista modelos cargados |
| `/v1/audio/voices` | `GET` | Lista voces disponibles |
| `/health` | `GET` | Health check |
| `/docs` | `GET` | Documentación interactiva (Swagger UI) |

## Cómo funciona

### Flujo TTS estándar

```
┌─────────┐   POST /v1/audio/speech           ┌─────────────────┐
│ Cliente │ ────────────────────────────────> │  Qwen TTS Server│
│         │  { input, voice, language }       │  (CustomVoice)  │
│         │                                   │     [GPU HOT]   │
│         │ <──────────────────────────────── │                 │
│         │   audio/wav  (~5 seg)             │                 │
└─────────┘                                   └─────────────────┘
```

### Flujo de Voice Clone (Stateless)

El servidor **no guarda estado**. Los perfiles de voz viven en el cliente.

```
Paso 1: Crear perfil de voz (una vez)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────┐   POST /v1/audio/voice-clone/prompt   ┌─────────────────┐
│ Cliente │ ────────────────────────────────────> │  Qwen TTS Server│
│         │  { ref_audio, ref_text }              │  (Base/Clone)   │
│         │                                       │   [GPU LAZY]    │
│         │ <──────────────────────────────────── │                 │
│         │   { voice_clone_prompt_b64 }          │                 │
└─────────┘                                       └─────────────────┘
     │
     ▼
┌─────────────────────────────┐
│  Cliente guarda blob base64 │
│  (SQLite / Redis / etc.)    │
└─────────────────────────────┘

Paso 2: Generar voz clonada (cuando quieras, las veces que quieras)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────┐   POST /v1/audio/voice-clone/generate   ┌─────────────────┐
│ Cliente │ ──────────────────────────────────────> │  Qwen TTS Server│
│         │  { input, voice_clone_prompt_b64 }      │  (Base/Clone)   │
│         │                                       │   [GPU LAZY]    │
│         │ <──────────────────────────────────── │                 │
│         │   audio/wav                           │                 │
└─────────┘                                       └─────────────────┘
```

## Ejemplos

### TTS con voz predefinida

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hola mundo",
    "voice": "Vivian",
    "language": "Spanish",
    "response_format": "wav"
  }' \
  --output speech.wav
```

### Voice Clone (stateless)

**1. Crear prompt:**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "ref_audio": "https://ejemplo.com/mi_voz.wav",
    "ref_text": "Texto exacto de referencia"
  }'
```

Guarda `voice_clone_prompt_b64` de la respuesta.

**2. Generar audio:**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hola, esta es mi voz clonada",
    "voice_clone_prompt_b64": "<el-base64-guardado>",
    "response_format": "wav"
  }' \
  --output clone.wav
```

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `QWEN_TTS_HOST` | `0.0.0.0` | Host de escucha |
| `QWEN_TTS_PORT` | `8000` | Puerto |
| `QWEN_CUSTOM_VOICE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Modelo CustomVoice |
| `QWEN_VOICE_DESIGN_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | Modelo VoiceDesign |
| `QWEN_VOICE_CLONE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Modelo Base/Clone |
| `QWEN_LAZY_TIMEOUT_SECONDS` | `300` | Segundos para auto-unload |

## Arquitectura de VRAM

```
CustomVoice (1.7B)  -> GPU HOT   (~5.5 GB, siempre)
VoiceDesign (1.7B)  -> GPU LAZY  (~5.5 GB, excluyente)
Base/Clone  (1.7B)  -> GPU LAZY  (~5.5 GB, excluyente)
```

VoiceDesign y Base/Clone **nunca están cargados simultáneamente**.

## Licencia

Apache 2.0 (mismo que Qwen3-TTS)
