# Qwen TTS Server

<div align="center">

[English](README.md) | **Español** | [简体中文](README.zh.md) | [日本語](README.ja.md)

</div>

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

- Python 3.10+
- **SoX** — requerido por librosa para procesamiento de audio (se instala automáticamente con `setup.sh`/`setup.bat`)
- ~12 GB VRAM (RTX 3060 o superior recomendado)

## Instalación

```bash
git clone <repo-url>
cd qwen-tts-server

# Windows
setup.bat

# Linux/Mac
bash setup.sh
```

El script de setup automáticamente:
- Verifica Python 3.10+ (muestra instrucciones de instalación si no lo encuentra)
- Instala `python3-venv` si es necesario (Debian/Ubuntu)
- Crea un entorno virtual
- Instala todas las dependencias de `requirements.txt`

## Uso

```bash
# Windows
start.bat

# Linux/Mac
bash start.sh
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

## Contribuir

¡Los PRs son bienvenidos! Las guidelines están en inglés: [CONTRIBUTING.md](CONTRIBUTING.md).

## Opcional: Flash Attention

[Flash Attention](https://github.com/Dao-AILab/flash-attention) puede mejorar la velocidad de inferencia y reducir el uso de VRAM en secuencias largas. **No es obligatorio** — el servidor funciona bien sin él usando SDPA integrado de PyTorch.

> **Solo Linux.** Flash Attention requiere compilar kernels CUDA y no está disponible en Windows ni macOS. También requiere una GPU NVIDIA con compute capability ≥ 8.0 (Ampere o superior: RTX 3000/4000, A100, etc.).

### Instalación rápida (wheel precompilado)

Hay un wheel precompilado disponible para **Linux x86_64 + Python 3.12 + CUDA 13 + GPUs Ampere** (RTX 3060/3070/3080/3090/A100):

```bash
# Descargar e instalar el wheel precompilado
wget https://github.com/feojeda/qwen-tts-server/releases/download/flash-attn-v2.8.3/flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
./venv/bin/pip install flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
rm flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
```

> Este wheel solo funciona en el entorno exacto para el que fue compilado (Linux x86_64, Python 3.12, CUDA 13.x, compute capability 8.x). Si no coincide con tu configuración, compilá desde el código fuente.

### Compilar desde el código (Linux, con < 32 GB RAM)

La compilación usa mucha RAM (~4-8 GB por job paralelo). Si tu sistema tiene RAM limitada, restringí la cantidad de jobs y compilá solo para la arquitectura de tu GPU:

```bash
# Primero instalá ninja (builds más rápidos) y nvcc
./venv/bin/pip install ninja nvidia-cuda-nvcc

# Compilar solo para tu GPU, limitar jobs para evitar OOM
FLASH_ATTN_CUDA_ARCHS="86" MAX_JOBS=3 ./venv/bin/pip install flash-attn --no-build-isolation
```

**`FLASH_ATTN_CUDA_ARCHS`** le dice al compilador que genere kernels solo para la compute capability de tu GPU. Ajustalo según tu hardware:

| Serie GPU | Compute Capability | `FLASH_ATTN_CUDA_ARCHS` |
|---|---|---|
| RTX 3060, 3070, 3080, 3090 | 8.6 | `"86"` |
| RTX 4060, 4070, 4080, 4090 | 8.9 | `"89"` |
| A100, A10G | 8.0 | `"80"` |
| H100 | 9.0 | `"90"` |

**`MAX_JOBS`** limita los jobs de compilación paralelos para evitar quedarse sin RAM:

| RAM del sistema | `MAX_JOBS` recomendado |
|---|---|
| 16 GB | `2`–`3` |
| 32 GB | `4`–`6` |
| 64 GB+ | Omitir (usa todos los cores) |

> **Importante:** Detené el servidor TTS antes de compilar. Ejecutar ambos simultáneamente puede causar un OOM kill.

### Instalar (Linux, con 32+ GB RAM)

```bash
./venv/bin/pip install ninja nvidia-cuda-nvcc
./venv/bin/pip install flash-attn --no-build-isolation
```

## Testing

```bash
# Unit tests (rápidos, no cargan modelos)
pytest tests/ -v

# Integration tests (lentos, requieren modelos reales)
pytest tests/test_integration.py -v --run-integration
```

| Suite de tests | Archivos | Carga de modelos | Velocidad | Corre en CI |
|-----------|-------|---------------|-------|-----------|
| **Unit** | `test_*.py` excepto `test_integration.py` | Mockeados (sin descargas) | ~0.5s | ✅ Sí |
| **Integration** | Solo `test_integration.py` | Modelos reales de HuggingFace | ~5-15 min | ❌ No |

Los integration tests están marcados con `@pytest.mark.integration` y se **saltan por defecto**. Cargan modelos Qwen3-TTS reales, descargan pesos en la primera ejecución y generan audio real. Correlos solo localmente cuando quieras verificar el comportamiento end-to-end con hardware real.

## Ubicación del Cache de Modelos

Por defecto, HuggingFace descarga modelos al directorio home del usuario (`~/.cache/huggingface/hub/` en Linux/Mac, `%USERPROFILE%\.cache\huggingface\hub\` en Windows). Este proyecto sobrescribe el cache a la carpeta del proyecto para que los modelos queden en el mismo disco que el código.

| Variable | Default (sobrescrito) | Ubicación del proyecto |
|----------|---------------------|------------------|
| `HF_HOME` | `~/.cache/huggingface` | `./cache/hf/` |

**`start.bat`** y **`start.sh`** configuran esto automáticamente. Si corres `main.py` manualmente, configurá la variable vos:

```powershell
# Windows
$env:HF_HOME="E:\qwentts\cache\hf"
.\venv\Scripts\python.exe main.py
```

```bash
# Linux/Mac
export HF_HOME="/path/to/qwen-tts-server/cache/hf"
./venv/bin/python main.py
```

La carpeta `cache/` ya está en `.gitignore`.

## Licencia

Apache 2.0 (mismo que Qwen3-TTS)
