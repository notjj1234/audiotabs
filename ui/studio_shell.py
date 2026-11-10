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
  <p>Upload a short solo-guitar clip or paste a public YouTube link. Convert locally to tab, chords, MIDI, and PDF.</p>
</div>
"""


def progress_card_html(rows: list[dict[str, str]]) -> str:
    items: list[str] = []
    for row in rows:
        state = str(row.get("state") or "pending")
        word = _STATE_WORDS.get(state, "Waiting")
        label = escape(str(row.get("label") or ""))
        detail = str(row.get("detail") or "").strip()
        detail_html = f" — {escape(detail)}" if detail else ""
        items.append(
            f'<li><span class="state {escape(state)}">{escape(word)}</span>'
            f"<span>{label}{detail_html}</span></li>"
        )
    body = "\n".join(items)
    return f"""
<div class="studio-progress" role="status" aria-live="polite">
  <h3>Transcribing</h3>
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
