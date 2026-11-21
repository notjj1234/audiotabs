"""Suggest a capo fret that lands the song in guitar-friendly open keys."""

from __future__ import annotations

from audio_to_tab.chords import PC_NAMES

FRIENDLY_KEYS: frozenset[str] = frozenset(
    {
        "C major",
        "G major",
        "D major",
        "A major",
        "E major",
        "A minor",
        "E minor",
        "D minor",
    }
)

_ROOT_INDEX = {name: index for index, name in enumerate(PC_NAMES)}


def _parse_key(key_name: str) -> tuple[int, str] | None:
    text = (key_name or "").strip()
    if not text or text == "Unknown":
        return None
    parts = text.split()
    if len(parts) != 2:
        return None
    root, quality = parts
    if root not in _ROOT_INDEX or quality not in {"major", "minor"}:
        return None
    return _ROOT_INDEX[root], quality


def suggest_capo_for_key(key_name: str, *, current_capo: int = 0) -> int | None:
    """Lowest capo 1–7 that yields a friendly written key; None if already friendly."""
    if (key_name or "").strip() in FRIENDLY_KEYS:
        return None
    parsed = _parse_key(key_name)
    if parsed is None:
        return None
    root, quality = parsed
    current = int(current_capo)
    for n in range(1, 8):
        if n == current:
            continue
        written = f"{PC_NAMES[(root - n) % 12]} {quality}"
        if written in FRIENDLY_KEYS:
            return n
    return None


__all__ = ["FRIENDLY_KEYS", "suggest_capo_for_key"]
