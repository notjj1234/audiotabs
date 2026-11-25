"""Which instruments a separated song contains, and which parts can be tabbed.

The picker shows one row per ``PartCandidate``. Guitar rows follow the real
Lead/Rhythm split outcome so the UI never preselects the same performance twice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from audio_to_tab.isolate import StemPresence

TabKind = Literal["tab", "staff", "drums"]

UNDETECTED_NOTE = "Barely audible, may produce few notes."
CLEAR_SHARE = 0.15

# id, label, family, source stem, tab kind, checked when detected
_NON_GUITAR: tuple[tuple[str, str, str, str, TabKind, bool], ...] = (
    ("bass", "Bass", "bass", "bass", "tab", True),
    ("vocals", "Vocals", "vocals", "vocals", "staff", True),
    ("keys", "Piano / keys", "keys", "piano", "staff", True),
    ("drums", "Drums (rough)", "drums", "drums", "drums", True),
    ("other", "Other instruments", "other", "other", "staff", False),
)


@dataclass
class LeadRhythmOutcome:
    ok: bool
    reason: str | None
    presence: dict[str, StemPresence] = field(default_factory=dict)
    # True when the user turned the split off (a choice, not a failure).
    skipped: bool = False


@dataclass
class PartCandidate:
    id: str
    label: str
    family: str
    stem: str
    detected: bool
    confidence: float
    reason: str
    tabbable: bool
    tab_kind: TabKind
    default_selected: bool
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PartCandidate:
        return cls(**{k: raw.get(k) for k in cls.__dataclass_fields__})


def presence_reason_text(p: StemPresence) -> str:
    pct = round(max(0.0, float(p.energy_share)) * 100)
    if not p.present:
        return "Barely audible: likely not in this song"
    if p.energy_share >= CLEAR_SHARE:
        return f"Clearly present: about {pct}% of the mix"
    return f"Present but quiet: about {pct}% of the mix"


def _row(
    id_: str,
    label: str,
    family: str,
    stem: str,
    kind: TabKind,
    presence: StemPresence,
    *,
    checked_if_detected: bool,
    note: str | None = None,
) -> PartCandidate:
    detected = bool(presence.present)
    return PartCandidate(
        id=id_,
        label=label,
        family=family,
        stem=stem,
        detected=detected,
        confidence=round(float(presence.confidence), 3),
        reason=presence_reason_text(presence),
        tabbable=True,
        tab_kind=kind,
        default_selected=detected and checked_if_detected,
        note=note if note is not None else (None if detected else UNDETECTED_NOTE),
    )


def build_inventory(
    presence: dict[str, StemPresence], *, lead_rhythm: LeadRhythmOutcome
) -> list[PartCandidate]:
    """Guitar rows first (Lead, Rhythm, Combined), then the other stems present."""
    rows: list[PartCandidate] = []
    guitar = presence.get("guitar")
    if guitar is not None:
        # Lead and Rhythm are always listed. Without a split there is no audio
        # for them, so they are shown but can't be tabbed.
        for part, label in (("lead", "Lead guitar"), ("rhythm", "Rhythm guitar")):
            row = _row(
                part,
                label,
                "guitar",
                f"{part}_guitar",
                "tab",
                lead_rhythm.presence.get(part, guitar),
                checked_if_detected=True,
            )
            row.default_selected = lead_rhythm.ok
            if not lead_rhythm.ok:
                row.tabbable = row.detected = False
                row.note = ""
            rows.append(row)
        if lead_rhythm.ok:
            rows.append(
                _row(
                    "combined",
                    "Combined guitar",
                    "guitar",
                    "guitar",
                    "tab",
                    guitar,
                    checked_if_detected=False,
                    note="One tab of everything the guitars play.",
                )
            )
        else:
            reason = (lead_rhythm.reason or "").strip()
            if lead_rhythm.skipped:
                note = f"One tab for all guitars. {reason}".strip()
            elif reason:
                note = f"Lead and Rhythm couldn't be separated: {reason}"
            else:
                note = "Lead and Rhythm couldn't be separated, so the guitars share one tab."
            rows.append(
                _row(
                    "combined",
                    "Combined guitar",
                    "guitar",
                    "guitar",
                    "tab",
                    guitar,
                    checked_if_detected=True,
                    note=note,
                )
            )
    for id_, label, family, stem, kind, checked in _NON_GUITAR:
        stem_presence = presence.get(stem)
        if stem_presence is None:
            continue
        rows.append(
            _row(id_, label, family, stem, kind, stem_presence, checked_if_detected=checked)
        )
    return rows
