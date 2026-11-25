#!/usr/bin/env python3
"""Measure lead/rhythm role accuracy and tab accuracy of the lead_rhythm_split mode.

Two kinds of ground truth:

guitarset
    GuitarSet (CC BY 4.0) has a ``comp`` and a ``solo`` take of every excerpt. Each pair is
    mixed into one two-guitar clip: rhythm = comp, lead = solo, notes from the JAMS
    ``note_midi`` annotations. One excerpt per player and genre is used (30 clips).

labels
    Your own songs with hand-marked sections, one JSON file per song (keep them in
    ``data/eval_labels/``, which git ignores)::

        {"audio": "path/to/song.mp3", "start": 120.0, "end": 240.0,
         "sections": [{"start": 120.0, "end": 151.5, "lead": false},
                      {"start": 151.5, "end": 180.0, "lead": true}]}

    Times are song seconds; ``start``/``end`` pick the clip (at most the split's length
    cap). ``lead`` is true when a lead line (solo, fill, melody) plays in that section.
    Besides the scores against the labels, each song reports label-free proxies (lead-share
    spread and changes per minute, notes left out of the rhythm part, vocal residue in Lead).

Both modes measure production code: ``guitarset`` runs the lead/rhythm stage
(``pipeline._run_lead_rhythm_stage``) on its two-guitar mixes; ``labels`` runs the app's own
path, the analysis phase (separation, vocal suppression, split) and then the tab job. Splits
and analyses are cached per clip under ``--out`` because fixes to transcription and roles don't
change them; pass ``--fresh-split`` after changing anything that feeds the splitter.

Usage:
    python scripts/eval_lead_rhythm.py guitarset --out /tmp/lr_eval --tag baseline
    python scripts/eval_lead_rhythm.py labels data/eval_labels/*.json --out /tmp/lr_eval --tag baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.eval_tabs import note_match_f1

DEFAULT_GUITARSET_ROOT = Path.home() / ".cache" / "audio_to_tab" / "datasets" / "guitarset"
SR = 44100
WINDOW_SEC = 1.0
LEAD_SHARE_THRESHOLD = 0.5
_PAIR_ID = re.compile(r"^(?P<player>\d+)_(?P<genre>[A-Za-z]+)\d+-.+$")


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------


def jams_notes(path: Path) -> list[dict]:
    """All ``note_midi`` notes of a GuitarSet JAMS file (six strings merged)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    notes = []
    for ann in data.get("annotations", []):
        if ann.get("namespace") != "note_midi":
            continue
        for obs in ann.get("data", []):
            start = float(obs["time"])
            notes.append(
                {
                    "pitch": round(float(obs["value"])),
                    "start": start,
                    "end": start + float(obs["duration"]),
                }
            )
    return sorted(notes, key=lambda n: (n["start"], n["pitch"]))


def select_pairs(annotation_dir: Path, per_player_genre: int = 1) -> list[str]:
    """Excerpt ids with both a comp and a solo take, ``per_player_genre`` per (player, genre)."""
    names = {p.stem for p in Path(annotation_dir).glob("*.jams")}
    ids = sorted(
        n[: -len("_comp")] for n in names if n.endswith("_comp") and f"{n[: -len('_comp')]}_solo" in names
    )
    taken: dict[tuple[str, str], int] = {}
    picked = []
    for pair_id in ids:
        m = _PAIR_ID.match(pair_id)
        if not m:
            continue
        key = (m["player"], m["genre"])
        if taken.get(key, 0) < per_player_genre:
            taken[key] = taken.get(key, 0) + 1
            picked.append(pair_id)
    return picked


def mix_pair(comp: np.ndarray, solo: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sum two mono takes at their recorded levels; one shared gain keeps the stems additive."""
    n = min(len(comp), len(solo))
    comp, solo = comp[:n].astype(np.float32), solo[:n].astype(np.float32)
    mix = comp + solo
    peak = float(np.max(np.abs(mix))) if n else 0.0
    gain = 0.95 / peak if peak > 0.95 else 1.0
    return mix * gain, comp * gain, solo * gain


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def role_accuracy(lead: list[dict], rhythm: list[dict], solo: list[dict], comp: list[dict]) -> float | None:
    """Of the notes transcribed correctly regardless of stem, the share filed in the right stem."""
    agnostic = note_match_f1(lead + rhythm, solo + comp)["matched"]
    if agnostic == 0:
        return None
    in_place = note_match_f1(lead, solo)["matched"] + note_match_f1(rhythm, comp)["matched"]
    return round(min(1.0, in_place / agnostic), 4)


def sdr_db(reference: np.ndarray, estimate: np.ndarray) -> float:
    n = min(len(reference), len(estimate))
    ref, est = reference[:n].astype(np.float64), estimate[:n].astype(np.float64)
    noise = float(np.sum((ref - est) ** 2))
    signal = float(np.sum(ref**2))
    if signal <= 0:
        return float("nan")
    return round(10.0 * np.log10(signal / max(noise, 1e-12)), 2)


def window_lead_share(lead: np.ndarray, rhythm: np.ndarray, sr: int = SR) -> tuple[np.ndarray, np.ndarray]:
    """Per-second lead share E_lead / (E_lead + E_rhythm) and an 'audible' mask (> max − 40 dB)."""
    win = int(sr * WINDOW_SEC)
    n = min(len(lead), len(rhythm)) // win
    el = (lead[: n * win].reshape(n, win) ** 2).sum(axis=1)
    er = (rhythm[: n * win].reshape(n, win) ** 2).sum(axis=1)
    total = el + er
    audible = total > (total.max() * 1e-4 if n else 0.0)
    return el / np.maximum(total, 1e-12), audible


def section_labels(sections: list[dict], clip_start: float, n_windows: int) -> np.ndarray:
    """Per-window label: 1 lead, 0 no lead, -1 unlabelled (window centre outside every section)."""
    out = np.full(n_windows, -1, dtype=int)
    for i in range(n_windows):
        t = clip_start + (i + 0.5) * WINDOW_SEC
        for sec in sections:
            if float(sec["start"]) <= t < float(sec["end"]):
                out[i] = 1 if sec["lead"] else 0
                break
    return out


def balanced_accuracy(pred: np.ndarray, truth: np.ndarray) -> float | None:
    rates = []
    for cls in (0, 1):
        sel = truth == cls
        if sel.any():
            rates.append(float(np.mean(pred[sel] == cls)))
    return round(float(np.mean(rates)), 4) if len(rates) == 2 else None


def changes_per_min(pred: np.ndarray) -> float:
    if len(pred) < 2:
        return 0.0
    return round(60.0 * float(np.sum(pred[1:] != pred[:-1])) / (len(pred) * WINDOW_SEC), 2)


def labelled_window_metrics(
    share: np.ndarray, audible: np.ndarray, lead_onsets: list[float], labels: np.ndarray, clip_start: float
) -> dict:
    """Audio (lead share) and tab (lead notes present) agreement with the hand labels."""
    sel = (labels >= 0) & audible
    truth = labels[sel]
    audio_pred = (share[sel] >= LEAD_SHARE_THRESHOLD).astype(int)
    counts = np.zeros(len(labels), dtype=int)
    for t in lead_onsets:
        i = int((t - clip_start) // WINDOW_SEC)
        if 0 <= i < len(counts):
            counts[i] += 1
    tab_pred = (counts[sel] > 0).astype(int)

    def mean_or_none(x: np.ndarray) -> float | None:
        return round(float(np.mean(x)), 4) if x.size else None

    return {
        "windows": int(sel.sum()),
        "audio_balanced_acc": balanced_accuracy(audio_pred, truth),
        "audio_lead_share_in_lead": mean_or_none(share[sel][truth == 1]),
        "audio_lead_share_in_no_lead": mean_or_none(share[sel][truth == 0]),
        "audio_changes_per_min": changes_per_min(audio_pred),
        "tab_balanced_acc": balanced_accuracy(tab_pred, truth),
        "tab_lead_notes_per_s_in_lead": mean_or_none(counts[sel][truth == 1] / WINDOW_SEC),
        "tab_lead_notes_per_s_in_no_lead": mean_or_none(counts[sel][truth == 0] / WINDOW_SEC),
    }


def mean_of(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float)) and np.isfinite(r[key])]
    return round(float(np.mean(vals)), 4) if vals else None


# ---------------------------------------------------------------------------
# Running the pipeline stage
# ---------------------------------------------------------------------------


def _mono(path: Path) -> np.ndarray:
    import soundfile as sf

    data, sr = sf.read(str(path), always_2d=True)
    if sr != SR:
        raise RuntimeError(f"{path} is {sr} Hz; expected {SR} Hz")
    return data.mean(axis=1)


def _midi_notes(path: Path) -> list[dict]:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(path))
    return [
        {"pitch": int(n.pitch), "start": float(n.start), "end": float(n.end)}
        for inst in pm.instruments
        for n in inst.notes
    ]


def eval_config():
    """The web flow's settings for the stage: split on, stems separated (mix-aware floors on)."""
    from audio_to_tab.pipeline import PipelineConfig

    return PipelineConfig(
        separate_stems=True,
        lead_rhythm_split=True,
        model="lead_rhythm_split",
        export_gp5=False,
    )


def run_stage(guitar_wav: Path, work: Path, *, device: str, fresh_split: bool) -> dict:
    """Split (cached) + the real lead/rhythm stage; returns final notes and stem paths."""
    from audio_to_tab import lead_rhythm_sep
    from audio_to_tab.isolate import probe_duration_sec
    from audio_to_tab.pipeline import _run_lead_rhythm_stage

    split_dir = work / "split"
    lead_wav, rhythm_wav = split_dir / "lead_guitar.wav", split_dir / "rhythm_guitar.wav"
    if fresh_split or not (lead_wav.is_file() and rhythm_wav.is_file()):
        lead_rhythm_sep.run_lead_rhythm_split(guitar_wav, split_dir, device=device)
    out_dir = work / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        _run_lead_rhythm_stage(
            cfg=eval_config(),
            transcribe_input=guitar_wav,
            tempo_audio_source=guitar_wav,
            output_dir=out_dir,
            tmp_path=Path(tmp),
            progress=lambda *_a, **_k: None,
            duration_sec=float(probe_duration_sec(guitar_wav) or 0.0),
            playback_path=guitar_wav,
            split_paths={"lead": lead_wav, "rhythm": rhythm_wav},
        )
    return {
        "lead": _midi_notes(out_dir / "lead.mid"),
        "rhythm": _midi_notes(out_dir / "rhythm.mid"),
        "lead_wav": lead_wav,
        "rhythm_wav": rhythm_wav,
    }


def eval_guitarset(root: Path, out: Path, *, device: str, fresh_split: bool, limit: int | None) -> dict:
    import soundfile as sf

    ann_dir, audio_dir = root / "annotation", root / "audio_mono-mic"
    if not ann_dir.is_dir() or not audio_dir.is_dir():
        raise SystemExit(f"GuitarSet not found under {root} (need annotation/ and audio_mono-mic/)")
    pairs = select_pairs(ann_dir)[: limit or None]
    rows = []
    for k, pair_id in enumerate(pairs, 1):
        work = out / "guitarset" / pair_id
        work.mkdir(parents=True, exist_ok=True)
        mix_wav = work / "mix.wav"
        mix, comp, solo = mix_pair(
            _mono(audio_dir / f"{pair_id}_comp_mic.wav"), _mono(audio_dir / f"{pair_id}_solo_mic.wav")
        )
        sf.write(str(mix_wav), mix, SR, subtype="PCM_16")
        res = run_stage(mix_wav, work, device=device, fresh_split=fresh_split)
        solo_n, comp_n = jams_notes(ann_dir / f"{pair_id}_solo.jams"), jams_notes(ann_dir / f"{pair_id}_comp.jams")
        lead_audio, rhythm_audio = _mono(res["lead_wav"]), _mono(res["rhythm_wav"])
        union = note_match_f1(res["lead"] + res["rhythm"], solo_n + comp_n)
        row = {
            "pair": pair_id,
            "lead_f1": note_match_f1(res["lead"], solo_n)["note_f1"],
            "rhythm_f1": note_match_f1(res["rhythm"], comp_n)["note_f1"],
            "union_f1": union["note_f1"],
            "union_recall": union["note_recall"],
            "role_accuracy": role_accuracy(res["lead"], res["rhythm"], solo_n, comp_n),
            "lead_sdr_db": sdr_db(solo, lead_audio),
            "rhythm_sdr_db": sdr_db(comp, rhythm_audio),
            "lead_notes": len(res["lead"]),
            "rhythm_notes": len(res["rhythm"]),
        }
        rows.append(row)
        print(f"[{k}/{len(pairs)}] {json.dumps(row)}", file=sys.stderr, flush=True)
    keys = ("lead_f1", "rhythm_f1", "union_f1", "union_recall", "role_accuracy", "lead_sdr_db", "rhythm_sdr_db")
    return {"mode": "guitarset", "clips": len(rows), "mean": {k: mean_of(rows, k) for k in keys}, "rows": rows}


def run_web_flow(spec: dict, work: Path, *, device: str, fresh_split: bool) -> dict:
    """The app's own path: analysis (separation, vocal suppression, split; cached) then the tab job."""
    import shutil
    from dataclasses import replace

    from audio_to_tab.analysis import (
        ANALYSIS_FILE,
        analysis_fingerprint,
        load_analysis,
        run_analysis,
    )
    from audio_to_tab.cancel import CancelToken
    from audio_to_tab.pipeline import run_pipeline

    start, end = float(spec["start"]), float(spec["end"])
    cfg = replace(eval_config(), max_duration_sec=end - start, demucs_device=device)
    source = {"kind": "upload", "upload_id": str(Path(spec["audio"]).resolve())}
    analysis_dir = work / "analysis"
    bundle = None
    if not fresh_split and (analysis_dir / ANALYSIS_FILE).is_file():
        bundle = load_analysis(analysis_dir)
        if bundle.fingerprint != analysis_fingerprint(source, cfg, start):
            bundle = None  # another clip (audio, start or end changed): analyse again
    if bundle is None:
        shutil.rmtree(analysis_dir, ignore_errors=True)
        bundle = run_analysis(
            audio_path=Path(spec["audio"]),
            youtube_url=None,
            analysis_dir=analysis_dir,
            config=cfg,
            source=source,
            on_progress=None,
            cancel=CancelToken(),
            trim_start_sec=start,
        )
    if not bundle.lead_rhythm.ok:
        raise SystemExit(f"{work.name}: the Lead/Rhythm split did not run: {bundle.lead_rhythm.reason}")
    run_dir = work / "run"
    shutil.rmtree(run_dir, ignore_errors=True)
    artifacts = run_pipeline(output_dir=run_dir, config=cfg, analysis=bundle, parts=["lead", "rhythm"])
    return {
        "lead": _midi_notes(artifacts["lead_midi"]),
        "lead_wav": artifacts["lead_guitar"],
        "rhythm_wav": artifacts["rhythm_guitar"],
        "vocals": bundle.stems.get("vocals"),
        "notes_json": json.loads(Path(artifacts["lead_rhythm_notes"]).read_text(encoding="utf-8")),
        "split_json": json.loads(
            Path(artifacts["lead_rhythm_split_diagnostics"]).read_text(encoding="utf-8")
        ),
    }


def song_proxies(res: dict, share: np.ndarray, audible: np.ndarray) -> dict:
    """Ground-truth-free numbers tracked across changes (see docs/lead-rhythm-split.md)."""
    from audio_to_tab.vocal_debleed import DebleedFeatures

    labels = np.where(share >= 0.65, "L", np.where(share < 0.35, "R", "M"))[audible]
    out = {
        "audible_windows": int(audible.sum()),
        "lead_share_L_R_M_pct": [round(100 * float(np.mean(labels == x)), 1) for x in "LRM"]
        if labels.size
        else None,
        "lead_share_changes_per_min": changes_per_min(labels) if labels.size else None,
        "lead_owned_left_out": (res["notes_json"].get("rhythm_source") or {}).get("lead_owned_left_out"),
        "vocal_suppression": res["split_json"].get("vocal_suppression"),
    }
    if res["vocals"] is not None and Path(res["vocals"]).is_file():
        gain = DebleedFeatures.from_audio(Path(res["lead_wav"]), Path(res["vocals"])).bleed_gain
        out["vocal_residue_in_lead"] = None if gain is None else round(float(gain), 4)
    return out


def eval_labels(label_files: list[Path], out: Path, *, device: str, fresh_split: bool) -> dict:
    rows = []
    for path in label_files:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        start = float(spec["start"])
        work = out / "labels" / Path(path).stem
        work.mkdir(parents=True, exist_ok=True)
        res = run_web_flow(spec, work, device=device, fresh_split=fresh_split)
        share, audible = window_lead_share(_mono(res["lead_wav"]), _mono(res["rhythm_wav"]))
        labels = section_labels(spec["sections"], start, len(share))
        row = {"song": Path(path).stem}
        row.update(labelled_window_metrics(share, audible, [start + n["start"] for n in res["lead"]], labels, start))
        row["proxies"] = song_proxies(res, share, audible)
        rows.append(row)
        print(json.dumps(row), file=sys.stderr, flush=True)
    keys = ("audio_balanced_acc", "audio_changes_per_min", "tab_balanced_acc")
    return {"mode": "labels", "songs": len(rows), "mean": {k: mean_of(rows, k) for k in keys}, "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    gs = sub.add_parser("guitarset")
    gs.add_argument("--root", type=Path, default=DEFAULT_GUITARSET_ROOT)
    gs.add_argument("--limit", type=int, default=None)
    lb = sub.add_parser("labels")
    lb.add_argument("files", type=Path, nargs="+")
    for p in (gs, lb):
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--tag", default="run")
        p.add_argument("--device", default="mps")
        p.add_argument("--fresh-split", action="store_true")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    if args.mode == "guitarset":
        report = eval_guitarset(args.root, args.out, device=args.device, fresh_split=args.fresh_split, limit=args.limit)
    else:
        report = eval_labels(args.files, args.out, device=args.device, fresh_split=args.fresh_split)
    report["tag"] = args.tag
    report_path = args.out / f"{args.mode}_{args.tag}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "mean": report["mean"]}, indent=2))


if __name__ == "__main__":
    main()
