"""Player model: waveform peaks, speeds, and metronome click times."""

from __future__ import annotations

import json
import shutil
from html import escape
from pathlib import Path

from audio_to_tab.metronome import metronome_grid_times
from audio_to_tab.mixer import waveform_peaks

# 0.25 is below clamp_playback_rate's 0.5 floor, so this allow-list is the player.
PLAYER_SPEEDS = (0.25, 0.5, 0.75, 1.0)


def player_speed(rate: float) -> float:
    for allowed in PLAYER_SPEEDS:
        if abs(float(rate) - allowed) < 1e-6:
            return allowed
    return 1.0


def player_click_times(*, duration_sec: float, bpm: float) -> list[float]:
    grid = metronome_grid_times(duration_sec=float(duration_sec), bpm=float(bpm), phase_sec=0.0)
    return [float(tick) for tick in grid]


def player_peaks(path: str | Path, *, num_points: int = 160) -> list[float]:
    return [float(value) for value in waveform_peaks(path, num_points=num_points)]


def clamp_loop(start: float, end: float, duration: float) -> tuple[float, float]:
    duration = max(0.0, float(duration))
    start = min(max(0.0, float(start)), duration)
    end = min(max(0.0, float(end)), duration)
    if end < start:
        start, end = end, start
    if duration > 0 and end - start < 0.05:
        end = min(duration, start + 0.05)
    return start, end


def synth_source_available() -> bool:
    """True only when pyfluidsynth and the fluidsynth binary are already installed."""
    try:
        import fluidsynth  # noqa: F401
    except ImportError:
        return False
    return shutil.which("fluidsynth") is not None


def player_source_labels() -> list[str]:
    labels = ["Original"]
    if synth_source_available():
        labels.append("Synth")
    return labels


def player_html(
    *,
    peaks: list[float],
    duration: float,
    click_times: list[float],
    audio_b64: str,
    mime: str = "audio/wav",
    title: str = "",
) -> str:
    """Self-contained player. Waveform stays in the column; transport pins to the window."""
    payload = json.dumps(
        {
            "peaks": [round(value, 4) for value in peaks],
            "duration": max(0.0, float(duration)),
            "clicks": [round(value, 4) for value in click_times],
            "src": f"data:{mime};base64,{audio_b64}" if audio_b64 else "",
            "speeds": [
                {"rate": speed, "label": label}
                for speed, label in ((0.25, "0.25"), (0.5, "0.50"), (0.75, "0.75"), (1.0, "1X"))
            ],
        }
    )
    song = f'<span class="song">{escape(title)}</span>' if title else ""
    return f"""
<div id="tab-player" class="studio">
  <div class="wave">
    <canvas id="tab-wave" width="960" height="72" aria-label="Waveform"></canvas>
    <p class="tip">Drag across the waveform to loop a section.</p>
  </div>
  <div class="transport">
    <button type="button" id="tab-play">Play</button>
    <span id="tab-time">0:00 / 0:00</span>
    {song}
    <span id="tab-speeds"></span>
    <label class="quiet">Volume <input id="tab-volume" type="range" min="0" max="1" step="0.05" value="1"></label>
    <label class="toggle"><input id="tab-loop" type="checkbox"> Loop</label>
    <label class="sr">Start <input id="tab-loop-start" type="range" min="0" max="1" step="0.01" value="0"></label>
    <label class="sr">End <input id="tab-loop-end" type="range" min="0" max="1" step="0.01" value="1"></label>
    <label class="toggle"><input id="tab-metro" type="checkbox"> Metronome</label>
  </div>
  <audio id="tab-audio" preload="auto"></audio>
</div>
<style>
  #tab-player.studio {{
    font: 14px/1.4 ui-sans-serif, system-ui, sans-serif;
    color: #e8eaef;
    background: transparent;
    border: 0;
    padding: 0;
    margin: 0 0 0.85rem 0;
  }}
  #tab-player .tip {{
    margin: 0.35rem 0 0;
    color: #9aa3b2;
    font-size: 0.78rem;
  }}
  #tab-player .transport {{
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 40;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.55rem 0.8rem;
    margin: 0;
    padding: 0.5rem 1rem;
    background: #0f1115;
    border-top: 1px solid #2a2f3a;
  }}
  #tab-player .song {{
    color: #e8eaef;
    font-weight: 600;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 16rem;
  }}
  #tab-player.studio button {{
    font: inherit;
    color: #9aa3b2;
    background: transparent;
    border: 0;
    border-radius: 8px;
    padding: 0.2rem 0.35rem;
  }}
  #tab-player.studio #tab-play {{
    width: 2.6rem;
    height: 2.6rem;
    border-radius: 999px;
    padding: 0;
    background: #e8a317;
    color: #111;
    border: 1px solid #e8a317;
    font-weight: 700;
    font-size: 0.72rem;
  }}
  #tab-player.studio button[aria-pressed="true"] {{
    background: #e8a317;
    color: #111;
    border-radius: 6px;
    font-weight: 700;
  }}
  #tab-player #tab-time {{
    font-variant-numeric: tabular-nums;
    color: #e8eaef;
    min-width: 6.5rem;
  }}
  #tab-player label.quiet {{ color: #9aa3b2; font-size: 0.78rem; }}
  #tab-player label.toggle {{
    position: relative;
    border: 1px solid #2a2f3a;
    border-radius: 8px;
    padding: 0.28rem 0.6rem;
    color: #9aa3b2;
    background: #171a21;
  }}
  #tab-player label.toggle:has(input:checked) {{
    background: #e8a317;
    color: #111;
    border-color: #e8a317;
  }}
  #tab-player label.toggle input,
  #tab-player label.sr {{
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
  }}
  #tab-wave {{
    width: 100%;
    height: 72px;
    border: 1px solid #2a2f3a;
    border-radius: 10px;
    background: #171a21;
    cursor: pointer;
    display: block;
  }}
</style>
<script>
const spec = {payload};
const audio = document.getElementById("tab-audio");
const play = document.getElementById("tab-play");
const time = document.getElementById("tab-time");
const wave = document.getElementById("tab-wave");
const loopBox = document.getElementById("tab-loop");
const loopStart = document.getElementById("tab-loop-start");
const loopEnd = document.getElementById("tab-loop-end");
const metro = document.getElementById("tab-metro");
const volume = document.getElementById("tab-volume");
const speeds = document.getElementById("tab-speeds");
if (spec.src) audio.src = spec.src;
loopStart.max = String(spec.duration || 1);
loopEnd.max = String(spec.duration || 1);
loopEnd.value = String(spec.duration || 1);
function fmt(seconds) {{
  const whole = Math.max(0, Math.floor(seconds || 0));
  return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
}}
function region() {{
  let start = Number(loopStart.value);
  let end = Number(loopEnd.value);
  if (end < start) {{ const swap = start; start = end; end = swap; }}
  return [start, end];
}}
function paint(now) {{
  const ctx = wave.getContext("2d");
  const w = wave.width, h = wave.height;
  const total = spec.duration || audio.duration || 0;
  const t = Math.max(0, Number(now) || 0);
  ctx.clearRect(0, 0, w, h);
  if (loopBox.checked && total > 0) {{
    const [start, end] = region();
    if (end > start) {{
      ctx.fillStyle = "rgba(232, 163, 23, 0.18)";
      ctx.fillRect((start / total) * w, 0, ((end - start) / total) * w, h);
    }}
  }}
  ctx.fillStyle = "#e8a317";
  const peaks = spec.peaks.length ? spec.peaks : [0];
  const bar = w / peaks.length;
  peaks.forEach((peak, index) => {{
    const bh = Math.max(1, peak * (h - 8));
    ctx.fillRect(index * bar, (h - bh) / 2, Math.max(1, bar - 1), bh);
  }});
  if (total > 0) {{
    const x = (t / total) * w;
    ctx.fillStyle = "#e8eaef";
    ctx.fillRect(Math.max(0, x - 1), 0, 2, h);
  }}
}}
function tickClock() {{
  const now = audio.currentTime || 0;
  const total = audio.duration || spec.duration || 0;
  time.textContent = fmt(now) + " / " + fmt(total);
  paint(now);
  if (loopBox.checked) {{
    const [start, end] = region();
    if (end > start && now >= end) audio.currentTime = start;
  }}
  if (metro.checked) {{
    while (clickCursor < spec.clicks.length && spec.clicks[clickCursor] < now - 0.12) clickCursor += 1;
    if (clickCursor < spec.clicks.length && spec.clicks[clickCursor] <= now) {{
      blip();
      clickCursor += 1;
    }}
  }}
}}
let rafId = 0;
function pump() {{
  tickClock();
  if (!audio.paused && !audio.ended) rafId = requestAnimationFrame(pump);
  else rafId = 0;
}}
function startPump() {{
  if (!rafId) rafId = requestAnimationFrame(pump);
}}
paint(0);
spec.speeds.forEach((item) => {{
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = item.label;
  button.dataset.speed = String(item.rate);
  button.setAttribute("aria-pressed", item.rate === 1 ? "true" : "false");
  button.addEventListener("click", () => {{
    audio.playbackRate = item.rate;
    Array.from(speeds.children).forEach((child) => child.setAttribute("aria-pressed", child === button ? "true" : "false"));
  }});
  speeds.appendChild(button);
}});
play.addEventListener("click", async () => {{
  if (audio.paused) {{
    try {{ await audio.play(); }} catch (err) {{ play.textContent = "Play"; return; }}
    play.textContent = "Pause";
    startPump();
  }} else {{
    audio.pause();
    play.textContent = "Play";
    paint(audio.currentTime || 0);
  }}
}});
volume.addEventListener("input", () => {{ audio.volume = Number(volume.value); }});
let dragFrom = null;
function xToTime(event) {{
  const rect = wave.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
  return ratio * (spec.duration || audio.duration || 0);
}}
wave.addEventListener("mousedown", (event) => {{ dragFrom = xToTime(event); }});
wave.addEventListener("mouseup", (event) => {{
  const end = xToTime(event);
  if (dragFrom !== null && Math.abs(end - dragFrom) > 0.05) {{
    loopBox.checked = true;
    loopStart.value = String(Math.min(dragFrom, end));
    loopEnd.value = String(Math.max(dragFrom, end));
  }} else {{
    audio.currentTime = end;
  }}
  paint(audio.currentTime || end);
  dragFrom = null;
}});
loopBox.addEventListener("change", () => paint(audio.currentTime || 0));
loopStart.addEventListener("input", () => paint(audio.currentTime || 0));
loopEnd.addEventListener("input", () => paint(audio.currentTime || 0));
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let actx = null;
let clickCursor = 0;
function blip() {{
  if (!actx) actx = new AudioCtx();
  const osc = actx.createOscillator();
  const gain = actx.createGain();
  osc.frequency.value = 1400;
  gain.gain.value = 0.15;
  osc.connect(gain); gain.connect(actx.destination);
  osc.start();
  osc.stop(actx.currentTime + 0.03);
}}
audio.addEventListener("timeupdate", () => {{ tickClock(); }});
audio.addEventListener("play", () => {{ play.textContent = "Pause"; startPump(); }});
audio.addEventListener("pause", () => {{ play.textContent = "Play"; paint(audio.currentTime || 0); }});
audio.addEventListener("seeked", () => {{
  clickCursor = spec.clicks.findIndex((tick) => tick >= audio.currentTime);
  if (clickCursor < 0) clickCursor = spec.clicks.length;
  paint(audio.currentTime || 0);
}});
audio.addEventListener("ended", () => {{ play.textContent = "Play"; paint(0); }});
</script>
"""
