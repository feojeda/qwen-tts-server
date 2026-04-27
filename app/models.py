"""Model lifecycle, VRAM pool, and prompt serialization.

VRAM Pool rule: VoiceDesign and Base/Clone are mutually exclusive on GPU.
When one is requested while the other is loaded, the server unloads the
incumbent first (torch.cuda.empty_cache()). CustomVoice never unloads.

Threading: A single threading.Lock() (model_lock) serializes all lazy
load/unload operations. The internal helpers (_do_load_*, _do_unload_*)
assume the lock is already held; the public helpers (_get_voice_*)
acquire it. Never nest with model_lock: — caused a deadlock in an
earlier version.
"""

import io
import base64
import pickle
import time
import threading
from typing import Optional, Any

import torch
from qwen_tts import Qwen3TTSModel

from app.i18n import _t
from app.config import (
    CUSTOM_VOICE_MODEL,
    VOICE_DESIGN_MODEL,
    VOICE_CLONE_MODEL,
    LAZY_TIMEOUT,
    DEVICE_GPU,
    VRAM_GB,
)

# ---------------------------------------------------------------------------
# Model state
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
    """Serialize voice clone prompt to base64 using pickle.

    pickle is used instead of torch.save to avoid torch reimport issues
    during testing and because PyTorch tensors are picklable anyway.
    """
    return base64.b64encode(pickle.dumps(items)).decode("utf-8")


def _deserialize_prompt(b64_string: str) -> Any:
    """Deserialize voice clone prompt from base64."""
    return pickle.loads(base64.b64decode(b64_string.encode("utf-8")))


# ---------------------------------------------------------------------------
# Model lifecycle helpers (INTERNAL - must be called with model_lock held)
# ---------------------------------------------------------------------------
def _do_unload_voice_design():
    global voice_design_model
    if voice_design_model is not None:
        print(f"[LAZY] {_t('unloading')} VoiceDesign {_t('free_vram')}...")
        del voice_design_model
        voice_design_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(f"[LAZY] VoiceDesign {_t('unloaded')}.")


def _do_unload_voice_clone():
    global voice_clone_model
    if voice_clone_model is not None:
        print(f"[LAZY] {_t('unloading')} Base/Clone {_t('free_vram')}...")
        del voice_clone_model
        voice_clone_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(f"[LAZY] Base/Clone {_t('unloaded')}.")


def _do_load_voice_design() -> Qwen3TTSModel:
    global voice_design_model
    if voice_clone_model is not None:
        _do_unload_voice_clone()
    print(f"[LAZY] {_t('loading')} VoiceDesign: {VOICE_DESIGN_MODEL} ...")
    voice_design_model = Qwen3TTSModel.from_pretrained(
        VOICE_DESIGN_MODEL,
        device_map=DEVICE_GPU,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    last_used["voice_design"] = time.time()
    print(f"[LAZY] VoiceDesign {_t('loaded')}.")
    return voice_design_model


def _do_load_voice_clone() -> Qwen3TTSModel:
    global voice_clone_model
    if voice_design_model is not None:
        _do_unload_voice_design()
    print(f"[LAZY] {_t('loading')} Base/Clone: {VOICE_CLONE_MODEL} ...")
    voice_clone_model = Qwen3TTSModel.from_pretrained(
        VOICE_CLONE_MODEL,
        device_map=DEVICE_GPU,
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    last_used["voice_clone"] = time.time()
    print(f"[LAZY] Base/Clone {_t('loaded')}.")
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
                    print(f"[AUTO] VoiceDesign {_t('inactive_for')} {idle:.0f}s. {_t('releasing')}...")
                    _do_unload_voice_design()
            if voice_clone_model is not None:
                idle = now - last_used["voice_clone"]
                if idle > LAZY_TIMEOUT:
                    print(f"[AUTO] Base/Clone {_t('inactive_for')} {idle:.0f}s. {_t('releasing')}...")
                    _do_unload_voice_clone()


# ---------------------------------------------------------------------------
# Startup / Shutdown helpers
# ---------------------------------------------------------------------------
def load_custom_voice() -> Qwen3TTSModel:
    """Load the hot (always-on) CustomVoice model. Called once at startup."""
    global custom_voice_model
    device = DEVICE_GPU if VRAM_GB > 0 else "cpu"
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    attn = "sdpa" if device.startswith("cuda") else "eager"

    print(f"[INIT] {_t('loading')} CustomVoice (hot): {CUSTOM_VOICE_MODEL} ...")
    custom_voice_model = Qwen3TTSModel.from_pretrained(
        CUSTOM_VOICE_MODEL,
        device_map=device,
        dtype=dtype,
        attn_implementation=attn,
    )
    print(f"[INIT] CustomVoice {_t('ready')}.")
    return custom_voice_model


def shutdown_models():
    """Unload all models. Called once at shutdown."""
    global custom_voice_model
    shutdown_flag.set()
    with model_lock:
        _do_unload_voice_design()
        _do_unload_voice_clone()
    # custom_voice stays in GPU until process exits
    custom_voice_model = None
