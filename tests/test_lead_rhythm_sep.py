"""Lead/Rhythm split backend: pinned downloads, config loader, availability."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from audio_to_tab import lead_rhythm_sep, roformer
from audio_to_tab.lead_rhythm_sep import (
    LEAD_RHYTHM_SPLIT_ID,
    MBR_LEAD_RHYTHM_CKPT_SHA256,
    MBR_LEAD_RHYTHM_CKPT_URL,
    MBR_LEAD_RHYTHM_CONFIG_SHA256,
    MBR_LEAD_RHYTHM_CONFIG_URL,
    download_mbr_lead_rhythm_weights,
    is_lead_rhythm_split_available,
    load_mbr_lead_rhythm_config,
    mbr_lead_rhythm_paths,
)

MODEL_DIR = "mbr_lead_rhythm_guitar_listra92"
CKPT_NAME = "mbr_lead_rhythm_guitar_listra92.ckpt"
YAML_NAME = "mbr_lead_rhythm_guitar_listra92_config.yaml"

VERIFIED_YAML = """\
audio:
  chunk_size: 132300
  dim_f: 1024
  dim_t: 256
  hop_length: 441
  n_fft: 2048
  num_channels: 2
  sample_rate: 44100
  min_mean_abs: 0
model:
  dim: 384
  depth: 4
  stereo: true
  num_stems: 1
  num_bands: 60
  dim_head: 64
  heads: 8
  sample_rate: 44100
  mask_estimator_depth: 2
training:
  instruments:
    - Lead
    - Rhythm
  target_instrument: Lead
inference:
  batch_size: 1
  dim_t: 256
  num_overlap: 2
"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_paths_resolve_under_separator_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ATT_SEPARATOR_CACHE", str(tmp_path))
    ckpt, yaml_path = mbr_lead_rhythm_paths()
    assert ckpt == tmp_path / MODEL_DIR / CKPT_NAME
    assert yaml_path == tmp_path / MODEL_DIR / YAML_NAME
    assert MBR_LEAD_RHYTHM_CKPT_URL.endswith(CKPT_NAME)
    assert MBR_LEAD_RHYTHM_CONFIG_URL.endswith(YAML_NAME)


def test_download_accepts_preverified_cached_files(tmp_path, monkeypatch):
    monkeypatch.setenv("ATT_SEPARATOR_CACHE", str(tmp_path))
    ckpt, yaml_path = mbr_lead_rhythm_paths()
    ckpt.parent.mkdir(parents=True)
    ckpt.write_bytes(b"ckpt")
    yaml_path.write_bytes(b"yaml")
    # Real download_sha256_file: seeded hashes match, so it must return the
    # cached files without touching the network (any fetch would fail offline).
    monkeypatch.setattr(
        "audio_to_tab.lead_rhythm_sep.MBR_LEAD_RHYTHM_CKPT_SHA256", _sha256(b"ckpt")
    )
    monkeypatch.setattr(
        "audio_to_tab.lead_rhythm_sep.MBR_LEAD_RHYTHM_CONFIG_SHA256", _sha256(b"yaml")
    )
    assert download_mbr_lead_rhythm_weights() == (ckpt, yaml_path)


def test_download_fetches_missing_files_with_pin(tmp_path, monkeypatch):
    monkeypatch.setenv("ATT_SEPARATOR_CACHE", str(tmp_path))
    ckpt, yaml_path = mbr_lead_rhythm_paths()
    calls: list[tuple[str, Path, str]] = []

    def fake_download(url, dest, expected_sha256, **kwargs):
        calls.append((url, Path(dest), expected_sha256))
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"x")
        return Path(dest)

    monkeypatch.setattr(roformer, "download_sha256_file", fake_download)
    download_mbr_lead_rhythm_weights()
    assert [c[0] for c in calls] == [MBR_LEAD_RHYTHM_CKPT_URL, MBR_LEAD_RHYTHM_CONFIG_URL]
    assert calls[0][2] == MBR_LEAD_RHYTHM_CKPT_SHA256
    assert calls[1][2] == MBR_LEAD_RHYTHM_CONFIG_SHA256
    assert [c[1] for c in calls] == [ckpt, yaml_path]


def test_download_force_redownloads(tmp_path, monkeypatch):
    monkeypatch.setenv("ATT_SEPARATOR_CACHE", str(tmp_path))
    ckpt, _ = mbr_lead_rhythm_paths()
    ckpt.parent.mkdir(parents=True)
    ckpt.write_bytes(b"ckpt")
    monkeypatch.setattr(
        "audio_to_tab.lead_rhythm_sep.MBR_LEAD_RHYTHM_CKPT_SHA256", _sha256(b"ckpt")
    )
    calls: list[str] = []

    def fake_download(url, dest, expected_sha256, **kwargs):
        calls.append(url)
        Path(dest).write_bytes(b"y")
        return Path(dest)

    monkeypatch.setattr(roformer, "download_sha256_file", fake_download)
    download_mbr_lead_rhythm_weights(force=True)
    assert MBR_LEAD_RHYTHM_CKPT_URL in calls


def test_config_loader_reads_verified_yaml(tmp_path):
    yaml_path = tmp_path / YAML_NAME
    yaml_path.write_text(VERIFIED_YAML, encoding="utf-8")
    config = load_mbr_lead_rhythm_config(yaml_path)
    assert config["audio"]["sample_rate"] == 44100
    assert config["training"]["instruments"] == ["Lead", "Rhythm"]
    assert config["training"]["target_instrument"] == "Lead"
    assert config["audio"]["chunk_size"] == 132300
    assert config["inference"]["num_overlap"] == 2


def test_config_loader_rejects_wrong_stems(tmp_path):
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text(VERIFIED_YAML.replace("- Lead\n    - Rhythm", "- Vocals\n    - Drums"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="instruments"):
        load_mbr_lead_rhythm_config(yaml_path)


def test_config_loader_rejects_missing_sample_rate(tmp_path):
    yaml_path = tmp_path / "bad.yaml"
    text = VERIFIED_YAML.replace("  sample_rate: 44100\n", "", 1)
    yaml_path.write_text(text, encoding="utf-8")
    with pytest.raises(RuntimeError, match="sample_rate"):
        load_mbr_lead_rhythm_config(yaml_path)


def test_availability_needs_every_bundled_model_dependency(monkeypatch):
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda n, *a: None if n == "rotary_embedding_torch" else real(n, *a)
    )
    assert is_lead_rhythm_split_available() is False
    monkeypatch.setattr(importlib.util, "find_spec", lambda n, *a: object())
    assert is_lead_rhythm_split_available() is True


def test_bundled_model_matches_checkpoint_layout():
    """The pip MelBand packages hard-code mlp_expansion_factor=4; the checkpoint needs 2."""
    import inspect

    pytest.importorskip("torch")
    pytest.importorskip("rotary_embedding_torch")
    from audio_to_tab.vendor.mel_band_roformer.model import MelBandRoformer

    params = inspect.signature(MelBandRoformer.__init__).parameters
    assert "mlp_expansion_factor" in params and "skip_connection" in params


def test_mode_id_is_stable():
    assert LEAD_RHYTHM_SPLIT_ID == "lead_rhythm_split"


def test_pinned_sha256_format():
    for digest in (MBR_LEAD_RHYTHM_CKPT_SHA256, MBR_LEAD_RHYTHM_CONFIG_SHA256):
        assert len(digest) == 64
        int(digest, 16)


class TestRunLeadRhythmSplit:
    def _patch_runtime(self, monkeypatch, tmp_path, sample_rate=44100, chunk_size=132300):
        import numpy as np

        from audio_to_tab import roformer

        monkeypatch.setattr(
            "audio_to_tab.lead_rhythm_sep.is_lead_rhythm_split_available", lambda: True
        )
        yaml_path = tmp_path / "cfg.yaml"
        yaml_path.write_text(
            VERIFIED_YAML.replace("  sample_rate: 44100", f"  sample_rate: {sample_rate}", 1)
            .replace("  chunk_size: 132300", f"  chunk_size: {chunk_size}", 1),
            encoding="utf-8",
        )
        ckpt = tmp_path / "model.ckpt"
        ckpt.write_bytes(b"weights")
        monkeypatch.setattr(
            "audio_to_tab.lead_rhythm_sep.download_mbr_lead_rhythm_weights",
            lambda **kw: (ckpt, yaml_path),
        )
        monkeypatch.setattr(roformer, "_refuse_long_roformer_audio", lambda p: None)
        monkeypatch.setattr(roformer, "_cap_cpu_threads", lambda device: None)
        monkeypatch.setattr(lead_rhythm_sep, "build_lead_rhythm_model", lambda *a, **k: object())
        monkeypatch.setattr(roformer, "_torch_device", lambda device: device)

        calls: dict[str, object] = {}

        def fake_load_stereo(path, sr):
            calls["load_sr"] = sr
            n = int(2.0 * sr)
            return np.full((2, n), 0.5, dtype=np.float32)

        def fake_demix(model, mix, *, device, chunk_size, n_overlap, num_stems):
            calls["chunk_size"] = chunk_size
            calls["n_overlap"] = n_overlap
            calls["num_stems"] = num_stems
            return np.full((1, mix.shape[0], mix.shape[1]), 0.25, dtype=np.float32)

        monkeypatch.setattr(roformer, "_load_audio_stereo", fake_load_stereo)
        monkeypatch.setattr(roformer, "_demix_track", fake_demix)
        return calls

    def test_emits_exact_stem_names_and_residual_rhythm(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab.lead_rhythm_sep import run_lead_rhythm_split

        self._patch_runtime(monkeypatch, tmp_path)
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((44100, 2), dtype=np.float32), 44100)
        out = tmp_path / "out"

        artifacts, diag = run_lead_rhythm_split(src, out)

        assert set(artifacts) == {"lead_guitar", "rhythm_guitar"}
        assert artifacts["lead_guitar"].name == "lead_guitar.wav"
        assert artifacts["rhythm_guitar"].name == "rhythm_guitar.wav"
        lead, sr = sf.read(str(artifacts["lead_guitar"]), always_2d=True)
        rhythm, _ = sf.read(str(artifacts["rhythm_guitar"]), always_2d=True)
        assert sr == 44100
        np.testing.assert_allclose(lead, 0.25, atol=1e-3)
        np.testing.assert_allclose(rhythm, 0.25, atol=1e-3)  # mix 0.5 - lead 0.25
        assert diag.model_sample_rate == 44100
        assert diag.resampled is False

    def test_model_yaml_drives_sample_rate_chunk_overlap(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab.lead_rhythm_sep import run_lead_rhythm_split

        calls = self._patch_runtime(monkeypatch, tmp_path, sample_rate=22050, chunk_size=66150)
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((22050, 2), dtype=np.float32), 22050)

        _, diag = run_lead_rhythm_split(src, tmp_path / "out")

        assert calls["load_sr"] == 22050  # read from YAML, not hardcoded
        assert calls["chunk_size"] == 66150  # non-default proves YAML-driven
        assert calls["n_overlap"] == 2
        assert calls["num_stems"] == 1
        assert diag.resampled is False
        assert diag.model_sample_rate == 22050

    def test_mismatched_input_records_resample(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab.lead_rhythm_sep import run_lead_rhythm_split

        self._patch_runtime(monkeypatch, tmp_path)  # model at 44100
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((48000, 2), dtype=np.float32), 48000)

        _, diag = run_lead_rhythm_split(src, tmp_path / "out")

        assert diag.input_sample_rate == 48000
        assert diag.model_sample_rate == 44100
        assert diag.resampled is True

    def test_missing_backend_fails_loud(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab import lead_rhythm_sep

        monkeypatch.setattr(lead_rhythm_sep, "is_lead_rhythm_split_available", lambda: False)
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((44100, 2), dtype=np.float32), 44100)
        with pytest.raises(RuntimeError, match=r"[Ll]ead/rhythm"):
            lead_rhythm_sep.run_lead_rhythm_split(src, tmp_path / "out")
        assert not (tmp_path / "out").exists()

    def test_demix_failure_raises_without_fallback(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab import roformer
        from audio_to_tab.lead_rhythm_sep import run_lead_rhythm_split

        self._patch_runtime(monkeypatch, tmp_path)

        def boom(*a, **k):
            raise ValueError("model exploded")

        monkeypatch.setattr(roformer, "_demix_track", boom)
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((44100, 2), dtype=np.float32), 44100)
        with pytest.raises(RuntimeError, match="Lead/rhythm split failed"):
            run_lead_rhythm_split(src, tmp_path / "out")

    def test_short_input_still_splits_with_warning(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab.lead_rhythm_sep import run_lead_rhythm_split

        self._patch_runtime(monkeypatch, tmp_path)
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((4410, 2), dtype=np.float32), 44100)

        artifacts, diag = run_lead_rhythm_split(src, tmp_path / "out")

        assert set(artifacts) == {"lead_guitar", "rhythm_guitar"}
        assert any("short" in w for w in diag.warnings)

    def test_progress_callback_receives_phases(self, tmp_path, monkeypatch):
        import numpy as np
        import soundfile as sf

        from audio_to_tab.lead_rhythm_sep import run_lead_rhythm_split

        self._patch_runtime(monkeypatch, tmp_path)
        src = tmp_path / "guitar.wav"
        sf.write(str(src), np.zeros((44100, 2), dtype=np.float32), 44100)
        seen: list[tuple[str, float]] = []
        run_lead_rhythm_split(
            src, tmp_path / "out", on_progress=lambda m, f: seen.append((m, f))
        )
        assert seen and all(0.0 <= f <= 1.0 for _, f in seen)
