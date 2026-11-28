"""Standalone YourMT3+ runner, executed by the *YourMT3 environment's* Python, never imported.

The app calls this file in a subprocess (see ``audio_to_tab.yourmt3``) so YourMT3's pinned
dependencies (transformers 4.45, huggingface_hub < 1) never meet the app's, its GPL code is
downloaded to the user's machine instead of shipping with the app, and a cancelled job can
kill it. It imports nothing from ``audio_to_tab``.

usage:
  python yourmt3_runner.py --home DIR --revision SHA --prefetch
  python yourmt3_runner.py --home DIR --revision SHA AUDIO OUT_JSON [--device cpu|mps|cuda]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types
from pathlib import Path

SPACE_REPO = "mimbres/YourMT3"
RUN_ID = "mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops"
CKPT_FILE = f"amt/logs/2024/{RUN_ID}/checkpoints/last.ckpt"
CODE_PATTERNS = [
    "model_helper.py",
    "amt/src/config/*",
    "amt/src/model/**",
    "amt/src/utils/**",
]
# "YPTF.MoE+Multi (noPS)", the Space's default model, with the Space's own arguments.
MODEL_ARGS = [
    f"{RUN_ID}@last.ckpt", "-p", "2024", "-tk", "mc13_full_plus_256", "-dec", "multi-t5",
    "-nl", "26", "-enc", "perceiver-tf", "-sqr", "1", "-ff", "moe", "-wf", "4", "-nmoe", "8",
    "-kmoe", "2", "-act", "silu", "-epe", "rope", "-rp", "1", "-ac", "spec", "-hop", "300",
    "-atc", "1", "-pr", "32",
]


def fetch(home: Path, revision: str) -> Path:
    """Code + checkpoint of the pinned Space revision into ``home/space`` (cached)."""
    from huggingface_hub import snapshot_download

    space = home / "space"
    snapshot_download(
        SPACE_REPO,
        repo_type="space",
        revision=revision,
        local_dir=str(space),
        allow_patterns=[*CODE_PATTERNS, CKPT_FILE],
    )
    return space


def pick_device(requested: str | None):
    import torch

    if requested == "cuda" and torch.cuda.is_available():
        return "cuda"
    if requested == "mps" and torch.backends.mps.is_available():
        return "mps"
    if requested in {"cpu", "cuda", "mps"}:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


class _NullTable:
    def __init__(self, *args, **kwargs):
        pass

    def add_data(self, *args, **kwargs):
        pass


def load_model(space: Path, device: str):
    sys.path.insert(0, str(space / "amt" / "src"))
    sys.path.insert(0, str(space))
    # ymt3.py builds a wandb.Table in __init__ to log samples during validation; inference
    # never fills it, so a stand-in saves installing wandb.
    try:
        import wandb  # noqa: F401
    except ImportError:
        stub = types.ModuleType("wandb")
        stub.Table = _NullTable
        sys.modules["wandb"] = stub
    os.chdir(space)  # the checkpoint path resolves relative to amt/logs
    from model_helper import load_model_checkpoint

    return load_model_checkpoint(args=MODEL_ARGS, device="cpu").to(device)


def transcribe(model, audio_path: Path, device: str) -> list[dict]:
    import soundfile as sf
    import torch
    import torchaudio
    from utils.audio import slice_padded_array
    from utils.event2note import merge_zipped_note_events_and_ties_to_notes
    from utils.note2event import mix_notes

    data, sr = sf.read(str(audio_path), dtype="float32", always_2d=True)
    audio = torch.from_numpy(data.mean(axis=1)).unsqueeze(0)
    audio = torchaudio.functional.resample(audio, sr, model.audio_cfg["sample_rate"])
    frames = model.audio_cfg["input_frames"]
    segments = slice_padded_array(audio, frames, frames)
    segments = torch.from_numpy(segments.astype("float32")).to(device).unsqueeze(1)
    with torch.no_grad():
        pred, _ = model.inference_file(bsz=8, audio_segments=segments)
    starts = [frames * i / model.audio_cfg["sample_rate"] for i in range(segments.shape[0])]
    channels = []
    for ch in range(model.task_manager.num_decoding_channels):
        zipped, _, _ = model.task_manager.detokenize_list_batches(
            [arr[:, ch, :] for arr in pred], starts, return_events=True
        )
        notes, _ = merge_zipped_note_events_and_ties_to_notes(zipped)
        channels.append(notes)
    return [
        {"pitch": int(n.pitch), "start": float(n.onset), "end": float(n.offset), "program": int(n.program)}
        for n in mix_notes(channels)
        if not n.is_drum
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", type=Path, required=True)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--prefetch", action="store_true")
    ap.add_argument("--device", default=None)
    ap.add_argument("audio", nargs="?", type=Path)
    ap.add_argument("out_json", nargs="?", type=Path)
    args = ap.parse_args()

    space = fetch(args.home.resolve(), args.revision)
    if args.prefetch:
        return 0
    if args.audio is None or args.out_json is None:
        ap.error("AUDIO and OUT_JSON are required unless --prefetch")
    audio, out = args.audio.resolve(), args.out_json.resolve()
    device = pick_device(args.device)
    t0 = time.monotonic()
    model = load_model(space, device)
    notes = transcribe(model, audio, device)
    out.write_text(
        json.dumps({"notes": notes, "device": device, "seconds": round(time.monotonic() - t0, 2)}),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
