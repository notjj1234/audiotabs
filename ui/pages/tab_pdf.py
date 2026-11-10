"""Streamlit page: Tab PDF — guitar tab generator (standalone app)."""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from ui.common import (
    AUDIO_UPLOAD_TYPES,
    ensure_src_path,
    list_recent_runs,
    max_upload_caption,
    run_output_dir,
    save_upload,
    write_run_metadata,
)
from ui.guitar_engines import (
    TRACK_OPTIONS,
    default_guitar_track_option,
    guitar_track_radio_ids,
    normalize_guitar_track_selection,
)
from ui.studio_shell import hero_html, progress_card_html, result_header_html
from ui.studio_theme import inject_studio_theme

ensure_src_path()

from audio_to_tab.chords import ChordHit  # noqa: E402
from audio_to_tab.hardware import get_desktop_probe, lite_accelerator_available  # noqa: E402
from audio_to_tab.ingest import YouTubeDownloadError, is_youtube_url  # noqa: E402
from audio_to_tab.lyrics import LyricLine  # noqa: E402
from audio_to_tab.notation_view import (  # noqa: E402
    align_chords_to_lyrics,
    chord_diagram_svg,
    piano_roll_svg,
    screen_tab_text,
    tab_staff_svg,
)
from audio_to_tab.pipeline import (  # noqa: E402
    EmptyTranscriptionError,
    PipelineConfig,
    run_pipeline,
)
from audio_to_tab.player_bar import player_click_times, player_html, player_peaks  # noqa: E402
from audio_to_tab.progress_checklist import apply_progress, new_checklist  # noqa: E402
from audio_to_tab.roformer import is_roformer_backend_available  # noqa: E402
from audio_to_tab.separate import guitar_ft_weights_path, is_demucs_available  # noqa: E402
from audio_to_tab.tab_bundle import (  # noqa: E402
    bundle_chords,
    download_menu,
    format_size_kb,
    key_for_midi,
    show_convert_action,
    tab_document_for,
    write_tab_exports,
)
from audio_to_tab.tuning import TUNING_PRESETS  # noqa: E402

logger = logging.getLogger(__name__)

YOUTUBE_DISCLAIMER = (
    "FYI: public YouTube links only. No Private or Unlisted YouTube links"
)
DEMUCS_INSTALL_HINT = (
    'Demucs is required for stem separation. Install with: pip install -e ".[demucs]"'
)
_PLAYER_BYTE_CAP = 24 * 1024 * 1024
def record_failure(state: dict, exc: BaseException, *, message: str | None = None) -> None:
    """Drop every download from a failed run and keep the message for the page."""
    state.pop("tab_pdf_artifacts", None)
    state.pop("tab_pdf_flash", None)
    state.pop("tab_pdf_export_sig", None)
    state["tab_pdf_error"] = message or str(exc)
    detail = str(exc)
    if message and detail and detail != message:
        state["tab_pdf_error_detail"] = detail
    else:
        state.pop("tab_pdf_error_detail", None)


def _tab_model_from_guitar_engine(engine: str) -> tuple[str, bool]:
    if engine == "guitar_roformer":
        return "bs_roformer_sw", False
    if engine == "guitar_roformer_refine":
        return "bs_roformer_sw", True
    return "htdemucs_6s", False


def _download_name(title: str, suffix: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in title).strip(" .")
    return f"{cleaned or 'guitar_tab'}{suffix}"


def _clock(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def _paint_checklist(slot, rows: list[dict[str, str]]) -> None:
    slot.markdown(progress_card_html(rows), unsafe_allow_html=True)


def _load_result(artifacts: dict) -> dict:
    raw = artifacts.get("result")
    if not raw:
        return {}
    path = Path(str(raw))
    if not path.is_file():
        return {}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _lyric_lines(stored: dict) -> list[LyricLine]:
    lines: list[LyricLine] = []
    for item in stored.get("lyrics") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        try:
            lines.append(LyricLine(start=float(item["start"]), end=float(item["end"]), text=text))
        except (KeyError, TypeError, ValueError):
            continue
    return lines


def _roll_notes(midi_path: Path) -> list[tuple[int, float, float]]:
    import pretty_midi

    music = pretty_midi.PrettyMIDI(str(midi_path))
    notes: list[tuple[int, float, float]] = []
    for instrument in music.instruments:
        if instrument.is_drum:
            continue
        notes.extend((int(note.pitch), float(note.start), float(note.end)) for note in instrument.notes)
    return notes


def _render_player(playback: Path | None, duration: float, tempo: float) -> None:
    if playback is None or not playback.is_file():
        st.caption("Original audio was not kept for this run.")
        return
    if playback.stat().st_size > _PLAYER_BYTE_CAP:
        st.audio(str(playback))
        st.caption("This clip is long, so playback uses the browser player.")
        return
    try:
        peaks = player_peaks(playback)
    except Exception:
        logger.warning("Could not read waveform peaks from %s", playback, exc_info=True)
        peaks = []
    clicks = player_click_times(duration_sec=max(duration, 0.1), bpm=tempo if tempo > 0 else 120.0)
    encoded = base64.b64encode(playback.read_bytes()).decode("ascii")
    components_html = player_html(
        peaks=peaks,
        duration=max(duration, 0.1),
        click_times=clicks,
        audio_b64=encoded,
        mime="audio/wav",
    )
    st.html(components_html, unsafe_allow_javascript=True)


def _render_success(artifacts: dict) -> None:
    stored = _load_result(artifacts)
    title = st.session_state.get("tab_pdf_title") or stored.get("title") or "Guitar Tab"
    if "tab_result_tuning" not in st.session_state:
        tuning_name = str(stored.get("tuning_name") or "Standard (EADGBE)")
        st.session_state["tab_result_tuning"] = (
            tuning_name if tuning_name in TUNING_PRESETS else "Standard (EADGBE)"
        )
    if "tab_result_capo" not in st.session_state:
        st.session_state["tab_result_capo"] = int(stored.get("capo") or 0)
    if "tab_result_transpose" not in st.session_state:
        st.session_state["tab_result_transpose"] = int(stored.get("transpose") or 0)
    if "tab_result_bars" not in st.session_state:
        st.session_state["tab_result_bars"] = int(stored.get("bars_per_line") or 4)

    if st.session_state.get("tab_pdf_skipped_separation"):
        st.info(
            "Ran without stem separation. Install Demucs for better full-mix results. "
            f"{DEMUCS_INSTALL_HINT}"
        )

    midi_raw = artifacts.get("midi")
    midi_path = Path(str(midi_raw)) if midi_raw else None
    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    duration = float(stored.get("duration_sec") or 0.0)
    beats = int(stored.get("beats_per_measure") or 4)
    lyric_lines = _lyric_lines(stored)
    lyrics_status = str(stored.get("lyrics_status") or "")

    control_col, download_col = st.columns([5, 1])
    with control_col:
        view = st.radio(
            "View",
            ["Chords", "Tab", "Text", "Piano roll"],
            horizontal=True,
            key="tab_pdf_view",
            label_visibility="collapsed",
        )
    with download_col, st.popover("Download"):
        items = download_menu(artifacts)
        if not items:
            st.caption("No files for this run.")
        suffixes = {"pdf": ".pdf", "midi": ".mid", "tab": ".tab", "guitar_stem": ".wav"}
        for item in items:
            payload: bytes | str
            if item["key"] == "tab":
                payload = item["path"].read_text(encoding="utf-8")
            else:
                payload = item["path"].read_bytes()
            st.download_button(
                label=item["label"],
                data=payload,
                file_name=_download_name(str(title), suffixes[item["key"]]),
                mime=item["mime"],
                key=f"tab_pdf_download_{item['key']}",
            )

    tuning_col, capo_col, transpose_col, bars_col = st.columns(4)
    with tuning_col:
        tuning_name = st.selectbox("Tuning", list(TUNING_PRESETS), key="tab_result_tuning")
    with capo_col:
        capo = int(
            st.selectbox(
                "Capo",
                list(range(13)),
                format_func=lambda fret: "Off" if int(fret) == 0 else str(fret),
                key="tab_result_capo",
            )
        )
    with transpose_col:
        transpose = int(
            st.number_input("Transpose", min_value=-12, max_value=12, step=1, key="tab_result_transpose")
        )
    with bars_col:
        bars = int(st.selectbox("Bars per line", list(range(1, 9)), key="tab_result_bars"))

    signature = [str(tuning_name), capo, transpose, bars]
    document = None
    chords: list[ChordHit] = []
    song_key = str(stored.get("key") or "Unknown")
    if midi_path is not None and midi_path.is_file():
        document = tab_document_for(
            midi_path,
            tempo_bpm=tempo,
            tempo_confidence=confidence,
            beats_per_measure=beats,
            tuning_name=str(tuning_name),
            capo=capo,
            transpose=transpose,
        )
        chords = bundle_chords(
            midi_path,
            transpose=transpose,
            capo=capo,
            tuning_name=str(tuning_name),
        )
        song_key = key_for_midi(midi_path, transpose=transpose, capo=capo)
        if st.session_state.get("tab_pdf_export_sig") != signature:
            output_dir = midi_path.parent
            write_tab_exports(
                document,
                output_dir,
                title=str(title),
                capo=capo,
                transpose=transpose,
                bars_per_line=bars,
                chords=chords,
                key=song_key,
                duration_sec=duration,
                tempo_bpm=tempo,
                tempo_confidence=confidence,
                tuning_name=str(tuning_name),
                lyrics=lyric_lines,
                lyrics_status=lyrics_status,
                beats_per_measure=beats,
            )
            st.session_state["tab_pdf_export_sig"] = signature

    st.markdown(
        result_header_html(
            str(title),
            key=str(song_key),
            tempo=f"{tempo:.0f} BPM",
            duration=_clock(duration),
        ),
        unsafe_allow_html=True,
    )
    st.caption("Check every note before you trust it.")

    show_rail = view in {"Chords", "Tab"} and bool(chords)
    if show_rail:
        main_col, rail_col = st.columns([3, 1])
    else:
        main_col = st.container()
        rail_col = None
    with main_col:
        if view == "Chords":
            chunks: list[str] = []
            if lyric_lines:
                for row in align_chords_to_lyrics(chords, lyric_lines):
                    if row["chords"]:
                        names = "  ".join(escape(name) for name in row["chords"])
                        chunks.append(f"<p><strong>{names}</strong></p>")
                    if row["text"]:
                        chunks.append(f"<p>{escape(row['text'])}</p>")
            elif chords:
                for hit in chords:
                    chunks.append(f"<p>{escape(_clock(hit.start))}  {escape(hit.name)}</p>")
            else:
                chunks.append("<p>No chords recognized in this clip.</p>")
            if lyrics_status:
                chunks.append(f"<p><em>{escape(lyrics_status)}</em></p>")
            st.markdown(
                f'<div class="studio-score">{"".join(chunks)}</div>',
                unsafe_allow_html=True,
            )
        elif view == "Tab":
            if document is None:
                st.caption("The MIDI for this run is gone, so the staff cannot be redrawn.")
            else:
                st.markdown(
                    f'<div class="studio-score">{tab_staff_svg(document, bars_per_line=bars)}</div>',
                    unsafe_allow_html=True,
                )
        elif view == "Text":
            if document is None:
                tab_raw = artifacts.get("tab")
                tab_path = Path(str(tab_raw)) if tab_raw else None
                body = (
                    tab_path.read_text(encoding="utf-8")
                    if tab_path and tab_path.is_file()
                    else ""
                )
                if not body:
                    st.caption("The tab text for this run is gone.")
                else:
                    st.markdown(
                        f'<div class="studio-score"><pre>{escape(body)}</pre></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    f'<div class="studio-score"><pre>{escape(screen_tab_text(document, bars))}</pre></div>',
                    unsafe_allow_html=True,
                )
        else:
            if midi_path is None or not midi_path.is_file():
                st.caption("The MIDI for this run is gone, so the piano roll cannot be drawn.")
            else:
                st.markdown(
                    '<div class="studio-score">'
                    + piano_roll_svg(
                        _roll_notes(midi_path),
                        tempo_bpm=tempo,
                        beats_per_measure=beats,
                        semitones=transpose + capo,
                    )
                    + "</div>",
                    unsafe_allow_html=True,
                )
    if rail_col is not None:
        with rail_col:
            diagrams = "".join(
                f'<div class="diagram">{chord_diagram_svg(hit.name, hit.frets)}</div>'
                for hit in chords
            )
            st.markdown(
                f'<div class="studio-rail"><h4>Chords</h4>{diagrams}</div>',
                unsafe_allow_html=True,
            )

    details = st.session_state.get("tab_pdf_details") or {}
    with st.expander("Transcription details"):
        st.write(f"Tempo confidence: {confidence}")
        if details:
            st.write(
                f"Onset {details.get('onset', '—')}, frame {details.get('frame', '—')}, "
                f"mix-aware {'on' if details.get('mix_aware') else 'off'}, "
                f"separation {'on' if details.get('separate') else 'off'}."
            )
        if lyrics_status:
            st.write(lyrics_status)
        st.caption("Transpose and capo change the written tab and the chord names. Playback stays the original audio.")

    playback_raw = artifacts.get("playback")
    playback = Path(str(playback_raw)) if playback_raw else None
    _render_player(playback, duration, tempo)


def main() -> None:
    inject_studio_theme()
    has_results = bool(st.session_state.get("tab_pdf_artifacts"))
    if not has_results:
        st.markdown(hero_html(), unsafe_allow_html=True)
    st.markdown(
        '<p class="studio-note"><strong>Experimental.</strong> Tabs are often wrong. '
        "Best on short solo-guitar clips. For full songs, turn on guitar stem separation "
        "(or isolate guitar elsewhere first).</p>",
        unsafe_allow_html=True,
    )

    demucs_ok = is_demucs_available()
    roformer_ok = is_roformer_backend_available()
    guitar_ft_ok = guitar_ft_weights_path().is_file()
    can_separate = demucs_ok or roformer_ok
    if not can_separate:
        st.info(
            "Stem separation is unavailable (Demucs not installed). "
            "Conversions run on the full mix. Quality may be lower with drums/bass. "
            f"{DEMUCS_INSTALL_HINT}"
        )

    recent_runs = list_recent_runs("tab_pdf")
    if recent_runs:
        with st.expander(f"Recent conversions ({len(recent_runs)})", expanded=False):
            for run in recent_runs:
                run_artifacts = run.get("artifacts", {})
                available = Path(run_artifacts.get("pdf", "")).exists() if run_artifacts else False
                cols = st.columns([3, 1])
                with cols[0]:
                    created_at = run.get("created_at")
                    when = (
                        datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")
                        if created_at
                        else ""
                    )
                    st.write(run.get("title") or "Guitar Tab")
                    st.caption(when if available else f"{when}. Files no longer available")
                with cols[1]:
                    if available and st.button("Reopen", key=f"reopen_tab_{run['run_dir']}"):
                        st.session_state["tab_pdf_artifacts"] = run_artifacts
                        st.session_state["tab_pdf_title"] = run.get("title") or "Guitar Tab"
                        st.session_state["tab_pdf_skipped_separation"] = False
                        st.session_state.pop("tab_pdf_flash", None)
                        st.session_state.pop("tab_pdf_error", None)
                        st.session_state.pop("tab_pdf_error_detail", None)
                        st.session_state.pop("tab_pdf_export_sig", None)
                        st.rerun()

    with st.expander("Conversion settings", expanded=not has_results):
        title = st.text_input(
            "Tab title",
            value="Guitar Tab",
            help="This text appears as the title on the generated tab PDF.",
        )
        if "tab_setup_tuning" not in st.session_state:
            st.session_state["tab_setup_tuning"] = "Standard (EADGBE)"
        if "tab_setup_capo" not in st.session_state:
            st.session_state["tab_setup_capo"] = 0
        tuning_name = st.selectbox("Tuning", list(TUNING_PRESETS), key="tab_setup_tuning")
        capo = int(
            st.selectbox(
                "Capo",
                list(range(13)),
                format_func=lambda fret: "Off" if int(fret) == 0 else str(fret),
                key="tab_setup_capo",
            )
        )
        if "tab_separate_stems" not in st.session_state:
            st.session_state["tab_separate_stems"] = False
        if "tab_safer_length" not in st.session_state:
            st.session_state["tab_safer_length"] = True
        if "tab_max_duration_sec" not in st.session_state:
            st.session_state["tab_max_duration_sec"] = 90

        separate_stems = st.toggle(
            "Separate guitar stem (full mixes only)",
            disabled=not can_separate,
            key="tab_separate_stems",
            help=(
                "Off by default for solo guitar (faster, usually better). "
                "Turn on only for full mixes."
                + (f" Install Demucs to enable: {DEMUCS_INSTALL_HINT}" if not can_separate else "")
            ),
        )
        if separate_stems and can_separate:
            st.warning(
                "Full mixes often leave guitar bleed and wrong notes (model limit). "
                "Prefer a clean solo-guitar clip when you can."
            )

        safer_length = st.checkbox(
            "Safer length (recommended)",
            key="tab_safer_length",
            help=(
                "Trims long clips before transcription. Tab PDF works best on short "
                "solo-guitar segments. Uncheck only if you need the full track."
            ),
        )
        max_duration: float | None = None
        if safer_length:
            max_duration = float(
                st.slider(
                    "Max duration (seconds)",
                    min_value=15,
                    max_value=300,
                    step=15,
                    key="tab_max_duration_sec",
                )
            )
        else:
            st.caption("Full track will be processed. This is slow and often worse for Tab PDF.")

        tab_model = "htdemucs_6s"
        tab_guitar_refine = False
        tab_guitar_checkpoint = None
        tab_low_end_restore_db = 0.0
        tab_sub_bass_debleed = False
        tab_bleed_gate = False
        tab_adaptive_fold_gain = False
        tab_guitar_ensemble = False
        mix_aware = True
        tempo_override = 0.0
        onset_threshold = 0.5
        frame_threshold = 0.3

        if separate_stems and can_separate:
            if "tab_low_end_restore_db" not in st.session_state:
                st.session_state["tab_low_end_restore_db"] = 0.0
            if "tab_sub_bass_debleed" not in st.session_state:
                st.session_state["tab_sub_bass_debleed"] = False
            radio_ids = guitar_track_radio_ids(roformer_available=roformer_ok)
            guitar_labels = {
                oid: TRACK_OPTIONS[oid]["label"] for oid in radio_ids if oid in TRACK_OPTIONS
            }
            promoted_default = default_guitar_track_option(
                roformer_available=roformer_ok,
                prefer_roformer=lite_accelerator_available(get_desktop_probe()),
            )
            current_engine = str(st.session_state.get("tab_guitar_engine") or promoted_default)
            if current_engine not in guitar_labels:
                st.session_state["tab_guitar_engine"] = normalize_guitar_track_selection(
                    current_engine,
                    roformer_available=roformer_ok,
                )
                if st.session_state["tab_guitar_engine"] not in guitar_labels:
                    st.session_state["tab_guitar_engine"] = next(iter(guitar_labels))
            engine = st.radio(
                "Guitar separation",
                options=list(guitar_labels.keys()),
                format_func=lambda oid: guitar_labels[oid],
                key="tab_guitar_engine",
            )
            tab_model, tab_guitar_refine = _tab_model_from_guitar_engine(str(engine))
            if tab_model == "htdemucs_6s":
                if guitar_ft_ok:
                    if st.checkbox(
                        "Use cached guitar-ft Demucs weights",
                        value=False,
                        key="tab_guitar_ft",
                        help="Uses guitar-ft already in TORCH_HOME. Does not download.",
                    ):
                        tab_guitar_checkpoint = "htdemucs_6s_guitar_ft"
                else:
                    st.caption(
                        "guitar-ft weights appear after a one-time ~330 MB download "
                        "when first used by Demucs guitar-ft."
                    )
            tab_low_end_restore_db = float(
                st.slider(
                    "Low-end restore (dB)",
                    min_value=0.0,
                    max_value=6.0,
                    step=1.0,
                    key="tab_low_end_restore_db",
                    help="Boosts 60–200 Hz on the guitar stem before transcription. 0 = off.",
                )
            )
            tab_sub_bass_debleed = st.checkbox(
                "Subtractive bass de-bleed",
                key="tab_sub_bass_debleed",
                help="Subtracts scaled bass/drum energy below ~150 Hz from the guitar stem.",
            )
            tab_bleed_gate = st.checkbox(
                "Spectral bleed gate",
                key="tab_bleed_gate",
                help="Scrubs leftover bass/cymbal flutter when competitor stems dominate.",
            )
            tab_adaptive_fold_gain = st.checkbox(
                "Adaptive fold gain",
                key="tab_adaptive_fold_gain",
                help="Searches the Other→Guitar mix gain instead of the fixed 0.5.",
            )
            tab_guitar_ensemble = st.checkbox(
                "Cross-model guitar ensemble",
                key="tab_guitar_ensemble",
                help="Also runs BS-RoFormer-SW and blends guitar stems. Much slower; needs [roformer].",
            )

        with st.expander("Advanced transcription settings"):
            mix_aware = st.checkbox("Mix-aware filtering (stricter note filters)", value=True)
            tempo_override = st.number_input(
                "Tempo override (BPM, 0 = auto)",
                min_value=0.0,
                max_value=240.0,
                value=0.0,
                step=1.0,
            )
            onset_threshold = st.slider("Onset threshold", 0.3, 0.9, 0.5, 0.05)
            frame_threshold = st.slider("Frame threshold", 0.2, 0.8, 0.3, 0.05)

        uploaded = st.file_uploader(
            "Upload MP3 / WAV / FLAC / M4A",
            type=AUDIO_UPLOAD_TYPES,
        )
        if uploaded is not None:
            size = getattr(uploaded, "size", None)
            if not isinstance(size, int):
                size = len(uploaded.getvalue())
            file_name = Path(str(getattr(uploaded, "name", "") or "audio")).name
            st.text(f"{file_name}  {format_size_kb(size)}")
            st.audio(uploaded)
        st.caption(f"{max_upload_caption()} Files are processed locally.")
        youtube_url = st.text_input("Or paste a YouTube URL")
        st.caption(YOUTUBE_DISCLAIMER)

        convert_clicked = False
        if show_convert_action(has_file=uploaded is not None, youtube_url=youtube_url):
            convert_clicked = st.button("Convert to tab PDF", type="primary")
        else:
            st.caption("Add an audio file or a public YouTube link.")

        if convert_clicked:
            st.session_state.pop("tab_pdf_error", None)
            st.session_state.pop("tab_pdf_error_detail", None)
            if not uploaded and not youtube_url.strip():
                record_failure(
                    st.session_state,
                    ValueError("Upload an audio file or enter a YouTube URL."),
                )
                st.rerun()
            if youtube_url.strip() and not is_youtube_url(youtube_url):
                record_failure(st.session_state, ValueError("Only YouTube URLs are allowed."))
                st.rerun()

            effective_separate = separate_stems and can_separate
            skipped_separation = separate_stems and not can_separate
            output_dir = run_output_dir()
            config = PipelineConfig(
                separate_stems=effective_separate,
                max_duration_sec=max_duration,
                title=title or "Guitar Tab",
                mix_aware_filtering=mix_aware,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                tempo_bpm_override=tempo_override if tempo_override > 0 else None,
                model=tab_model,
                guitar_refine=tab_guitar_refine,
                guitar_checkpoint=tab_guitar_checkpoint,
                low_end_restore_db=tab_low_end_restore_db,
                sub_bass_debleed=tab_sub_bass_debleed,
                bleed_gate=tab_bleed_gate,
                adaptive_fold_gain=tab_adaptive_fold_gain,
                guitar_ensemble=tab_guitar_ensemble,
                tuning_name=str(tuning_name),
                capo=capo,
                transpose=0,
                bars_per_line=4,
            )
            rows = new_checklist()
            progress_slot = st.empty()
            _paint_checklist(progress_slot, rows)

            def on_progress(stage: str, message: str) -> None:
                nonlocal rows
                rows = apply_progress(rows, stage, message)
                _paint_checklist(progress_slot, rows)

            try:
                audio_path = save_upload(uploaded) if uploaded else None
                url = youtube_url.strip() or None
                artifacts = run_pipeline(
                    audio_path=audio_path,
                    youtube_url=url,
                    output_dir=output_dir,
                    config=config,
                    on_progress=on_progress,
                )
                rows = apply_progress(rows, "done", "Pipeline complete")
                _paint_checklist(progress_slot, rows)
                st.session_state["tab_pdf_artifacts"] = {key: str(value) for key, value in artifacts.items()}
                st.session_state["tab_pdf_title"] = title or "Guitar Tab"
                st.session_state["tab_pdf_skipped_separation"] = skipped_separation
                st.session_state["tab_pdf_source_audio_path"] = str(audio_path) if audio_path else None
                st.session_state["tab_pdf_flash"] = "Conversion complete."
                st.session_state["tab_pdf_details"] = {
                    "onset": onset_threshold,
                    "frame": frame_threshold,
                    "mix_aware": mix_aware,
                    "separate": effective_separate,
                }
                st.session_state["tab_result_tuning"] = str(tuning_name)
                st.session_state["tab_result_capo"] = int(capo)
                st.session_state["tab_result_transpose"] = 0
                st.session_state["tab_result_bars"] = 4
                st.session_state["tab_pdf_export_sig"] = [str(tuning_name), int(capo), 0, 4]
                st.session_state.pop("tab_pdf_error", None)
                st.session_state.pop("tab_pdf_error_detail", None)
                write_run_metadata(
                    output_dir,
                    page="tab_pdf",
                    title=title or "Guitar Tab",
                    artifacts=artifacts,
                )
                st.rerun()
            except EmptyTranscriptionError as exc:
                record_failure(st.session_state, exc)
                st.rerun()
            except YouTubeDownloadError as exc:
                record_failure(st.session_state, exc)
                st.rerun()
            except (FileNotFoundError, OSError) as exc:
                logger.warning("Tab PDF could not read the audio file: %s", exc)
                record_failure(st.session_state, exc, message="Could not read that audio file.")
                st.rerun()
            except ValueError as exc:
                record_failure(st.session_state, exc)
                st.rerun()
            except Exception as exc:
                logger.exception("Unexpected tab conversion error")
                record_failure(
                    st.session_state,
                    exc,
                    message="Conversion failed unexpectedly. Check that the audio file is valid.",
                )
                st.rerun()

    if flash := st.session_state.pop("tab_pdf_flash", None):
        st.success(flash)

    error = st.session_state.get("tab_pdf_error")
    artifacts_map = st.session_state.get("tab_pdf_artifacts")
    if error and not artifacts_map:
        st.error(error)
        if detail := st.session_state.get("tab_pdf_error_detail"):
            with st.expander("Technical details"):
                st.code(detail)
        return
    if not artifacts_map:
        return
    _render_success(artifacts_map)


if __name__ == "__main__":
    main()
