"""Non-interactive HTML chrome for the studio shell."""

from __future__ import annotations

from html import escape

_STATE_WORDS = {
    "done": "Done",
    "active": "Working",
    "skipped": "Skipped",
    "pending": "Waiting",
}


def hero_html() -> str:
    return """
<div class="studio-hero">
  <h1>Tab PDF</h1>
</div>
"""


def progress_card_html(rows: list[dict[str, str]]) -> str:
    items: list[str] = []
    active_label = ""
    finished = 0
    for row in rows:
        state = str(row.get("state") or "pending")
        word = _STATE_WORDS.get(state, "Waiting")
        label = escape(str(row.get("label") or ""))
        detail = str(row.get("detail") or "").strip()
        detail_html = f" — {escape(detail)}" if detail else ""
        if state == "active" and not active_label:
            active_label = str(row.get("label") or "Transcribing")
        if state in {"done", "skipped"}:
            finished += 1
        items.append(
            f'<li class="{escape(state)}">'
            f'<span class="mark" aria-hidden="true"></span>'
            f'<span class="label">{label}{detail_html}</span>'
            f'<span class="state {escape(state)}">{escape(word)}</span>'
            f"</li>"
        )
    total = max(len(rows), 1)
    working = any(str(row.get("state") or "") == "active" for row in rows)
    ratio = (finished + (0.45 if working else 0.0)) / total
    percent = max(0, min(100, round(ratio * 100)))
    if active_label:
        heading = active_label
    elif rows and finished == len(rows):
        heading = "Ready"
    else:
        heading = "Transcribing"
    body = "\n".join(items)
    return f"""
<div class="studio-progress" role="status" aria-live="polite">
  <div class="head">
    <span class="pct">{percent}%</span>
    <h3>{escape(heading)}</h3>
  </div>
  <div class="studio-progress-bar" role="progressbar" aria-valuenow="{percent}" aria-valuemin="0" aria-valuemax="100">
    <span style="width:{percent}%"></span>
  </div>
  <ul>
{body}
  </ul>
</div>
"""


def result_header_html(title: str, *, key: str, tempo: str, duration: str) -> str:
    return f"""
<div class="studio-result-header">
  <h2>{escape(title)}</h2>
  <div class="studio-result-meta">
    <span>Key <strong>{escape(key)}</strong></span>
    <span>Tempo <strong>{escape(tempo)}</strong></span>
    <span>Duration <strong>{escape(duration)}</strong></span>
  </div>
</div>
"""
