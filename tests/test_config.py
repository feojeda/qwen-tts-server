"""Tests for configuration, VRAM detection, and model selection (app/config.py)."""

from app.config import _auto_select_models, _detect_vram_gb


class TestDetectVramGb:
    def test_returns_float(self):
        vram = _detect_vram_gb()
        assert isinstance(vram, float)
        assert vram >= 0.0


class TestAutoSelectModels:
    def test_high_vram_uses_1_7b(self):
        """11+ GB should select 1.7B models for all."""
        cv, vd, vc = _auto_select_models(12.0)
        assert "1.7B" in cv
        assert "1.7B" in vd
        assert "1.7B" in vc

    def test_medium_vram_uses_mixed(self):
        """7.5-10.9 GB should select mixed sizes."""
        cv, vd, vc = _auto_select_models(8.0)
        assert "0.6B" in cv
        assert "1.7B" in vd
        assert "0.6B" in vc

    def test_low_vram_uses_0_6b(self):
        """5.5-7.4 GB should select 0.6B models for all."""
        cv, vd, vc = _auto_select_models(6.0)
        assert "0.6B" in cv
        assert "0.6B" in vd
        assert "0.6B" in vc

    def test_cpu_uses_0_6b(self):
        """0 GB (no CUDA) should select 0.6B models for all."""
        cv, vd, vc = _auto_select_models(0.0)
        assert "0.6B" in cv
        assert "0.6B" in vd
        assert "0.6B" in vc

    def test_boundary_11_0(self):
        """Exactly 11.0 GB should get 1.7B models."""
        cv, vd, vc = _auto_select_models(11.0)
        assert "1.7B" in cv

    def test_boundary_7_5(self):
        """Exactly 7.5 GB should get mixed models."""
        cv, vd, vc = _auto_select_models(7.5)
        assert "0.6B" in cv
        assert "1.7B" in vd

    def test_boundary_5_5(self):
        """Exactly 5.5 GB should get 0.6B models."""
        cv, vd, vc = _auto_select_models(5.5)
        assert "0.6B" in cv
        assert "0.6B" in vd

    def test_very_high_vram(self):
        """Even very high VRAM should still get 1.7B models."""
        cv, vd, vc = _auto_select_models(48.0)
        assert "1.7B" in cv
        assert "1.7B" in vd
        assert "1.7B" in vc
