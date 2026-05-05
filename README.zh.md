# Qwen TTS Server

<div align="center">

[English](README.md) | [Español](README.es.md) | **简体中文** | [日本語](README.ja.md)

</div>

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) 的 REST API，支持多模型、VRAM 懒加载和无状态语音克隆提示。

## 为什么会有这个项目？

我开发这个项目是因为我想在我的游戏 PC 上**本地运行 Qwen3-TTS**，配置是 **RTX 3060（12 GB VRAM）**。问题在于：同时加载三个 1.7B 模型需要 **~16.5 GB VRAM**，根本放不下。我的解决方案是 **VRAM 池 + 懒加载**：只有一个模型常驻 GPU，其他模型按需加载并共享同一个 VRAM 空间。这种方式非常适合拥有 **12 GB VRAM 显卡**（RTX 3060、4060 等）的用户，甚至在 **同等 RAM 的 CPU 上** 也能运行 —— 无需昂贵的 GPU 升级。

## 功能特性

- **单服务器运行 3 个模型：**
  - `CustomVoice` (1.7B) — 预定义语音，常驻 GPU
  - `VoiceDesign` (1.7B) — 通过描述设计语音，懒加载
  - `Base/Clone` (1.7B) — 语音克隆，懒加载
- **懒加载 + VRAM 池：** 只有 CustomVoice 常驻 GPU。VoiceDesign 和 Base/Clone 共享 VRAM，按需加载。
- **无状态语音克隆提示：** 服务器不保存状态。提示序列化为 base64，由客户端存储。
- **OpenAI 兼容：** 端点位于 `/v1/audio/speech`、`/v1/models` 等。
- **自动卸载：** 懒加载模型在闲置后自动卸载。

## 系统要求

- Python 3.10+
- **SoX** — librosa 音频处理所需（`setup.sh`/`setup.bat` 自动安装）
- GPU（可选）：任何支持 **CUDA 12.6+** 且拥有 **~12 GB VRAM** 的 NVIDIA GPU（如 RTX 3060、RTX 4060、A100 等）
- CPU 模式也可用，但生成速度 **慢 10-30 倍**

## 安装

```bash
git clone <repo-url>
cd qwen-tts-server

# Windows
setup.bat

# Linux/Mac
bash setup.sh
```

安装脚本会自动：
- 检查 Python 3.10+（如果缺失会显示安装说明）
- 如有需要安装 `python3-venv`（Debian/Ubuntu）
- 创建虚拟环境
- 从 `requirements.txt` 安装所有依赖

## 使用方法

```bash
# Windows
start.bat

# Linux/Mac
bash start.sh
```

或手动运行：
```bash
# Windows
.\venv\Scripts\python.exe main.py

# Linux/Mac
./venv/bin/python main.py
```

服务器默认监听 `http://0.0.0.0:8000`。

> **首次运行将下载约 ~3.4 GB**（CustomVoice 模型）来自 HuggingFace。后续启动是即时的。其他模型在首次使用时下载。

## API 端点

| 端点 | 方法 | 描述 |
|----------|--------|-------------|
| `/v1/audio/speech` | `POST` | 使用预定义语音进行 TTS（OpenAI 兼容） |
| `/v1/audio/voice-design` | `POST` | 通过描述设计语音 |
| `/v1/audio/voice-clone` | `POST` | 使用参考音频进行语音克隆 |
| `/v1/audio/voice-clone/prompt` | `POST` | 计算可复用提示（返回 base64） |
| `/v1/audio/voice-clone/generate` | `POST` | 从 base64 提示生成音频 |
| `/v1/models` | `GET` | 列出已加载的模型 |
| `/v1/audio/voices` | `GET` | 列出可用语音 |
| `/health` | `GET` | 健康检查 |
| `/docs` | `GET` | 交互式文档（Swagger UI） |

## 工作原理

### 标准 TTS 流程

```
┌─────────┐   POST /v1/audio/speech          ┌─────────────────┐
│ Client  │ ───────────────────────────────> │  Qwen TTS Server│
│         │  { input, voice, language }      │  (CustomVoice)  │
│         │                                  │     [GPU HOT]   │
│         │ <─────────────────────────────── │                 │
│         │   audio/wav  (~5 sec)            │                 │
└─────────┘                                  └─────────────────┘
```

### 语音克隆流程（无状态）

服务器**不保存任何状态**。所有语音配置文件都存储在客户端。

```
步骤 1：创建语音配置文件（一次性）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────┐   POST /v1/audio/voice-clone/prompt   ┌─────────────────┐
│ Client  │ ────────────────────────────────────> │  Qwen TTS Server│
│         │  { ref_audio, ref_text }              │  (Base/Clone)   │
│         │                                       │   [GPU LAZY]    │
│         │ <──────────────────────────────────── │                 │
│         │   { voice_clone_prompt_b64 }          │                 │
└─────────┘                                       └─────────────────┘
     │
     ▼
┌─────────────────────────────┐
│  客户端存储 base64 blob      │
│  (SQLite / Redis / etc.)    │
└─────────────────────────────┘

步骤 2：生成克隆语音（随时，重复多次）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────┐   POST /v1/audio/voice-clone/generate   ┌─────────────────┐
│ Client  │ ──────────────────────────────────────> │  Qwen TTS Server│
│         │  { input, voice_clone_prompt_b64 }      │  (Base/Clone)   │
│         │                                       │   [GPU LAZY]    │
│         │ <──────────────────────────────────── │                 │
│         │   audio/wav                           │                 │
└─────────┘                                       └─────────────────┘
```

## 示例

### 使用预定义语音进行 TTS

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hello world",
    "voice": "Vivian",
    "language": "English",
    "response_format": "wav"
  }' \
  --output speech.wav
```

### 语音克隆（无状态）

**1. 创建提示：**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "ref_audio": "https://example.com/my_voice.wav",
    "ref_text": "Exact transcript of the reference audio"
  }'
```

保存响应中的 `voice_clone_prompt_b64`。

**2. 生成音频：**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hello, this is my cloned voice",
    "voice_clone_prompt_b64": "<保存的-base64>",
    "response_format": "wav"
  }' \
  --output clone.wav
```

## 环境变量

| 变量 | 默认值 | 描述 |
|----------|---------|-------------|
| `QWEN_TTS_HOST` | `0.0.0.0` | 监听主机 |
| `QWEN_TTS_PORT` | `8000` | 端口 |
| `QWEN_CUSTOM_VOICE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | CustomVoice 模型 |
| `QWEN_VOICE_DESIGN_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | VoiceDesign 模型 |
| `QWEN_VOICE_CLONE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Base/Clone 模型 |
| `QWEN_LAZY_TIMEOUT_SECONDS` | `300` | 自动卸载前的秒数 |

## VRAM 架构

```
CustomVoice (1.7B)  -> GPU HOT   (~5.5 GB, 始终)
VoiceDesign (1.7B)  -> GPU LAZY  (~5.5 GB, 独占)
Base/Clone  (1.7B)  -> GPU LAZY  (~5.5 GB, 独占)
```

VoiceDesign 和 Base/Clone **永远不会同时加载**。

### CPU 模式

设置 `QWEN_TTS_DEVICE=cpu` 以在无 GPU 的情况下运行。服务器可以工作，但生成时间会显著变慢：

```bash
# Windows
$env:QWEN_TTS_DEVICE="cpu"
.\venv\Scripts\python.exe main.py

# Linux/Mac
QWEN_TTS_DEVICE=cpu python main.py
```

## 可选：Flash Attention

[Flash Attention](https://github.com/Dao-AILab/flash-attention) 可以提高推理速度并减少长序列的 VRAM 使用。它**不是必需的** — 服务器使用 PyTorch 内置的 SDPA 即可正常运行。

> **仅限 Linux。** Flash Attention 需要编译 CUDA 内核，不支持 Windows 或 macOS。还需要 compute capability ≥ 8.0 的 NVIDIA GPU（Ampere 或更新：RTX 3000/4000、A100 等）。

### 快速安装（预编译 wheel）

提供预编译 wheel，适用于 **Linux x86_64 + Python 3.12 + CUDA 13 + Ampere GPU**（RTX 3060/3070/3080/3090/A100）：

```bash
# 下载并安装预编译 wheel
wget https://github.com/feojeda/qwen-tts-server/releases/download/flash-attn-v2.8.3/flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
./venv/bin/pip install flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
rm flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
```

> 此 wheel 仅适用于编译时的精确环境（Linux x86_64、Python 3.12、CUDA 13.x、compute capability 8.x）。如不匹配，请从源码编译。

### 从源码编译（Linux，RAM < 32 GB）

编译会占用大量 RAM（每个并行任务约 4-8 GB）。如果系统内存有限，请限制并行任务数并仅针对你的 GPU 架构编译：

```bash
# 先安装 ninja（更快构建）和 nvcc
./venv/bin/pip install ninja nvidia-cuda-nvcc

# 仅针对你的 GPU 编译，限制并行任务避免 OOM
FLASH_ATTN_CUDA_ARCHS="86" MAX_JOBS=3 ./venv/bin/pip install flash-attn --no-build-isolation
```

**`FLASH_ATTN_CUDA_ARCHS`** 告诉编译器仅为你 GPU 的 compute capability 构建内核。根据硬件调整：

| GPU 系列 | Compute Capability | `FLASH_ATTN_CUDA_ARCHS` |
|---|---|---|
| RTX 3060, 3070, 3080, 3090 | 8.6 | `"86"` |
| RTX 4060, 4070, 4080, 4090 | 8.9 | `"89"` |
| A100, A10G | 8.0 | `"80"` |
| H100 | 9.0 | `"90"` |

**`MAX_JOBS`** 限制并行编译任务数以避免内存不足：

| 系统内存 | 推荐 `MAX_JOBS` |
|---|---|
| 16 GB | `2`–`3` |
| 32 GB | `4`–`6` |
| 64 GB+ | 省略（使用所有核心） |

> **重要：** 编译前请停止 TTS 服务器。同时运行两者可能导致 OOM kill。

### 安装（Linux，RAM ≥ 32 GB）

```bash
./venv/bin/pip install ninja nvidia-cuda-nvcc
./venv/bin/pip install flash-attn --no-build-isolation
```

## 测试

```bash
# 单元测试（快速，不加载模型）
pytest tests/ -v

# 集成测试（慢，需要真实模型）
pytest tests/test_integration.py -v --run-integration
```

| 测试套件 | 文件 | 模型加载 | 速度 | 在 CI 中运行 |
|-----------|-------|---------------|-------|-----------|
| **单元** | `test_*.py` 除了 `test_integration.py` | Mock（不下载） | ~0.5秒 | ✅ 是 |
| **集成** | 仅 `test_integration.py` | HuggingFace 真实模型 | ~5-15 分钟 | ❌ 否 |

集成测试标记为 `@pytest.mark.integration`，**默认跳过**。它们加载真实的 Qwen3-TTS 模型，首次运行时下载权重，并生成实际音频。仅在本地验证端到端行为时运行。

## 模型缓存位置

默认情况下，HuggingFace 将模型下载到用户主目录（Linux/Mac 为 `~/.cache/huggingface/hub/`，Windows 为 `%USERPROFILE%\.cache\huggingface\hub\`）。本项目将缓存覆盖到项目文件夹，以便模型与代码位于同一驱动器。

| 变量 | 默认值（已覆盖） | 项目位置 |
|----------|---------------------|------------------|
| `HF_HOME` | `~/.cache/huggingface` | `./cache/hf/` |

**`start.bat`** 和 **`start.sh`** 会自动设置。如果手动运行 `main.py`，请自行设置：

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

`cache/` 目录已在 `.gitignore` 中。

## Docker

```bash
# 构建
docker build -t qwen-tts-server .

# 使用 GPU 运行
docker run --gpus all -p 8000:8000 qwen-tts-server

# 仅 CPU 运行
docker run -p 8000:8000 -e QWEN_TTS_DEVICE=cpu qwen-tts-server
```

基础镜像：`nvidia/cuda:12.6.0-runtime-ubuntu22.04`。需要 NVIDIA Container Toolkit 进行 GPU 透传。

## 贡献

欢迎提交 PR！贡献指南为英文：[CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

Apache 2.0（与 Qwen3-TTS 相同）
