"""Non-interactive HTML chrome for the studio shell."""

from __future__ import annotations

from html import escape

_STATE_WORDS = {
    "done": "Done",
    "active": "Working",
    "skipped": "Skipped",
    "pending": "Waiting",
}


def hero_html(*, icon_data_uri: str | None = None) -> str:
    icon = ""
    if icon_data_uri:
        icon = (
            f'<img class="studio-hero-icon" src="{escape(icon_data_uri, quote=True)}" '
            'alt="" width="72" height="72">'
        )
    return f"""
<div class="studio-hero">
  {icon}
  <div class="studio-hero-title">Tab PDF</div>
</div>
"""


def progress_card_html(
    rows: list[dict[str, str]],
    *,
    elapsed_sec: float | None = None,
    tip: str | None = None,
) -> str:
    from audio_to_tab.progress_checklist import STAGE_WEIGHTS
    from audio_to_tab.progress_tips import format_elapsed

    items: list[str] = []
    active_label = ""
    finished_count = 0
    finished_weight = 0.0
    active_weight = 0.0
    active_fraction = 0.0
    total_weight = 0.0
    for row in rows:
        state = str(row.get("state") or "pending")
        word = _STATE_WORDS.get(state, "Waiting")
        raw_label = str(row.get("label") or "")
        label = escape(raw_label)
        detail = str(row.get("detail") or "").strip()
        if detail and detail.casefold() != raw_label.casefold():
            detail_html = f" — {escape(detail)}"
        else:
            detail_html = ""
        stage_id = str(row.get("id") or "")
        weight = float(STAGE_WEIGHTS.get(stage_id, 1.0))
        total_weight += weight
        if state == "active" and not active_label:
            active_label = raw_label or "Transcribing"
            active_weight = weight
            try:
                active_fraction = max(0.0, min(1.0, float(row.get("fraction") or 0.05)))
            except (TypeError, ValueError):
                active_fraction = 0.05
        if state in {"done", "skipped"}:
            finished_count += 1
            finished_weight += weight
        items.append(
            f'<li class="{escape(state)}">'
            f'<span class="mark" aria-hidden="true"></span>'
            f'<span class="label">{label}{detail_html}</span>'
            f'<span class="state {escape(state)}">{escape(word)}</span>'
            f"</li>"
        )
    total_weight = max(total_weight, 1.0)
    ratio = (finished_weight + active_weight * active_fraction) / total_weight
    percent = max(0, min(100, round(ratio * 100)))
    if active_label:
        heading = active_label
    elif rows and finished_count == len(rows):
        heading = "Ready"
        percent = 100
    else:
        heading = "Transcribing"
    elapsed_html = ""
    if elapsed_sec is not None:
        elapsed_html = (
            f'<span class="studio-progress-elapsed">Elapsed {escape(format_elapsed(elapsed_sec))}</span>'
        )
    tip_text = str(tip or "").strip()
    tip_html = (
        f'<p class="studio-progress-tip">{escape(tip_text)}</p>' if tip_text else ""
    )
    body = "\n".join(items)
    return f"""
<div class="studio-progress" role="status" aria-live="polite">
  <div class="head">
    <span class="pct">{percent}%</span>
    <h3>{escape(heading)}</h3>
    {elapsed_html}
  </div>
  <div class="studio-progress-bar" role="progressbar" aria-valuenow="{percent}" aria-valuemin="0" aria-valuemax="100">
    <span style="width:{percent}%"></span>
  </div>
  {tip_html}
  <ul>
{body}
  </ul>
</div>
"""


def depth_banner_html(actions: list[dict]) -> str:
    if not actions:
        return ""
    items = "".join(
        f'<li>{escape(str(item.get("label") or item.get("id") or ""))}</li>'
        for item in actions
    )
    return f"""
<div class="studio-depth-banner">
  <div class="studio-depth-banner-title">Go deeper</div>
  <p class="studio-depth-banner-copy">Explore views and exports that prove the tab.</p>
  <ul class="studio-depth-banner-list">{items}</ul>
</div>
"""


def result_header_html(
    title: str,
    *,
    key: str,
    tempo: str,
    duration: str,
    confidence: str | None = None,
    notes: str | None = None,
    technical: str | None = None,
) -> str:
    key_span = f"<span>Key <strong>{escape(key)}</strong></span>" if key else ""
    confidence_span = (
        f"<span>Confidence <strong>{escape(confidence)}</strong></span>" if confidence else ""
    )
    notes_html = f'<p class="studio-result-notes">{escape(notes)}</p>' if notes else ""
    technical_html = (
        f'<p class="studio-result-technical">{escape(technical)}</p>' if technical else ""
    )
    return f"""
<div class="studio-result-header">
  <h2>{escape(title)}</h2>
  <div class="studio-result-meta">
    {key_span}
    <span>Tempo <strong>{escape(tempo)}</strong></span>
    <span>Duration <strong>{escape(duration)}</strong></span>
    {confidence_span}
  </div>
  {notes_html}
  {technical_html}
</div>
"""


def recent_conversions_heading_html() -> str:
    return """
<div class="studio-recent-heading">
  <div class="studio-recent-heading-label">Recent conversions</div>
</div>
"""


def advanced_panel_heading_html() -> str:
    return """
<div class="studio-advanced-heading">
  <h3>Advanced</h3>
</div>
"""
