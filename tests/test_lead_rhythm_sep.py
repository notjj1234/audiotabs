"""Lead/Rhythm split backend: pinned downloads, config loader, availability."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from audio_to_tab import roformer
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


def test_availability_requires_bs_roformer_melband(monkeypatch):
    monkeypatch.setattr(roformer, "_is_bs_melband_available", lambda: False)
    assert is_lead_rhythm_split_available() is False
    monkeypatch.setattr(roformer, "_is_bs_melband_available", lambda: True)
    assert is_lead_rhythm_split_available() is True


def test_mode_id_is_stable():
    assert LEAD_RHYTHM_SPLIT_ID == "lead_rhythm_split"


def test_pinned_sha256_format():
    for digest in (MBR_LEAD_RHYTHM_CKPT_SHA256, MBR_LEAD_RHYTHM_CONFIG_SHA256):
        assert len(digest) == 64
        int(digest, 16)
