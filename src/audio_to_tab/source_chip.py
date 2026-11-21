"""Selected-source chip model for the converter card."""

from __future__ import annotations

from audio_to_tab.tab_bundle import format_size_kb


def source_chip(
    *,
    name: str,
    size_bytes: int | None = None,
    duration_sec: float | None = None,
) -> dict:
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("source chip requires a non-empty name")
    chip: dict = {"name": cleaned}
    if size_bytes is not None:
        chip["size_bytes"] = max(0, int(size_bytes))
    if duration_sec is not None:
        chip["duration_sec"] = max(0.0, float(duration_sec))
    return chip


def _clock(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def format_source_chip_caption(chip: dict) -> str:
    bits: list[str] = []
    if "size_bytes" in chip:
        bits.append(format_size_kb(int(chip["size_bytes"])))
    if "duration_sec" in chip:
        bits.append(f"Duration about {_clock(float(chip['duration_sec']))}.")
    return " ".join(bits)
