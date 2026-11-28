#!/usr/bin/env python3
"""Measure guitar separation and its effect on the lead/rhythm tabs, through the app's own path.

Every run goes through the web flow: the analysis phase (6-stem separation, vocal suppression,
Lead/Rhythm split) and then the tab job for the lead and rhythm parts. ``--stage1`` picks the
separator that makes the guitar stem the split gets (``ATT_SPLIT_STAGE1``): ``demucs``
(htdemucs_6s, guitar-ft when cached) or ``bs_roformer_sw``.

bandmix
    Band mixes with a known guitar part. Each GuitarSet (CC BY 4.0) comp + solo pair is mixed
    (rhythm = comp, lead = solo, one excerpt per player and genre: 30 clips) over real drums,
    bass and vocals stems from the MUSDB18 7-second sample set (non-commercial research use;
    the ``other`` stem is left out because it often holds guitars). Backing comes from real
    multitracks, not from either separator, so neither is favoured. Reports guitar-stem SI-SDR
    against the true guitar, lead/rhythm/both note F1 and role accuracy against the JAMS notes,
    plus the label-free proxies below. Data roots::

        ~/.cache/audio_to_tab/datasets/guitarset/{annotation,audio_mono-mic}/
        ~/.cache/audio_to_tab/datasets/musdb18_7s/raw/{train,test}/*.stem.mp4
          (https://zenodo.org/records/3270814/files/MUSDB18-7-STEMS.zip)

proxies
    Any songs, no ground truth: % of tab notes outside the guitar's range, notes per second,
    median polyphony at onsets per part, and bass-stem/guitar-stem envelope correlation
    (a bleed indicator).

Usage:
    python scripts/eval_guitar.py bandmix --stage1 demucs --out data/eval_runs/guitar --tag demucs
    python scripts/eval_guitar.py bandmix --stage1 bs_roformer_sw --out data/eval_runs/guitar --tag rofo
    python scripts/eval_guitar.py proxies a.mp3 b.wav --start 30 --end 150 --stage1 bs_roformer_sw \\
        --out data/eval_runs/guitar --tag rofo
    python scripts/eval_guitar.py table data/eval_runs/guitar/demucs.json data/eval_runs/guitar/rofo.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.eval_lead_rhythm import (
    DEFAULT_GUITARSET_ROOT,
    SR,
    _midi_notes,
    _mono,
    eval_config,
    jams_notes,
    mean_of,
    mix_pair,
    role_accuracy,
    select_pairs,
)
from scripts.eval_tabs import note_match_f1

DEFAULT_MUSDB_ROOT = Path.home() / ".cache" / "audio_to_tab" / "datasets" / "musdb18_7s" / "raw"
MUSDB_BACKING_STREAMS = (1, 2, 4)  # stem.mp4 streams: 0 mix, 1 drums, 2 bass, 3 other, 4 vocals
GUITAR_TO_BACKING_DB = -3.0
GUITAR_MIDI_RANGE = (40, 88)  # standard tuning: open low E to the 24th fret of the high E
ENVELOPE_SEC = 0.05
ONSET_GROUP_SEC = 0.05
STAGE1 = {"demucs": "demucs", "bs_roformer_sw": "bs_roformer_sw"}
# (comp position, solo position): -1 hard left, 0 centre. "centre" is GuitarSet as recorded
# (both mono, centred); the other two test the stereo pre-split's convention and its reverse.
LAYOUTS = {
    "centre": (0.0, 0.0),
    "lead_centre_rhythm_left": (-0.8, 0.0),
    "lead_left_rhythm_centre": (0.0, -0.8),
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def si_sdr_db(reference: np.ndarray, estimate: np.ndarray) -> float:
    """Scale-invariant SDR (Le Roux et al., 2019): gain differences don't count as error."""
    n = min(len(reference), len(estimate))
    ref, est = reference[:n].astype(np.float64), estimate[:n].astype(np.float64)
    energy = float(np.dot(ref, ref))
    if energy <= 0:
        return float("nan")
    target = (float(np.dot(est, ref)) / energy) * ref
    noise = est - target
    return round(10.0 * np.log10(float(np.dot(target, target)) / max(float(np.dot(noise, noise)), 1e-12)), 2)


def envelope_correlation(a: np.ndarray, b: np.ndarray, sr: int = SR) -> float | None:
    """Pearson correlation of two signals' 50 ms RMS envelopes."""
    win = int(sr * ENVELOPE_SEC)
    n = min(len(a), len(b)) // win
    if n < 3:
        return None
    ea = np.sqrt((a[: n * win].reshape(n, win) ** 2).mean(axis=1))
    eb = np.sqrt((b[: n * win].reshape(n, win) ** 2).mean(axis=1))
    if ea.std() == 0 or eb.std() == 0:
        return None
    return round(float(np.corrcoef(ea, eb)[0, 1]), 4)


def out_of_range_pct(notes: list[dict]) -> float | None:
    if not notes:
        return None
    low, high = GUITAR_MIDI_RANGE
    return round(100.0 * sum(not low <= n["pitch"] <= high for n in notes) / len(notes), 2)


def median_polyphony(notes: list[dict]) -> float | None:
    """Median number of notes sounding at each onset (onsets within 50 ms are one attack)."""
    if not notes:
        return None
    starts = sorted({round(n["start"] / ONSET_GROUP_SEC) for n in notes})
    counts = [
        sum(n["start"] <= s * ONSET_GROUP_SEC + ONSET_GROUP_SEC / 2 < n["end"] for n in notes)
        for s in starts
    ]
    return float(np.median(counts))


def tab_proxies(lead: list[dict], rhythm: list[dict], duration: float, stems: dict) -> dict:
    both = lead + rhythm
    guitar = _mono(Path(stems["guitar"]))
    bass = _mono(Path(stems["bass"])) if stems.get("bass") else None
    return {
        "out_of_range_pct": out_of_range_pct(both),
        "notes_per_sec": round(len(both) / duration, 3) if duration > 0 else None,
        "lead_polyphony": median_polyphony(lead),
        "rhythm_polyphony": median_polyphony(rhythm),
        "bass_guitar_env_corr": None if bass is None else envelope_correlation(bass, guitar),
    }


# ---------------------------------------------------------------------------
# Running the app's path
# ---------------------------------------------------------------------------


def run_flow(audio: Path, work: Path, *, stage1: str, device: str, fresh: bool,
             start: float = 0.0, end: float | None = None, presplit: bool = False) -> dict:
    """Analysis (cached per clip and stage 1) then the lead + rhythm tab job."""
    from dataclasses import replace

    from audio_to_tab.analysis import ANALYSIS_FILE, load_analysis, run_analysis
    from audio_to_tab.cancel import CancelToken
    from audio_to_tab.guitar_roles_stereo import STEREO_PRESPLIT_ENV
    from audio_to_tab.pipeline import run_pipeline
    from audio_to_tab.roformer import SPLIT_STAGE1_ENV

    os.environ[SPLIT_STAGE1_ENV] = STAGE1[stage1]
    os.environ[STEREO_PRESPLIT_ENV] = "1" if presplit else "0"
    cfg = replace(
        eval_config(),
        demucs_device=device,
        max_duration_sec=None if end is None else end - start,
    )
    analysis_dir = work / "analysis"
    seconds = None
    if not fresh and (analysis_dir / ANALYSIS_FILE).is_file():
        bundle = load_analysis(analysis_dir)
    else:
        shutil.rmtree(analysis_dir, ignore_errors=True)
        t0 = time.monotonic()
        bundle = run_analysis(
            audio_path=audio,
            youtube_url=None,
            analysis_dir=analysis_dir,
            config=cfg,
            source={"kind": "upload", "upload_id": str(audio.resolve())},
            on_progress=None,
            cancel=CancelToken(),
            trim_start_sec=start,
        )
        seconds = round(time.monotonic() - t0, 1)
    if not bundle.lead_rhythm.ok:
        raise SystemExit(f"{work.name}: the Lead/Rhythm split did not run: {bundle.lead_rhythm.reason}")
    meta = json.loads((analysis_dir / ANALYSIS_FILE).read_text(encoding="utf-8"))
    run_dir = work / "run"
    shutil.rmtree(run_dir, ignore_errors=True)
    artifacts = run_pipeline(output_dir=run_dir, config=cfg, analysis=bundle, parts=["lead", "rhythm"])
    return {
        "lead": _midi_notes(artifacts["lead_midi"]),
        "rhythm": _midi_notes(artifacts["rhythm_midi"]),
        "stems": bundle.stems,
        "work_audio": bundle.work_audio,
        "separation": meta.get("separation") or {"model": meta.get("model")},
        "analysis_sec": seconds,
    }


# ---------------------------------------------------------------------------
# Band mixes
# ---------------------------------------------------------------------------


def _decode_stream(mp4: Path, stream: int) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(mp4), "-map", f"0:{stream}",
           "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def backing_tracks(musdb_root: Path) -> list[Path]:
    tracks = sorted(Path(musdb_root).glob("*/*.stem.mp4"))
    if not tracks:
        raise SystemExit(f"MUSDB18 7 s sample not found under {musdb_root} (see the docstring)")
    return tracks


def backing_for(index: int, n: int, tracks: list[Path]) -> tuple[np.ndarray, list[str]]:
    """Stereo drums + bass + vocals, consecutive 7 s excerpts from track ``index`` on, ``n`` samples."""
    parts, names, k = [], [], 0
    while sum(len(p) for p in parts) < n:
        mp4 = tracks[(index * 3 + k) % len(tracks)]
        streams = [_decode_stream(mp4, s) for s in MUSDB_BACKING_STREAMS]
        m = min(len(s) for s in streams)
        parts.append(sum(s[:m] for s in streams))
        names.append(mp4.name.removesuffix(".stem.mp4"))
        k += 1
    return np.concatenate(parts)[:n], names


def _pan(mono: np.ndarray, position: float) -> np.ndarray:
    """Equal-power pan: -1 hard left, 0 centre, +1 hard right."""
    angle = (position + 1.0) * np.pi / 4
    return np.column_stack([mono * np.cos(angle), mono * np.sin(angle)]) * np.sqrt(2.0)


def band_mix(comp: np.ndarray, solo: np.ndarray, backing: np.ndarray, layout: str) -> tuple[np.ndarray, np.ndarray]:
    """Pan comp and solo per ``layout`` over the stereo backing at GUITAR_TO_BACKING_DB.

    Returns (mix, true guitar), both samples x 2.
    """
    comp_pos, solo_pos = LAYOUTS[layout]
    guitar = _pan(comp, comp_pos) + _pan(solo, solo_pos)
    g_rms = float(np.sqrt(np.mean(guitar**2))) or 1.0
    b_rms = float(np.sqrt(np.mean(backing**2))) or 1.0
    g = guitar * (b_rms / g_rms) * 10 ** (GUITAR_TO_BACKING_DB / 20)
    mix = backing + g
    gain = min(1.0, 0.95 / float(np.max(np.abs(mix))))
    return (mix * gain).astype(np.float32), (g * gain).astype(np.float32)


def eval_bandmix(args) -> dict:
    import soundfile as sf

    ann_dir, audio_dir = args.root / "annotation", args.root / "audio_mono-mic"
    if not ann_dir.is_dir() or not audio_dir.is_dir():
        raise SystemExit(f"GuitarSet not found under {args.root} (need annotation/ and audio_mono-mic/)")
    tracks = backing_tracks(args.musdb)
    pairs = select_pairs(ann_dir)[: args.limit or None]
    rows = []
    for k, pair_id in enumerate(pairs):
        mix_dir = args.out / "bandmix" / "mixes"
        mix_dir.mkdir(parents=True, exist_ok=True)
        guitar, comp, solo = mix_pair(
            _mono(audio_dir / f"{pair_id}_comp_mic.wav"), _mono(audio_dir / f"{pair_id}_solo_mic.wav")
        )
        backing, backing_names = backing_for(k, len(guitar), tracks)
        mix, guitar_true = band_mix(comp, solo, backing, args.layout)
        guitar_true = guitar_true.mean(axis=1)
        suffix = "" if args.layout == "centre" else f"_{args.layout}"
        mix_wav = mix_dir / f"{pair_id}{suffix}.wav"
        sf.write(str(mix_wav), mix, SR, subtype="FLOAT")
        run_name = args.stage1 + suffix + ("_presplit" if args.presplit else "")
        work = args.out / "bandmix" / run_name / pair_id
        work.mkdir(parents=True, exist_ok=True)
        res = run_flow(mix_wav, work, stage1=args.stage1, device=args.device, fresh=args.fresh,
                       presplit=args.presplit)
        solo_n = jams_notes(ann_dir / f"{pair_id}_solo.jams")
        comp_n = jams_notes(ann_dir / f"{pair_id}_comp.jams")
        union = note_match_f1(res["lead"] + res["rhythm"], solo_n + comp_n)
        row = {
            "pair": pair_id,
            "backing": backing_names,
            "separation": res["separation"],
            "analysis_sec": res["analysis_sec"],
            "guitar_si_sdr_db": si_sdr_db(guitar_true, _mono(Path(res["stems"]["guitar"]))),
            "lead_f1": note_match_f1(res["lead"], solo_n)["note_f1"],
            "rhythm_f1": note_match_f1(res["rhythm"], comp_n)["note_f1"],
            "union_f1": union["note_f1"],
            "union_recall": union["note_recall"],
            "role_accuracy": role_accuracy(res["lead"], res["rhythm"], solo_n, comp_n),
            **tab_proxies(res["lead"], res["rhythm"], len(guitar) / SR, res["stems"]),
        }
        rows.append(row)
        print(f"[{k + 1}/{len(pairs)}] {json.dumps(row)}", file=sys.stderr, flush=True)
    keys = ("guitar_si_sdr_db", "lead_f1", "rhythm_f1", "union_f1", "union_recall", "role_accuracy",
            "out_of_range_pct", "notes_per_sec", "bass_guitar_env_corr", "analysis_sec")
    used = sorted({r["separation"].get("model") for r in rows})
    return {"mode": "bandmix", "stage1": args.stage1, "layout": args.layout, "presplit": args.presplit,
            "models_used": used, "clips": len(rows),
            "mean": {k: mean_of(rows, k) for k in keys}, "rows": rows}


def eval_proxies(args) -> dict:
    rows = []
    for k, audio in enumerate(args.files, 1):
        audio = Path(audio)
        work = args.out / "proxies" / args.stage1 / audio.stem
        work.mkdir(parents=True, exist_ok=True)
        res = run_flow(audio, work, stage1=args.stage1, device=args.device, fresh=args.fresh,
                       start=args.start, end=args.end)
        duration = len(_mono(Path(res["work_audio"]))) / SR
        row = {"song": audio.stem, "separation": res["separation"], "analysis_sec": res["analysis_sec"],
               **tab_proxies(res["lead"], res["rhythm"], duration, res["stems"])}
        rows.append(row)
        print(f"[{k}/{len(args.files)}] {json.dumps(row, ensure_ascii=False)}", file=sys.stderr, flush=True)
    keys = ("out_of_range_pct", "notes_per_sec", "lead_polyphony", "rhythm_polyphony",
            "bass_guitar_env_corr", "analysis_sec")
    return {"mode": "proxies", "stage1": args.stage1, "songs": len(rows),
            "mean": {k: mean_of(rows, k) for k in keys}, "rows": rows}


def markdown_table(reports: list[dict]) -> str:
    keys = [k for k in reports[0]["mean"] if all(k in r["mean"] for r in reports)]
    lines = ["| run | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for r in reports:
        cells = ["–" if r["mean"][k] is None else f"{r['mean'][k]:g}" for k in keys]
        lines.append(f"| {r.get('tag', r['stage1'])} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    for name in ("bandmix", "proxies"):
        p = sub.add_parser(name)
        p.add_argument("--stage1", choices=sorted(STAGE1), required=True)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--tag", required=True)
        p.add_argument("--device", default="mps")
        p.add_argument("--fresh", action="store_true", help="re-run the analysis even if cached")
        p.add_argument("--presplit", action="store_true", help="ATT_STEREO_PRESPLIT=1 for the split")
        if name == "bandmix":
            p.add_argument("--layout", choices=sorted(LAYOUTS), default="centre")
            p.add_argument("--root", type=Path, default=DEFAULT_GUITARSET_ROOT)
            p.add_argument("--musdb", type=Path, default=DEFAULT_MUSDB_ROOT)
            p.add_argument("--limit", type=int, default=None)
        else:
            p.add_argument("files", nargs="+", type=Path)
            p.add_argument("--start", type=float, default=0.0)
            p.add_argument("--end", type=float, default=None)
    t = sub.add_parser("table")
    t.add_argument("reports", nargs="+", type=Path)
    args = ap.parse_args()

    if args.mode == "table":
        print(markdown_table([json.loads(p.read_text(encoding="utf-8")) for p in args.reports]))
        return
    report = eval_bandmix(args) if args.mode == "bandmix" else eval_proxies(args)
    report["tag"] = args.tag
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.tag}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["mean"], indent=2))
    print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
