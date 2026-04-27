"""Tests for model lifecycle, VRAM pool, and prompt serialization (app/models.py)."""

import base64
import pickle
import pytest

from app.models import _serialize_prompt, _deserialize_prompt


class TestPromptSerialization:
    def test_roundtrip_dict(self):
        original = {"speaker_embedding": [0.1, 0.2, 0.3], "text": "hello"}
        b64 = _serialize_prompt(original)
        assert isinstance(b64, str)
        assert len(b64) > 0
        restored = _deserialize_prompt(b64)
        assert restored == original

    def test_roundtrip_nested(self):
        original = {"a": {"b": [1, 2, 3]}, "c": None}
        b64 = _serialize_prompt(original)
        restored = _deserialize_prompt(b64)
        assert restored == original

    def test_deserialize_invalid_base64(self):
        with pytest.raises(Exception):
            _deserialize_prompt("not-valid-base64!!!")

    def test_deserialize_empty_string(self):
        with pytest.raises(Exception):
            _deserialize_prompt("")
