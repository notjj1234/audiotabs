"""Checklist rows driven by real pipeline progress events."""

from __future__ import annotations

STAGES: tuple[tuple[str, str], ...] = (
    ("ingest", "Ingest"),
    ("separate", "Separating stems"),
    ("transcribe", "Detecting notes"),
    ("tab", "Mapping tablature"),
    ("chords", "Recognizing chords"),
    ("lyrics", "Extracting lyrics"),
    ("pdf", "Finalizing PDF"),
)


def new_checklist() -> list[dict[str, str]]:
    return [{"id": stage_id, "label": label, "state": "pending", "detail": ""} for stage_id, label in STAGES]


def apply_progress(rows: list[dict[str, str]], stage: str, message: str) -> list[dict[str, str]]:
    """Return a new checklist. Unknown stages, including tempo, do not add a row."""
    updated = [dict(row) for row in rows]
    index = {row["id"]: position for position, row in enumerate(updated)}
    text = message or ""
    if text.startswith("skipped:"):
        if stage in index:
            updated[index[stage]]["state"] = "skipped"
            updated[index[stage]]["detail"] = text.split(":", 1)[1].strip()
        return updated
    if stage == "done":
        for row in updated:
            if row["state"] == "active":
                row["state"] = "done"
            elif row["state"] == "pending":
                row["state"] = "skipped"
                row["detail"] = row["detail"] or "Not reported"
        return updated
    if stage not in index:
        return updated
    position = index[stage]
    for row in updated[:position]:
        if row["state"] == "active":
            row["state"] = "done"
    updated[position]["state"] = "active"
    updated[position]["detail"] = text
    return updated
