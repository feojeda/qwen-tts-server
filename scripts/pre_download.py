#!/usr/bin/env python3
"""Pre-download Qwen3-TTS models before starting the server.

Uses huggingface_hub.snapshot_download() which:
- Resumes interrupted downloads automatically (.incomplete files + Range headers).
- Uses hf_transfer for parallel chunked downloads when HF_HUB_ENABLE_HF_TRANSFER=1.

Mirror support:
    Set HF_ENDPOINT to use a mirror, e.g.:
        export HF_ENDPOINT=https://hf-mirror.com

Usage:
    # Download auto-selected models (same as server would use)
    ./venv/bin/python scripts/pre_download.py

    # Download a specific model
    ./venv/bin/python scripts/pre_download.py --model Qwen/Qwen3-TTS-12Hz-1.7B-Base

    # Using a mirror
    HF_ENDPOINT=https://hf-mirror.com ./venv/bin/python scripts/pre_download.py
"""

import argparse
import sys
import os

from huggingface_hub import snapshot_download, constants
from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

# Import model config (triggers VRAM auto-detection, which needs torch)
from app.config import CUSTOM_VOICE_MODEL, VOICE_DESIGN_MODEL, VOICE_CLONE_MODEL


def _endpoint_label() -> str:
    ep = constants.ENDPOINT
    if ep == "https://huggingface.co":
        return ep
    return f"{ep} (mirror)"


def is_model_cached(model_id: str) -> bool:
    """Check if model is already fully cached (no network call)."""
    try:
        snapshot_download(repo_id=model_id, local_files_only=True)
        return True
    except Exception:
        return False


def download_model(model_id: str) -> bool:
    if is_model_cached(model_id):
        print(f"[CACHED] {model_id}")
        return True

    print(f"[DOWNLOAD] {model_id}  ({_endpoint_label()})")
    try:
        path = snapshot_download(
            repo_id=model_id,
        )
        print(f"[OK] {model_id}")
        return True
    except GatedRepoError:
        print(f"[ERROR] {model_id}: Access restricted (gated repo).")
        print("        Log in with: huggingface-cli login")
        return False
    except RepositoryNotFoundError:
        print(f"[ERROR] {model_id}: Repository not found on HuggingFace.")
        return False
    except KeyboardInterrupt:
        print(f"\n[INTERRUPTED] {model_id} — download resumes on next run.")
        return False
    except Exception as e:
        print(f"[ERROR] {model_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Pre-download Qwen3-TTS models to local cache"
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Specific HuggingFace model ID to download (repeatable). "
             "If not set, downloads the auto-selected models from config.",
    )
    args = parser.parse_args()

    if args.models:
        models = args.models
    else:
        models = [CUSTOM_VOICE_MODEL, VOICE_DESIGN_MODEL, VOICE_CLONE_MODEL]

    # Deduplicate while preserving order
    seen = set()
    models = [m for m in models if not (m in seen or seen.add(m))]

    failed = []
    for model_id in models:
        if not download_model(model_id):
            failed.append(model_id)

    if not failed:
        return 0

    print(f"\n[WARN] {len(failed)} model(s) failed/incomplete:")
    for m in failed:
        print(f"  - {m}")
    print("Re-run to resume/retry.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
