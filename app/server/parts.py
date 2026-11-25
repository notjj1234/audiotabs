"""Part registry: which tracks a run can show and where each one's files live.

Runs made through the instrument picker record ``details.parts``; older runs
don't, and fall back to the original Lead / Rhythm / Combined detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .store import RunRecord

GUITAR_PARTS = ("lead", "rhythm", "combined")


@dataclass(frozen=True)
class PartSpec:
    id: str
    label: str
    kind: str  # "tab" | "staff" | "drums"
    midi_key: str
    result_key: str
    audio_key: str


REGISTRY: dict[str, PartSpec] = {
    spec.id: spec
    for spec in (
        PartSpec("lead", "Lead guitar", "tab", "lead_midi", "lead_result", "lead_guitar"),
        PartSpec("rhythm", "Rhythm guitar", "tab", "rhythm_midi", "rhythm_result", "rhythm_guitar"),
        PartSpec("combined", "Combined guitar", "tab", "midi", "result", "guitar_stem"),
        PartSpec("bass", "Bass", "tab", "bass_midi", "bass_result", "bass_stem"),
        PartSpec("vocals", "Vocals", "staff", "vocals_midi", "vocals_result", "vocals_stem"),
        PartSpec("keys", "Piano / keys", "staff", "keys_midi", "keys_result", "piano_stem"),
        PartSpec("drums", "Drums (rough)", "drums", "drums_midi", "drums_result", "drums_stem"),
        PartSpec("other", "Other instruments", "staff", "other_midi", "other_result", "other_stem"),
    )
}


def _is_file(record: RunRecord, key: str) -> bool:
    path = record.artifacts.get(key)
    return path is not None and Path(path).is_file()


def part_has_data(record: RunRecord, part: str) -> bool:
    spec = REGISTRY.get(part)
    if spec is None:
        return False
    if part in GUITAR_PARTS:
        return _is_file(record, spec.midi_key)
    return _is_file(record, spec.result_key)


def run_parts(record: RunRecord) -> list[str] | None:
    """Parts recorded by the picker flow, in order; None for legacy runs."""
    raw = (record.details or {}).get("parts")
    if not isinstance(raw, list):
        return None
    empty = (record.details or {}).get("empty_parts") or {}
    parts = [
        p
        for p in dict.fromkeys(str(x) for x in raw)
        if p in REGISTRY and (part_has_data(record, p) or p in empty)
    ]
    return parts or None


def legacy_available_parts(record: RunRecord) -> list[str]:
    """Ordered part ids present for a legacy run (always includes combined)."""
    parts: list[str] = []
    for part in ("lead", "rhythm"):
        if _is_file(record, f"{part}_midi") and _is_file(record, f"{part}_result"):
            parts.append(part)
    parts.append("combined")
    return parts


def available_parts(record: RunRecord) -> list[str]:
    generic = run_parts(record)
    return generic if generic is not None else legacy_available_parts(record)


def part_label(part: str) -> str:
    spec = REGISTRY.get(part)
    return spec.label if spec else part.title()
