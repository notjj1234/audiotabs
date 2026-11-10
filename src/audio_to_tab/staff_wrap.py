"""On-screen ASCII staff wrapping. The .tab download stays unwrapped."""

from __future__ import annotations

import re

_CSI_M_OR_K = re.compile(r"\x1b\[[0-9;?]*[mK]")


def strip_ansi_csi(text: str) -> str:
    """Remove ANSI CSI sequences whose final byte is ``m`` or ``K``."""
    return _CSI_M_OR_K.sub("", text or "")


def _split_body(body: str, room: int) -> list[str]:
    if body == "":
        return [""]
    step = max(1, room)
    return [body[index : index + step] for index in range(0, len(body), step)]


def _wrap_staff(lines: list[str], width: int) -> list[str]:
    if all(len(line) <= width for line in lines):
        return list(lines)
    prefixes: list[str] = []
    bodies: list[str] = []
    for line in lines:
        pipe = line.find("|")
        if pipe < 0:
            prefixes.append("")
            bodies.append(line)
        else:
            prefixes.append(line[: pipe + 1])
            bodies.append(line[pipe + 1 :])
    longest = max((len(body) for body in bodies), default=0)
    padded = [body.ljust(longest, "-") for body in bodies]
    rooms = [max(1, width - len(prefix)) for prefix in prefixes]
    room = min(rooms) if rooms else max(1, width)
    parts = [_split_body(body, room) for body in padded]
    count = max(len(chunks) for chunks in parts)
    rendered: list[str] = []
    for index in range(count):
        if count > 1:
            rendered.append(f"--- Part {index + 1}/{count} ---")
        for prefix, chunks in zip(prefixes, parts, strict=True):
            chunk = chunks[index] if index < len(chunks) else ""
            rendered.append(f"{prefix}{chunk}")
        if index != count - 1:
            rendered.append("")
    return rendered


def wrap_tab_staff(text: str, width: int = 100) -> str:
    """Wrap each six-line staff wider than ``width``. Other lines pass through."""
    cleaned = strip_ansi_csi(text).replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = cleaned.split("\n")
    if raw_lines and raw_lines[-1] == "":
        raw_lines = raw_lines[:-1]
    output: list[str] = []
    index = 0
    while index < len(raw_lines):
        window = raw_lines[index : index + 6]
        if len(window) == 6 and all("|" in line for line in window):
            output.extend(_wrap_staff(window, width))
            index += 6
        else:
            output.append(raw_lines[index])
            index += 1
    rendered = "\n".join(output)
    if cleaned.endswith("\n") or text.endswith("\n"):
        rendered += "\n"
    return rendered
