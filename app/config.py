"""Configuration, VRAM auto-detection, and model selection."""

import os

import torch


def _detect_vram_gb() -> float:
    """Detect available VRAM in GB. Returns 0.0 if no CUDA GPU."""
    if not torch.cuda.is_available():
        return 0.0
    try:
        total_bytes = torch.cuda.get_device_properties(0).total_memory
        return total_bytes / (1024 ** 3)
    except Exception:
        return 0.0


def _auto_select_models(vram_gb: float) -> tuple[str, str, str]:
    """
    Auto-select model sizes based on available VRAM.
    Returns (custom_voice, voice_design, voice_clone) model IDs.
    """
    if vram_gb >= 11.0:
        # 11+ GB: covers RTX 3060 12GB (reports ~11.7), RTX 4060, etc.
        return (
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        )
    elif vram_gb >= 7.5:
        # 7.5-10.9 GB: RTX 3070 laptop, RTX 4060 Ti 8GB, etc.
        # Peak ~7.5 GB (0.6B hot + 1.7B lazy)
        return (
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        )
    elif vram_gb >= 5.5:
        # 5.5-7.4 GB: RTX 3060 laptop, RTX 2060, GTX 1660 Ti, etc.
        # Peak ~4 GB (0.6B hot + 0.6B lazy)
        return (
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            "Qwen/Qwen3-TTS-12Hz-0.6B-VoiceDesign",
            "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        )
    else:
        # < 5.5 GB or CPU
        return (
            "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            "Qwen/Qwen3-TTS-12Hz-0.6B-VoiceDesign",
            "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        )


HOST = os.getenv("QWEN_TTS_HOST", "0.0.0.0")
PORT = int(os.getenv("QWEN_TTS_PORT", "8000"))

_vram_gb = _detect_vram_gb()
_auto_cv, _auto_vd, _auto_vc = _auto_select_models(_vram_gb)

CUSTOM_VOICE_MODEL = os.getenv("QWEN_CUSTOM_VOICE_MODEL", _auto_cv)
VOICE_DESIGN_MODEL = os.getenv("QWEN_VOICE_DESIGN_MODEL", _auto_vd)
VOICE_CLONE_MODEL = os.getenv("QWEN_VOICE_CLONE_MODEL", _auto_vc)

LAZY_TIMEOUT = int(os.getenv("QWEN_LAZY_TIMEOUT_SECONDS", "300"))
DEVICE_GPU = "cuda:0"
VRAM_GB = _vram_gb
