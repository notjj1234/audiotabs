"""Post-success “go deeper” action list (feature discovery, not billing)."""

from __future__ import annotations

from pathlib import Path


def depth_banner_actions(
    *,
    artifacts: dict | None,
    details: dict | None,
    has_midi: bool,
) -> list[dict]:
    actions: list[dict] = []
    if has_midi:
        actions.append({"id": "piano_roll", "label": "Open piano roll"})
    if details is not None and not details.get("separate"):
        actions.append({"id": "try_separation", "label": "Try stem separation"})
    raw = (artifacts or {}).get("gp5")
    if raw and Path(str(raw)).is_file():
        actions.append({"id": "guitar_pro", "label": "Export Guitar Pro"})
    return actions


__all__ = ["depth_banner_actions"]
