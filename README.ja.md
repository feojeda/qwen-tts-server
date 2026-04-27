# Qwen TTS Server

<div align="center">

[English](README.md) | [Español](README.es.md) | [简体中文](README.zh.md) | **日本語**

</div>

[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) の REST API で、マルチモデル対応、VRAM レイジーローディング、ステートレスな音声クローンプロンプトを備えています。

## なぜこのプロジェクトを作ったのか？

私はゲーミング PC で **Qwen3-TTS をローカルで実行** したかったのですが、構成は **RTX 3060（12 GB VRAM）** でした。問題は、3 つの 1.7B モデルを同時にロードすると **~16.5 GB VRAM** が必要で、単純に収まらないことです。私の解決策は **VRAM プール + レイジーローディング** でした：1 つのモデルのみが GPU に常駐し、他のモデルはオンデマンドでロードされ、同じ VRAM スペースを共有します。このアプローチは、**12 GB VRAM カード**（RTX 3060、4060 など）を持つ人や、**同等の RAM を持つ CPU 上** でさえ完璧に動作します — 高価な GPU アップグレードは不要です。

## 機能

- **単一サーバーで 3 モデル：**
  - `CustomVoice` (1.7B) — 定義済み音声、常に GPU に常駐
  - `VoiceDesign` (1.7B) — 説明による音声デザイン、レイジーロード
  - `Base/Clone` (1.7B) — 音声クローニング、レイジーロード
- **レイジーローディング + VRAM プール：** CustomVoice のみが GPU に常駐。VoiceDesign と Base/Clone は VRAM を共有し、オンデマンドでロードされます。
- **ステートレスな音声クローンプロンプト：** サーバーは状態を保持しません。プロンプトは base64 にシリアライズされ、クライアントが保存します。
- **OpenAI 互換：** `/v1/audio/speech`、`/v1/models` などのエンドポイント。
- **自動アンロード：** レイジーロードモデルは非アクティブ後に自動的にアンロードされます。

## 要件

- Python 3.12+
- GPU（オプション）：**CUDA 12.6+** をサポートし、**~12 GB VRAM** を持つ NVIDIA GPU（例：RTX 3060、RTX 4060、A100 など）
- CPU モードも動作しますが、生成は **10-30 倍遅く** なります

## インストール

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

## 使い方

```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh
./start.sh
```

または手動で：
```bash
# Windows
.\venv\Scripts\python.exe main.py

# Linux/Mac
./venv/bin/python main.py
```

サーバーはデフォルトで `http://0.0.0.0:8000` をリッスンします。

> **初回実行時に約 ~3.4 GB**（CustomVoice モデル）を HuggingFace からダウンロードします。後続の起動は即座です。他のモデルは初回使用時にダウンロードされます。

## エンドポイント

| エンドポイント | メソッド | 説明 |
|----------|--------|-------------|
| `/v1/audio/speech` | `POST` | 定義済み音声での TTS（OpenAI 互換） |
| `/v1/audio/voice-design` | `POST` | 説明による音声デザイン |
| `/v1/audio/voice-clone` | `POST` | 参照音声による音声クローニング |
| `/v1/audio/voice-clone/prompt` | `POST` | 再利用可能なプロンプトを計算（base64 を返す） |
| `/v1/audio/voice-clone/generate` | `POST` | base64 プロンプトから音声を生成 |
| `/v1/models` | `GET` | ロード済みモデルを一覧表示 |
| `/v1/audio/voices` | `GET` | 利用可能な音声を一覧表示 |
| `/health` | `GET` | ヘルスチェック |
| `/docs` | `GET` | インタラクティブドキュメント（Swagger UI） |

## 仕組み

### 標準 TTS フロー

```
┌─────────┐   POST /v1/audio/speech          ┌─────────────────┐
│ Client  │ ───────────────────────────────> │  Qwen TTS Server│
│         │  { input, voice, language }      │  (CustomVoice)  │
│         │                                  │     [GPU HOT]   │
│         │ <─────────────────────────────── │                 │
│         │   audio/wav  (~5 sec)            │                 │
└─────────┘                                  └─────────────────┘
```

### 音声クローンフロー（ステートレス）

サーバーは**ゼロ状態**を保持します。すべての音声プロファイルはクライアント上に存在します。

```
ステップ 1：音声プロファイルの作成（一度きり）
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
│  クライアントが base64 blob を保存  │
│  (SQLite / Redis / etc.)    │
└─────────────────────────────┘

ステップ 2：クローン音声の生成（いつでも、繰り返し）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────┐   POST /v1/audio/voice-clone/generate   ┌─────────────────┐
│ Client  │ ──────────────────────────────────────> │  Qwen TTS Server│
│         │  { input, voice_clone_prompt_b64 }      │  (Base/Clone)   │
│         │                                       │   [GPU LAZY]    │
│         │ <──────────────────────────────────── │                 │
│         │   audio/wav                           │                 │
└─────────┘                                       └─────────────────┘
```

## 例

### 定義済み音声での TTS

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

### 音声クローン（ステートレス）

**1. プロンプトを作成：**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "ref_audio": "https://example.com/my_voice.wav",
    "ref_text": "Exact transcript of the reference audio"
  }'
```

レスポンスから `voice_clone_prompt_b64` を保存してください。

**2. 音声を生成：**
```bash
curl -X POST http://localhost:8000/v1/audio/voice-clone/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-tts",
    "input": "Hello, this is my cloned voice",
    "voice_clone_prompt_b64": "<保存した-base64>",
    "response_format": "wav"
  }' \
  --output clone.wav
```

## 環境変数

| 変数 | デフォルト | 説明 |
|----------|---------|-------------|
| `QWEN_TTS_HOST` | `0.0.0.0` | リッスンホスト |
| `QWEN_TTS_PORT` | `8000` | ポート |
| `QWEN_CUSTOM_VOICE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | CustomVoice モデル |
| `QWEN_VOICE_DESIGN_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | VoiceDesign モデル |
| `QWEN_VOICE_CLONE_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Base/Clone モデル |
| `QWEN_LAZY_TIMEOUT_SECONDS` | `300` | 自動アンロード前の秒数 |

## VRAM アーキテクチャ

```
CustomVoice (1.7B)  -> GPU HOT   (~5.5 GB, 常時)
VoiceDesign (1.7B)  -> GPU LAZY  (~5.5 GB, 排他)
Base/Clone  (1.7B)  -> GPU LAZY  (~5.5 GB, 排他)
```

VoiceDesign と Base/Clone は**同時にロードされることはありません**。

### CPU モード

`QWEN_TTS_DEVICE=cpu` を設定して GPU なしで実行します。サーバーは動作しますが、生成時間は大幅に遅くなります：

```bash
# Windows
$env:QWEN_TTS_DEVICE="cpu"
.\venv\Scripts\python.exe main.py

# Linux/Mac
QWEN_TTS_DEVICE=cpu python main.py
```

## テスト

```bash
# ユニットテスト（高速、モデルロードなし）
pytest tests/ -v

# 統合テスト（遅い、GPU が必要）
pytest tests/ -v --run-integration
```

## Docker

```bash
# ビルド
docker build -t qwen-tts-server .

# GPU で実行
docker run --gpus all -p 8000:8000 qwen-tts-server

# CPU のみで実行
docker run -p 8000:8000 -e QWEN_TTS_DEVICE=cpu qwen-tts-server
```

ベースイメージ：`nvidia/cuda:12.6.0-runtime-ubuntu22.04`。GPU パススルーには NVIDIA Container Toolkit が必要です。

## コントリビューション

PR を歓迎します。ガイドラインは英語です：[CONTRIBUTING.md](CONTRIBUTING.md)。

## ライセンス

Apache 2.0（Qwen3-TTS と同じ）
