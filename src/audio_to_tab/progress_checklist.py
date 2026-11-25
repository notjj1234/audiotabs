"""Checklist rows driven by real pipeline progress events."""

from __future__ import annotations

STAGES: tuple[tuple[str, str], ...] = (
    ("ingest", "Loading audio"),
    ("separate", "Separating stems"),
    ("transcribe", "Detecting notes"),
    ("tab", "Mapping tablature"),
    ("chords", "Recognizing chords"),
    ("lyrics", "Extracting lyrics"),
    ("pdf", "Finalizing PDF"),
)

ANALYSIS_STAGES: tuple[tuple[str, str], ...] = (
    ("ingest", "Getting the audio"),
    ("separate", "Separating instruments"),
    ("split", "Splitting lead and rhythm guitar"),
    ("detect", "Checking which instruments play"),
)

# Heavier weight on long stages so the bar reflects wall time better.
STAGE_WEIGHTS: dict[str, float] = {
    "ingest": 1.0,
    "separate": 4.0,
    "transcribe": 2.0,
    "tab": 1.0,
    "chords": 1.0,
    "lyrics": 0.5,
    "pdf": 0.5,
}

_DEFAULT_ACTIVE_FRACTION = 0.05


def new_checklist() -> list[dict[str, str]]:
    return [
        {"id": stage_id, "label": label, "state": "pending", "detail": "", "fraction": ""}
        for stage_id, label in STAGES
    ]


def new_analysis_checklist() -> list[dict[str, str]]:
    return [
        {"id": stage_id, "label": label, "state": "pending", "detail": "", "fraction": ""}
        for stage_id, label in ANALYSIS_STAGES
    ]


def apply_progress(
    rows: list[dict[str, str]],
    stage: str,
    message: str,
    fraction: float | None = None,
) -> list[dict[str, str]]:
    """Return a new checklist. Unknown stages, including tempo, do not add a row."""
    updated = [dict(row) for row in rows]
    index = {row["id"]: position for position, row in enumerate(updated)}
    text = message or ""
    if text.startswith("skipped:"):
        if stage in index:
            updated[index[stage]]["state"] = "skipped"
            updated[index[stage]]["detail"] = text.split(":", 1)[1].strip()
            updated[index[stage]]["fraction"] = ""
        return updated
    if stage == "done":
        for row in updated:
            if row["state"] == "active":
                row["state"] = "done"
                row["fraction"] = ""
            elif row["state"] == "pending":
                row["state"] = "skipped"
                row["detail"] = row["detail"] or ""
                row["fraction"] = ""
        return updated
    if stage not in index:
        return updated
    position = index[stage]
    for row in updated[:position]:
        if row["state"] == "active":
            row["state"] = "done"
            row["fraction"] = ""
    updated[position]["state"] = "active"
    updated[position]["detail"] = text
    if fraction is None:
        existing = str(updated[position].get("fraction") or "").strip()
        if not existing:
            updated[position]["fraction"] = str(_DEFAULT_ACTIVE_FRACTION)
    else:
        clamped = max(0.0, min(1.0, float(fraction)))
        updated[position]["fraction"] = str(clamped)
    return updated
