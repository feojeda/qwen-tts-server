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

- Python 3.10+
- **SoX** — librosa の音声処理に必要（`setup.sh`/`setup.bat` で自動インストール）
- GPU（オプション）：**CUDA 12.6+** をサポートし、**~12 GB VRAM** を持つ NVIDIA GPU（例：RTX 3060、RTX 4060、A100 など）
- CPU モードも動作しますが、生成は **10-30 倍遅く** なります

## インストール

```bash
git clone <repo-url>
cd qwen-tts-server

# Windows
setup.bat

# Linux/Mac
bash setup.sh
```

セットアップスクリプトは自動的に以下を行います：
- Python 3.10+ の確認（見つからない場合はインストール手順を表示）
- 必要に応じて `python3-venv` をインストール（Debian/Ubuntu）
- 仮想環境の作成
- `requirements.txt` からすべての依存関係をインストール

## 使い方

```bash
# Windows
start.bat

# Linux/Mac
bash start.sh
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

## オプション：Flash Attention

[Flash Attention](https://github.com/Dao-AILab/flash-attention) は推論速度の向上と長いシーケンスでの VRAM 使用量削減に役立ちます。**必須ではありません** — サーバーは PyTorch の内蔵 SDPA で正常に動作します。

> **Linux のみ。** Flash Attention は CUDA カーネルのコンパイルが必要で、Windows や macOS では利用できません。また、compute capability ≥ 8.0 の NVIDIA GPU（Ampere 以降：RTX 3000/4000、A100 など）が必要です。

### クイックインストール（プリコンパイル済み wheel）

**Linux x86_64 + Python 3.12 + CUDA 13 + Ampere GPU**（RTX 3060/3070/3080/3090/A100）用のプリコンパイル済み wheel が利用可能です：

```bash
# プリコンパイル済み wheel をダウンロードしてインストール
wget https://github.com/feojeda/qwen-tts-server/releases/download/flash-attn-v2.8.3/flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
./venv/bin/pip install flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
rm flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl
```

> この wheel はコンパイル時の環境でのみ動作します（Linux x86_64、Python 3.12、CUDA 13.x、compute capability 8.x）。環境が一致しない場合はソースからコンパイルしてください。

### ソースからコンパイル（Linux、RAM < 32 GB）

コンパイルは多くの RAM を使用します（並列ジョブごとに約 4-8 GB）。メモリが限られている場合は、並列ジョブ数を制限し、GPU アーキテクチャのみを対象にコンパイルしてください：

```bash
# まず ninja（高速ビルド）と nvcc をインストール
./venv/bin/pip install ninja nvidia-cuda-nvcc

# GPU のみにコンパイル、OOM を防ぐためジョブ数を制限
FLASH_ATTN_CUDA_ARCHS="86" MAX_JOBS=3 ./venv/bin/pip install flash-attn --no-build-isolation
```

**`FLASH_ATTN_CUDA_ARCHS`** は GPU の compute capability のみカーネルをビルドするようコンパイラに指示します。ハードウェアに合わせて調整してください：

| GPU シリーズ | Compute Capability | `FLASH_ATTN_CUDA_ARCHS` |
|---|---|---|
| RTX 3060, 3070, 3080, 3090 | 8.6 | `"86"` |
| RTX 4060, 4070, 4080, 4090 | 8.9 | `"89"` |
| A100, A10G | 8.0 | `"80"` |
| H100 | 9.0 | `"90"` |

**`MAX_JOBS`** はメモリ不足を防ぐため並列コンパイルジョブ数を制限します：

| システム RAM | 推奨 `MAX_JOBS` |
|---|---|
| 16 GB | `2`–`3` |
| 32 GB | `4`–`6` |
| 64 GB+ | 省略（全コア使用） |

> **重要：** コンパイル前に TTS サーバーを停止してください。同時に実行すると OOM kill が発生する可能性があります。

### インストール（Linux、RAM ≥ 32 GB）

```bash
./venv/bin/pip install ninja nvidia-cuda-nvcc
./venv/bin/pip install flash-attn --no-build-isolation
```

## テスト

```bash
# ユニットテスト（高速、モデルロードなし）
pytest tests/ -v

# 統合テスト（遅い、実際のモデルが必要）
pytest tests/test_integration.py -v --run-integration
```

| テストスイート | ファイル | モデル読み込み | 速度 | CI で実行 |
|-----------|-------|---------------|-------|-----------|
| **Unit** | `test_integration.py` 以外 | Mock（ダウンロードなし） | ~0.5秒 | ✅ はい |
| **Integration** | `test_integration.py` のみ | HuggingFace の実モデル | ~5-15 分 | ❌ いいえ |

統合テストは `@pytest.mark.integration` でマークされており、**デフォルトでスキップされます**。実際の Qwen3-TTS モデルを読み込み、初回実行時に重みをダウンロードし、実際のオーディオを生成します。実際のハードウェアでエンドツーエンドの動作を確認する場合のみ、ローカルで実行してください。

## モデルキャッシュの場所

デフォルトでは、HuggingFace はユーザーのホームディレクトリにモデルをダウンロードします（Linux/Mac は `~/.cache/huggingface/hub/`、Windows は `%USERPROFILE%\.cache\huggingface\hub\`）。このプロジェクトでは、モデルがコードと同じドライブに残るように、キャッシュをプロジェクトフォルダにオーバーライドしています。

| 変数 | デフォルト（オーバーライド済み） | プロジェクトの場所 |
|----------|---------------------|------------------|
| `HF_HOME` | `~/.cache/huggingface` | `./cache/hf/` |

**`start.bat`** と **`start.sh`** はこれを自動的に設定します。`main.py` を手動で実行する場合は、自分で設定してください：

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

`cache/` ディレクトリはすでに `.gitignore` に含まれています。

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
