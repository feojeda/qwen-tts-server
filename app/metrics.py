"""Thread-safe metrics counters for the TTS server.

Tracks total text characters processed, speech tokens generated,
and requests served across all endpoints.

Speech tokens are approximated as: audio_duration_seconds * codec_rate.
For Qwen3-TTS-Tokenizer-12Hz the rate is 12.5 tokens/second.
"""

import threading
import time
from typing import Dict, Any


class MetricsCounter:
    """Thread-safe counters for TTS usage metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests_total = 0
        self._text_chars_total = 0
        self._speech_tokens_total = 0
        self._audio_seconds_total = 0.0
        self._errors_total = 0
        self._start_time = time.time()

    def record(
        self,
        text_input: str,
        audio_duration_seconds: float,
        speech_tokens: int,
        error: bool = False,
    ) -> None:
        """Record metrics for a single generation request.

        Args:
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

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of current counters."""
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                "requests_total": self._requests_total,
                "text_chars_total": self._text_chars_total,
                "speech_tokens_total": self._speech_tokens_total,
                "audio_seconds_total": round(self._audio_seconds_total, 2),
                "errors_total": self._errors_total,
                "uptime_seconds": round(uptime, 2),
            }


# Global singleton — instantiated at import time.
metrics = MetricsCounter()
