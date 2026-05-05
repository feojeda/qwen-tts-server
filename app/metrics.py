"""Thread-safe metrics counters for the TTS server.

Tracks total text characters processed, speech tokens generated,
and requests served — globally and per model.

Speech tokens are approximated as: audio_duration_seconds * codec_rate.
For Qwen3-TTS-Tokenizer-12Hz the rate is 12.5 tokens/second.
"""

import threading
import time
from typing import Dict, Any


class ModelMetrics:
    """Counters for a single model."""

    def __init__(self):
        self.requests = 0
        self.text_chars = 0
        self.speech_tokens = 0
        self.audio_seconds = 0.0
        self.errors = 0


class MetricsCounter:
    """Thread-safe counters for TTS usage metrics (global + per-model)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests_total = 0
        self._text_chars_total = 0
        self._speech_tokens_total = 0
        self._audio_seconds_total = 0.0
        self._errors_total = 0
        self._start_time = time.time()
        self._models: Dict[str, ModelMetrics] = {}

    def record(
        self,
        model: str,
        text_input: str,
        audio_duration_seconds: float,
        speech_tokens: int,
        error: bool = False,
    ) -> None:
        """Record metrics for a single generation request.

        Args:
            model: Model ID used for this request.
            text_input: The input text that was synthesised.
            audio_duration_seconds: Duration of the generated audio.
            speech_tokens: Number of codec tokens generated.
            error: Whether the request ended in an error.
        """
        with self._lock:
            self._requests_total += 1
            self._text_chars_total += len(text_input)
            self._speech_tokens_total += speech_tokens
            self._audio_seconds_total += audio_duration_seconds
            if error:
                self._errors_total += 1

            per_model = self._models.setdefault(model, ModelMetrics())
            per_model.requests += 1
            per_model.text_chars += len(text_input)
            per_model.speech_tokens += speech_tokens
            per_model.audio_seconds += audio_duration_seconds
            if error:
                per_model.errors += 1

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of current counters (global + per-model)."""
        with self._lock:
            uptime = time.time() - self._start_time
            models = {
                model_id: {
                    "requests": m.requests,
                    "text_chars": m.text_chars,
                    "speech_tokens": m.speech_tokens,
                    "audio_seconds": round(m.audio_seconds, 2),
                    "errors": m.errors,
                }
                for model_id, m in self._models.items()
            }
            return {
                "requests_total": self._requests_total,
                "text_chars_total": self._text_chars_total,
                "speech_tokens_total": self._speech_tokens_total,
                "audio_seconds_total": round(self._audio_seconds_total, 2),
                "errors_total": self._errors_total,
                "uptime_seconds": round(uptime, 2),
                "models": models,
            }


# Global singleton — instantiated at import time.
metrics = MetricsCounter()
