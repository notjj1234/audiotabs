"""Lead/Rhythm guitar split stage (Mel-Band RoFormer by listra92).

2026-11-19: the pipeline's first genuine *lead vs rhythm* separator. The
existing ``lead_rhythm.py`` is a post-hoc heuristic classifier on one
combined Demucs guitar stem — useful, but not a separator. This module
integrates the community checkpoint trained for exactly two stems:

- **Mel-Band RoFormer Lead-Rhythm Guitar by listra92** — stems
  ``[Lead, Rhythm]`` (``training.instruments``), ``target_instrument: Lead``,
  44.1 kHz. One-target inference: Lead comes from the model, Rhythm is the
  residual of the guitar mixture (same pattern as the becruily MelBand
  guitar model; see ``roformer._run_inprocess``).

Checkpoint hosting: ``noblebarkrr/mvsepless_resources`` on Hugging Face is a
community mirror aggregating many trainers' models. **No license is stated
for this checkpoint — treat it as all-rights-reserved, same posture as
BS-RoFormer-SW (see ``roformer.py``).** Weights are SHA256-pinned, cached
under ``separator_cache_dir()``, and never committed.

Runtime: the in-process ``bs_roformer`` package (optional extra
``[roformer]``) — the same route ``run_melband_guitar`` prefers. The
``audio_separator`` UVR stack cannot load this checkpoint unchanged: its
``load_model`` only accepts filenames from its own registry
(``separator.py:873`` raises for unknown files; verified 2026-11-19 against
audio-separator 0.48.0), and this checkpoint is not in that registry.
"""

from __future__ import annotations

import logging
from pathlib import Path

from audio_to_tab import roformer

logger = logging.getLogger(__name__)

LEAD_RHYTHM_SPLIT_ID = "lead_rhythm_split"

LEAD_RHYTHM_MODEL_DIR = "mbr_lead_rhythm_guitar_listra92"
MBR_LEAD_RHYTHM_CKPT_NAME = "mbr_lead_rhythm_guitar_listra92.ckpt"
MBR_LEAD_RHYTHM_CONFIG_NAME = "mbr_lead_rhythm_guitar_listra92_config.yaml"

MBR_LEAD_RHYTHM_HF_REPO = "noblebarkrr/mvsepless_resources"
MBR_LEAD_RHYTHM_CKPT_URL = (
    f"https://huggingface.co/{MBR_LEAD_RHYTHM_HF_REPO}/resolve/main/"
    f"mel_band_roformer/{MBR_LEAD_RHYTHM_CKPT_NAME}"
)
MBR_LEAD_RHYTHM_CONFIG_URL = (
    f"https://huggingface.co/{MBR_LEAD_RHYTHM_HF_REPO}/resolve/main/"
    f"mel_band_roformer/{MBR_LEAD_RHYTHM_CONFIG_NAME}"
)

# Phase 0 verification (2026-11-19): 337,073,664 bytes, computed locally.
MBR_LEAD_RHYTHM_CKPT_SHA256 = (
    "b3c47bca33609ca1ba0bb2d2076410bfd1eb941b051b72afc1f3e24d12b17eef"
)
MBR_LEAD_RHYTHM_CONFIG_SHA256 = (
    "a26685bc9ab10aab4dc153b74ec3559f1b4bd2251d129a13b6b22fe3a27d382d"
)

LEAD_RHYTHM_STEM_NAMES = ("lead_guitar", "rhythm_guitar")

INSTALL_HINT = (
    "Lead/Rhythm split requires the RoFormer runtime: pip install -e \".[roformer]\""
)


def mbr_lead_rhythm_paths() -> tuple[Path, Path]:
    root = roformer.separator_cache_dir() / LEAD_RHYTHM_MODEL_DIR
    return root / MBR_LEAD_RHYTHM_CKPT_NAME, root / MBR_LEAD_RHYTHM_CONFIG_NAME


def download_mbr_lead_rhythm_weights(*, force: bool = False) -> tuple[Path, Path]:
    """Download checkpoint + config (urllib, SHA256-pinned), unless verified cached."""
    ckpt, yaml_path = mbr_lead_rhythm_paths()
    if force:
        ckpt.unlink(missing_ok=True)
        yaml_path.unlink(missing_ok=True)
    roformer.download_sha256_file(
        MBR_LEAD_RHYTHM_CKPT_URL, ckpt, MBR_LEAD_RHYTHM_CKPT_SHA256
    )
    roformer.download_sha256_file(
        MBR_LEAD_RHYTHM_CONFIG_URL, yaml_path, MBR_LEAD_RHYTHM_CONFIG_SHA256
    )
    return ckpt, yaml_path


def load_mbr_lead_rhythm_config(yaml_path: Path) -> dict:
    """Load the model YAML and validate it is the verified Lead/Rhythm config."""
    config = roformer._load_yaml(Path(yaml_path))
    training = config.get("training") or {}
    instruments = list(training.get("instruments") or [])
    if instruments != ["Lead", "Rhythm"]:
        raise RuntimeError(
            f"Expected Lead/Rhythm instruments in {yaml_path}, got {instruments!r}"
        )
    audio = config.get("audio") or {}
    sample_rate = audio.get("sample_rate")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise RuntimeError(f"Missing audio.sample_rate in {yaml_path}")
    return config


def is_lead_rhythm_split_available() -> bool:
    """True when the installed bs_roformer runtime supports MelBand configs."""
    return roformer._is_bs_melband_available()
