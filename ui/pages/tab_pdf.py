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
    app_icon_data_uri,
    ensure_src_path,
    list_recent_runs,
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
from audio_to_tab.hardware import (  # noqa: E402
    get_desktop_probe,
    lite_accelerator_available,
    roformer_max_audio_sec,
)
from audio_to_tab.ingest import (  # noqa: E402
    FFmpegMissingError,
    YouTubeDownloadError,
    YouTubeSearchError,
    download_direct_media,
    ffmpeg_available,
    ffmpeg_install_hint,
    format_youtube_duration,
    is_direct_media_url,
    is_youtube_url,
    probe_youtube_availability,
    search_youtube_videos,
    validate_youtube_url_shape,
)
from audio_to_tab.isolate import probe_duration_sec  # noqa: E402
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
from audio_to_tab.roformer import RoFormerTooLongError, is_roformer_backend_available  # noqa: E402
from audio_to_tab.separate import (  # noqa: E402
    guitar_ft_weights_cached,
    guitar_ft_weights_corrupt,
    is_demucs_available,
)
from audio_to_tab.tab_bundle import (  # noqa: E402
    bundle_chords,
    download_menu,
    key_for_midi,
    show_convert_action,
    tab_document_for,
    write_tab_exports,
)
from audio_to_tab.tuning import TUNING_PRESETS  # noqa: E402
from audio_to_tab.user_errors import user_facing_message  # noqa: E402
from ui.youtube_search import (  # noqa: E402
    PAGE_SIZE,
    hit_meta,
    hit_state,
    normalize_page,
)

logger = logging.getLogger(__name__)

YOUTUBE_DISCLAIMER = (
    "FYI: public YouTube links only. No Private or Unlisted YouTube links"
)
DEMUCS_INSTALL_HINT = (
    'Demucs is required for stem separation. Install with: pip install -e ".[demucs]"'
)
_PLAYER_BYTE_CAP = 24 * 1024 * 1024

_YOUTUBE_OPEN_KEY = "tab_youtube_open"
_YOUTUBE_QUERY_KEY = "tab_youtube_query"
_YOUTUBE_HITS_KEY = "tab_youtube_hits"
_YOUTUBE_PAGE_KEY = "tab_youtube_page"
_YOUTUBE_ERROR_KEY = "tab_youtube_error"
_YOUTUBE_URL_KEY = "tab_youtube_url"
_YOUTUBE_TITLE_KEY = "tab_youtube_title"
_YOUTUBE_DURATION_KEY = "tab_youtube_duration"
_MEDIA_URL_KEY = "tab_media_url_paste"
_GUITAR_CAUTION = (
    "Best results: clean solo guitar. Full mixes need stem separation."
)


def _close_youtube_search() -> None:
    st.session_state[_YOUTUBE_OPEN_KEY] = False


def _run_youtube_search(query: str, page: int) -> None:
    """Fetch one page of public results; errors stay inside the dialog."""
    page = normalize_page(page)
    st.session_state[_YOUTUBE_PAGE_KEY] = page
    st.session_state.pop(_YOUTUBE_ERROR_KEY, None)
    try:
        hits = search_youtube_videos(
            query,
            max_results=PAGE_SIZE,
            offset=(page - 1) * PAGE_SIZE,
        )
    except (YouTubeSearchError, ValueError) as exc:
        st.session_state[_YOUTUBE_HITS_KEY] = []
        st.session_state[_YOUTUBE_ERROR_KEY] = str(exc)
        return
    st.session_state[_YOUTUBE_HITS_KEY] = [hit_state(hit) for hit in hits]


def _select_youtube_hit(hit: dict) -> None:
    st.session_state[_YOUTUBE_URL_KEY] = str(hit.get("url") or "")
    st.session_state[_YOUTUBE_TITLE_KEY] = str(hit.get("title") or "")
    st.session_state[_YOUTUBE_DURATION_KEY] = hit.get("duration_sec")
    _close_youtube_search()


@st.dialog("Search YouTube", width="large", on_dismiss=_close_youtube_search)
def _youtube_search_dialog() -> None:
    """Modal: search public videos, then use one as the conversion source."""
    st.caption("Public videos only. Pick a video, then convert it to tab.")
    st.caption(YOUTUBE_DISCLAIMER)
    with st.form("tab_youtube_search_form", clear_on_submit=False, border=False):
        query = st.text_input(
            "Song or artist",
            key=_YOUTUBE_QUERY_KEY,
            placeholder="e.g. artist, song title",
        )
        submitted = st.form_submit_button("Search", type="primary", width="stretch")
    if submitted:
        _run_youtube_search(query, 1)

    error = st.session_state.get(_YOUTUBE_ERROR_KEY)
    if error:
        st.warning(str(error))

    page = normalize_page(st.session_state.get(_YOUTUBE_PAGE_KEY, 1))
    hits = st.session_state.get(_YOUTUBE_HITS_KEY) or []
    if not isinstance(hits, list):
        hits = []
    if hits:
        start = (page - 1) * PAGE_SIZE
        st.caption(f"Showing {start + 1}–{start + len(hits)}")
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            video_id = str(hit.get("video_id") or "")
            url = str(hit.get("url") or "").strip()
            title = str(hit.get("title") or "Untitled")
            with st.container(border=True):
                st.markdown(f"**{title}**")
                meta = hit_meta(hit)
                if meta:
                    st.caption(meta)
                if st.button(
                    "Use",
                    key=f"tab_youtube_pick_{video_id}",
                    type="primary",
                    disabled=not url,
                ):
                    _select_youtube_hit(hit)
                    st.rerun()

    if hits or page > 1:
        if st.button(
            "Previous",
            key="tab_youtube_prev",
            type="secondary",
            disabled=page <= 1,
        ):
            _run_youtube_search(str(st.session_state.get(_YOUTUBE_QUERY_KEY) or ""), page - 1)
            st.rerun()
        if st.button(
            "Next",
            key="tab_youtube_next",
            type="secondary",
            disabled=len(hits) < PAGE_SIZE,
        ):
            _run_youtube_search(str(st.session_state.get(_YOUTUBE_QUERY_KEY) or ""), page + 1)
            st.rerun()

    if st.button("Close", key="tab_youtube_close", type="secondary", width="stretch"):
        _close_youtube_search()
        st.rerun()


def record_failure(state: dict, exc: BaseException, *, message: str | None = None) -> None:
    """Drop every download from a failed run and keep the message for the page."""
    state.pop("tab_pdf_artifacts", None)
    state.pop("tab_pdf_flash", None)
    state.pop("tab_pdf_export_sig", None)
    if message is None:
        primary, detail = user_facing_message(exc)
        state["tab_pdf_error"] = primary
        if detail and detail != primary:
            state["tab_pdf_error_detail"] = detail
        else:
            state.pop("tab_pdf_error_detail", None)
        if isinstance(exc, EmptyTranscriptionError):
            state["tab_pdf_empty_recovery"] = True
        else:
            state.pop("tab_pdf_empty_recovery", None)
        return
    state["tab_pdf_error"] = message
    detail = str(exc)
    if detail and detail != message:
        state["tab_pdf_error_detail"] = detail
    else:
        state.pop("tab_pdf_error_detail", None)
    state.pop("tab_pdf_empty_recovery", None)


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


def _render_player(playback: Path | None, duration: float, tempo: float, title: str = "") -> None:
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
        title=title,
    )
    st.html(components_html, unsafe_allow_javascript=True)


_INK = "#e8eaef"
_LINE = "#3d4553"


def _capo_label(fret: int) -> str:
    return "None" if int(fret) == 0 else str(int(fret))


def _clear_song() -> None:
    st.session_state["tab_upload_nonce"] = int(st.session_state.get("tab_upload_nonce") or 0) + 1
    for key in (
        "tab_pdf_artifacts",
        "tab_pdf_flash",
        "tab_pdf_error",
        "tab_pdf_error_detail",
        "tab_pdf_export_sig",
        "tab_pdf_skipped_separation",
        "tab_pdf_details",
        "tab_pdf_pending",
        "tab_pdf_title",
        "tab_result_tuning",
        "tab_result_capo",
        "tab_result_transpose",
        "tab_result_bars",
        "tab_pdf_view",
        _YOUTUBE_URL_KEY,
        _YOUTUBE_TITLE_KEY,
        _YOUTUBE_DURATION_KEY,
        _YOUTUBE_OPEN_KEY,
    ):
        st.session_state.pop(key, None)


def _init_setup_state() -> None:
    st.session_state.setdefault("tab_pdf_title", "Guitar Tab")
    st.session_state.setdefault("tab_setup_tuning", "Standard (EADGBE)")
    st.session_state.setdefault("tab_setup_capo", 0)
    if "tab_separate_stems" not in st.session_state:
        st.session_state["tab_separate_stems"] = False
    st.session_state.setdefault("tab_safer_length", True)
    st.session_state.setdefault("tab_max_duration_sec", 90)
    st.session_state.setdefault("tab_transcription_preset", "solo")
    st.session_state.setdefault("tab_expert_options", False)
    st.session_state.setdefault("tab_full_track_confirm", False)
    st.session_state.setdefault(_MEDIA_URL_KEY, "")


def _apply_transcription_preset(preset: str) -> None:
    if preset == "full_mix":
        st.session_state["tab_separate_stems"] = True
        st.session_state["tab_mix_aware"] = True
    else:
        st.session_state["tab_separate_stems"] = False
        st.session_state["tab_mix_aware"] = False


def _render_success(artifacts: dict) -> None:
    st.session_state.pop("tab_pdf_flash", None)
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

    tuning_name = st.session_state["tab_result_tuning"]
    capo = int(st.session_state["tab_result_capo"])
    transpose = int(st.session_state["tab_result_transpose"])
    bars = int(st.session_state["tab_result_bars"])

    midi_raw = artifacts.get("midi")
    midi_path = Path(str(midi_raw)) if midi_raw else None
    tempo = float(stored.get("tempo_bpm") or 120.0)
    confidence = str(stored.get("tempo_confidence") or "high")
    duration = float(stored.get("duration_sec") or 0.0)
    beats = int(stored.get("beats_per_measure") or 4)
    lyric_lines = _lyric_lines(stored)
    lyrics_status = str(stored.get("lyrics_status") or "")

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
            write_tab_exports(
                document,
                midi_path.parent,
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

    action_col, download_col = st.columns([6, 1])
    with action_col:
        if st.button("New song", key="tab_new_song", type="secondary"):
            _clear_song()
            st.rerun()
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

    tuning_col, capo_col, transpose_col, bars_col = st.columns(4)
    with tuning_col:
        st.selectbox("Tuning", list(TUNING_PRESETS), key="tab_result_tuning")
    with capo_col:
        st.selectbox(
            "Capo",
            list(range(13)),
            format_func=_capo_label,
            key="tab_result_capo",
        )
    with transpose_col:
        st.number_input("Transpose", min_value=-12, max_value=12, step=1, key="tab_result_transpose")
    with bars_col:
        st.selectbox("Bars", list(range(1, 9)), key="tab_result_bars")

    if st.session_state.get("tab_pdf_skipped_separation"):
        st.caption(
            "Ran without stem separation. Install Demucs for better full-mix results. "
            f"{DEMUCS_INSTALL_HINT}"
        )

    playback_raw = artifacts.get("playback")
    playback = Path(str(playback_raw)) if playback_raw else None
    _render_player(playback, duration, tempo, str(title))

    view = st.radio(
        "View",
        ["Tab", "Chords", "Text", "Piano roll"],
        horizontal=True,
        key="tab_pdf_view",
        label_visibility="collapsed",
    )

    score_title = f'<h3 class="score-title">{escape(str(title))}</h3>'
    if view == "Chords":
        chunks: list[str] = [score_title]
        if lyric_lines:
            for row in align_chords_to_lyrics(chords, lyric_lines):
                if row["chords"]:
                    names = "  ".join(escape(name) for name in row["chords"])
                    chunks.append(f'<p class="chord-names">{names}</p>')
                if row["text"]:
                    chunks.append(f'<p class="lyric-line">{escape(row["text"])}</p>')
        elif chords:
            for hit in chords:
                chunks.append(
                    f'<p class="chord-names">{escape(hit.name)}</p>'
                    f'<p class="lyric-line">{escape(_clock(hit.start))}</p>'
                )
        else:
            chunks.append("<p>No chords recognized in this clip.</p>")
        if lyrics_status:
            chunks.append(f'<p class="lyric-line"><em>{escape(lyrics_status)}</em></p>')
        main_html = "".join(chunks)
    elif view == "Tab":
        if document is None:
            main_html = score_title + "<p>The MIDI for this run is gone, so the staff cannot be redrawn.</p>"
        else:
            main_html = score_title + tab_staff_svg(
                document, bars_per_line=bars, ink=_INK, line=_LINE
            )
    elif view == "Text":
        if document is None:
            tab_raw = artifacts.get("tab")
            tab_path = Path(str(tab_raw)) if tab_raw else None
            body = tab_path.read_text(encoding="utf-8") if tab_path and tab_path.is_file() else ""
            if not body:
                main_html = score_title + "<p>The tab text for this run is gone.</p>"
            else:
                main_html = score_title + f"<pre>{escape(body)}</pre>"
        else:
            main_html = score_title + f"<pre>{escape(screen_tab_text(document, bars))}</pre>"
    else:
        if midi_path is None or not midi_path.is_file():
            main_html = score_title + "<p>The MIDI for this run is gone, so the piano roll cannot be drawn.</p>"
        else:
            main_html = score_title + piano_roll_svg(
                _roll_notes(midi_path),
                tempo_bpm=tempo,
                beats_per_measure=beats,
                semitones=transpose + capo,
                ink=_INK,
                line=_LINE,
            )

    show_rail = view in {"Chords", "Tab"} and bool(chords)
    rail = ""
    if show_rail:
        diagrams = "".join(
            f'<div class="diagram">{chord_diagram_svg(hit.name, hit.frets, ink=_INK)}</div>'
            for hit in chords
        )
        rail = f'<aside class="studio-rail"><h4>Chords</h4><div class="diagrams">{diagrams}</div></aside>'
    st.markdown(
        f'<div class="studio-stage"><div class="studio-score">{main_html}</div>{rail}</div>',
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


def _render_entry() -> None:
    _init_setup_state()
    st.markdown(hero_html(icon_data_uri=app_icon_data_uri()), unsafe_allow_html=True)

    demucs_ok = is_demucs_available()
    roformer_ok = is_roformer_backend_available()
    guitar_ft_ok = guitar_ft_weights_cached()
    guitar_ft_bad = guitar_ft_weights_corrupt()
    can_separate = demucs_ok or roformer_ok
    has_ffmpeg = ffmpeg_available()
    if not has_ffmpeg:
        st.warning(
            "ffmpeg is required for conversion. Convert is disabled until it is installed. "
            + ffmpeg_install_hint()
        )

    with st.container(key="tab_source_entry"):
        uploaded = st.file_uploader(
            "Upload audio",
            type=AUDIO_UPLOAD_TYPES,
            key=f"tab_upload_{int(st.session_state.get('tab_upload_nonce') or 0)}",
            help="MP3, WAV, M4A, or FLAC. Processing stays on this computer.",
        )
        if st.button(
            "Search YouTube",
            key="tab_youtube_search_open_btn",
            type="secondary",
            width="stretch",
        ):
            st.session_state[_YOUTUBE_OPEN_KEY] = True
            st.rerun()
        if st.session_state.get(_YOUTUBE_OPEN_KEY):
            _youtube_search_dialog()

        selected_url = str(st.session_state.get(_YOUTUBE_URL_KEY) or "").strip()
        if selected_url:
            selected_title = str(st.session_state.get(_YOUTUBE_TITLE_KEY) or "YouTube video")
            selected_duration = format_youtube_duration(
                st.session_state.get(_YOUTUBE_DURATION_KEY)
            )
            chip_cols = st.columns([4, 1, 1], vertical_alignment="center")
            with chip_cols[0]:
                st.markdown(f"**{selected_title}**")
                if selected_duration:
                    st.caption(selected_duration)
            with chip_cols[1]:
                if st.button("Change", key="tab_youtube_change", type="secondary", width="stretch"):
                    st.session_state[_YOUTUBE_OPEN_KEY] = True
                    st.rerun()
            with chip_cols[2]:
                if st.button("Remove", key="tab_youtube_remove", type="secondary", width="stretch"):
                    for key in (_YOUTUBE_URL_KEY, _YOUTUBE_TITLE_KEY, _YOUTUBE_DURATION_KEY):
                        st.session_state.pop(key, None)
                    st.rerun()

        media_url = st.text_input(
            "Paste media URL",
            key=_MEDIA_URL_KEY,
            help="YouTube watch link or a direct audio/video file URL (.mp3, .wav, .flac, …).",
            placeholder="https://…/song.mp3 or YouTube URL",
        ).strip()
        source_url = selected_url or media_url

        upload_duration: float | None = None
        upload_path_for_trim: Path | None = None
        if uploaded is not None:
            st.audio(uploaded)
            st.caption(_GUITAR_CAUTION)
            try:
                saved_preview = save_upload(uploaded)
                upload_path_for_trim = saved_preview
                upload_duration = probe_duration_sec(saved_preview)
            except (OSError, ValueError):
                upload_duration = None
            if upload_duration is not None:
                st.caption(f"Duration about {_clock(upload_duration)}.")

        known_duration: float | None = upload_duration
        if known_duration is None:
            raw_yt = st.session_state.get(_YOUTUBE_DURATION_KEY)
            try:
                known_duration = float(raw_yt) if raw_yt not in (None, "") else None
            except (TypeError, ValueError):
                known_duration = None

        convert_clicked = False
        continue_ok = show_convert_action(
            has_file=uploaded is not None, youtube_url=source_url
        )
        if continue_ok:
            title = st.text_input(
                "Title",
                key="tab_pdf_title",
                help="This text appears as the title on the generated tab PDF.",
            )
            tune_col, capo_col = st.columns(2)
            with tune_col:
                tuning_name = st.selectbox("Tuning", list(TUNING_PRESETS), key="tab_setup_tuning")
            with capo_col:
                capo = int(
                    st.selectbox(
                        "Capo",
                        list(range(13)),
                        format_func=_capo_label,
                        key="tab_setup_capo",
                    )
                )
            preset = st.radio(
                "Transcription preset",
                options=["solo", "full_mix"],
                format_func=lambda p: (
                    "Solo / fingerstyle" if p == "solo" else "Full mix"
                ),
                key="tab_transcription_preset",
                horizontal=True,
                help="Solo keeps gentler note filters. Full mix turns on stem separation and mix-aware floors.",
            )
            if st.session_state.get("_tab_last_preset") != preset:
                _apply_transcription_preset(str(preset))
                st.session_state["_tab_last_preset"] = preset
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
                st.caption(
                    "Full mixes often leave guitar bleed and wrong notes. "
                    "Prefer a clean solo-guitar clip when you can."
                )
            convert_disabled = not has_ffmpeg
            if continue_ok and st.button(
                "Convert",
                type="primary",
                key="tab_convert",
                width="stretch",
                disabled=convert_disabled,
            ):
                convert_clicked = True
        else:
            title = str(st.session_state.get("tab_pdf_title") or "Guitar Tab")
            tuning_name = str(st.session_state.get("tab_setup_tuning") or "Standard (EADGBE)")
            capo = int(st.session_state.get("tab_setup_capo") or 0)
            separate_stems = bool(st.session_state.get("tab_separate_stems"))

        with st.expander("Conversion settings", expanded=True):
            if not can_separate:
                st.caption(f"Stem separation unavailable. {DEMUCS_INSTALL_HINT}")
            safer_length = st.checkbox(
                "Safer length (recommended)",
                key="tab_safer_length",
                help=(
                    "Trims long clips before transcription. Tab PDF works best on short "
                    "solo-guitar segments. Uncheck only if you need the full track."
                ),
            )
            max_duration: float | None = None
            full_track_ok = True
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
                if known_duration is not None and known_duration > max_duration:
                    st.warning(
                        f"Only the first {int(max_duration)} seconds will be transcribed "
                        f"(clip is about {known_duration:.0f} s)."
                    )
            else:
                st.caption(
                    "Full track will be processed. This is slow and often worse for Tab PDF."
                )
                full_track_ok = bool(
                    st.checkbox(
                        "I understand this may be very slow / memory-heavy",
                        key="tab_full_track_confirm",
                    )
                )
            trim_start = 0.0
            if uploaded is not None and has_ffmpeg and known_duration and known_duration > 5:
                trim_start = float(
                    st.slider(
                        "Trim start (seconds)",
                        min_value=0.0,
                        max_value=max(0.0, float(known_duration) - 1.0),
                        value=0.0,
                        step=1.0,
                        key="tab_trim_start_sec",
                    )
                )

        tab_model = "htdemucs_6s"
        tab_guitar_refine = False
        tab_guitar_checkpoint = None
        tab_low_end_restore_db = 0.0
        tab_sub_bass_debleed = False
        tab_bleed_gate = False
        tab_adaptive_fold_gain = False
        tab_guitar_ensemble = False
        mix_aware = bool(st.session_state.get("tab_mix_aware", separate_stems))
        tempo_override = 0.0
        onset_threshold = 0.5
        frame_threshold = 0.3

        with st.expander("Advanced", expanded=False):
            expert = st.checkbox(
                "Expert options",
                key="tab_expert_options",
                help="Show engine surgery controls and raw transcription thresholds.",
            )
            if separate_stems and can_separate:
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
                roformer_cap = roformer_max_audio_sec(get_desktop_probe())
                if tab_model == "bs_roformer_sw" and known_duration and known_duration > roformer_cap:
                    st.warning(
                        f"RoFormer limit on this machine is {roformer_cap:.0f} s; "
                        f"this clip is about {known_duration:.0f} s. Shorten the section or use Demucs."
                    )
                    if st.button("Use Demucs instead", key="tab_switch_demucs"):
                        st.session_state["tab_guitar_engine"] = "guitar_demucs_6s"
                        st.rerun()
                if tab_model == "htdemucs_6s":
                    if guitar_ft_ok:
                        if st.checkbox(
                            "Use cached guitar-ft Demucs weights",
                            value=False,
                            key="tab_guitar_ft",
                            help="Uses verified guitar-ft already in TORCH_HOME. Does not download.",
                        ):
                            tab_guitar_checkpoint = "htdemucs_6s_guitar_ft"
                    elif guitar_ft_bad:
                        st.caption(
                            "guitar-ft cache looks corrupt (hash mismatch). "
                            "Re-enable guitar-ft later to re-download the ~330 MB weights."
                        )
                    else:
                        st.caption(
                            "guitar-ft weights appear after a one-time ~330 MB download "
                            "when first used by Demucs guitar-ft."
                        )
                if expert:
                    if "tab_low_end_restore_db" not in st.session_state:
                        st.session_state["tab_low_end_restore_db"] = 0.0
                    if "tab_sub_bass_debleed" not in st.session_state:
                        st.session_state["tab_sub_bass_debleed"] = False
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
                    if tab_low_end_restore_db > 0 and tab_sub_bass_debleed:
                        st.caption(
                            "Low-end restore and bass de-bleed both change low frequencies; use one first."
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
                    if tab_guitar_ensemble and not roformer_ok:
                        st.caption("Ensemble needs the [roformer] extra.")
            if expert:
                mix_aware = st.checkbox(
                    "Mix-aware filtering (stricter note filters)",
                    key="tab_mix_aware",
                    help="When stem separation is on, raises onset/frame floors for full mixes.",
                )
                tempo_override = st.number_input(
                    "Tempo override (BPM, 0 = auto)",
                    min_value=0.0,
                    max_value=240.0,
                    value=0.0,
                    step=1.0,
                    key="tab_tempo_override",
                )
                onset_threshold = st.slider(
                    "Onset threshold", 0.3, 0.9, 0.5, 0.05, key="tab_onset_threshold"
                )
                frame_threshold = st.slider(
                    "Frame threshold", 0.2, 0.8, 0.3, 0.05, key="tab_frame_threshold"
                )
            else:
                mix_aware = bool(st.session_state.get("tab_mix_aware", separate_stems))

    with st.container(key="tab_recent"):
        recent_runs = list_recent_runs("tab_pdf")
        if recent_runs:
            with st.expander("Recent conversions", expanded=False):
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
                            for key in (
                                "tab_result_tuning",
                                "tab_result_capo",
                                "tab_result_transpose",
                                "tab_result_bars",
                            ):
                                st.session_state.pop(key, None)
                            st.rerun()

    if convert_clicked:
        st.session_state.pop("tab_pdf_error", None)
        st.session_state.pop("tab_pdf_error_detail", None)
        st.session_state.pop("tab_pdf_empty_recovery", None)
        if not has_ffmpeg:
            record_failure(st.session_state, FFmpegMissingError(ffmpeg_install_hint()))
            st.rerun()
        if not safer_length and not full_track_ok:
            record_failure(
                st.session_state,
                ValueError("Confirm the full-track warning before converting without Safer length."),
            )
            st.rerun()
        url = source_url.strip()
        if not uploaded and not url:
            record_failure(
                st.session_state,
                ValueError("Upload an audio file, paste a media URL, or pick a YouTube video."),
            )
            st.rerun()
        youtube_url = ""
        audio_path = None
        try:
            if uploaded is not None:
                audio_path = upload_path_for_trim or save_upload(uploaded)
                if trim_start > 0 and has_ffmpeg and audio_path is not None:
                    from audio_to_tab.isolate import _trim_audio as _isolate_trim

                    length = max_duration if max_duration else (known_duration or 90.0)
                    audio_path = _isolate_trim(
                        Path(audio_path), float(length), start_sec=float(trim_start)
                    )
            elif is_youtube_url(url):
                if not validate_youtube_url_shape(url):
                    record_failure(
                        st.session_state,
                        ValueError("That does not look like a specific YouTube video link."),
                    )
                    st.rerun()
                try:
                    probe_youtube_availability(url)
                except YouTubeDownloadError as exc:
                    record_failure(st.session_state, exc)
                    st.rerun()
                youtube_url = url
            elif is_direct_media_url(url):
                dest_dir = run_output_dir()
                audio_path = download_direct_media(url, dest_dir)
            else:
                record_failure(
                    st.session_state,
                    ValueError(
                        "Paste a YouTube video URL or a direct audio/video file link "
                        "(.mp3, .wav, .flac, …)."
                    ),
                )
                st.rerun()
        except (OSError, ValueError, FFmpegMissingError) as exc:
            record_failure(st.session_state, exc)
            st.rerun()

        engine_name = str(st.session_state.get("tab_guitar_engine") or "")
        if (
            separate_stems
            and can_separate
            and engine_name.startswith("guitar_roformer")
            and known_duration is not None
            and known_duration > roformer_max_audio_sec(get_desktop_probe())
            and not safer_length
        ):
            record_failure(
                st.session_state,
                RoFormerTooLongError(
                    known_duration, roformer_max_audio_sec(get_desktop_probe())
                ),
            )
            st.rerun()

        effective_separate = bool(separate_stems) and can_separate
        st.session_state["tab_pdf_pending"] = {
            "audio_path": str(audio_path) if audio_path else "",
            "youtube_url": youtube_url,
            "title": title or "Guitar Tab",
            "tuning_name": str(tuning_name),
            "capo": int(capo),
            "separate_stems": effective_separate,
            "skipped_separation": bool(separate_stems) and not can_separate,
            "max_duration_sec": max_duration,
            "mix_aware": bool(mix_aware),
            "onset_threshold": float(onset_threshold),
            "frame_threshold": float(frame_threshold),
            "tempo_override": float(tempo_override),
            "model": tab_model,
            "guitar_refine": bool(tab_guitar_refine),
            "guitar_checkpoint": tab_guitar_checkpoint,
            "low_end_restore_db": float(tab_low_end_restore_db),
            "sub_bass_debleed": bool(tab_sub_bass_debleed),
            "bleed_gate": bool(tab_bleed_gate),
            "adaptive_fold_gain": bool(tab_adaptive_fold_gain),
            "guitar_ensemble": bool(tab_guitar_ensemble),
        }
        st.rerun()

    error = st.session_state.get("tab_pdf_error")
    if error and not st.session_state.get("tab_pdf_artifacts"):
        st.error(error)
        if st.session_state.get("tab_pdf_empty_recovery"):
            cols = st.columns(2)
            with cols[0]:
                if st.button("Use Solo / fingerstyle preset", key="tab_empty_solo"):
                    st.session_state["tab_transcription_preset"] = "solo"
                    _apply_transcription_preset("solo")
                    st.session_state["tab_expert_options"] = True
                    st.session_state.pop("tab_pdf_error", None)
                    st.session_state.pop("tab_pdf_error_detail", None)
                    st.session_state.pop("tab_pdf_empty_recovery", None)
                    st.rerun()
            with cols[1]:
                if st.button("Open Expert thresholds", key="tab_empty_expert"):
                    st.session_state["tab_expert_options"] = True
                    st.session_state["tab_mix_aware"] = False
                    st.rerun()
        if detail := st.session_state.get("tab_pdf_error_detail"):
            with st.expander("Technical details"):
                st.code(detail)



def _execute_pending() -> None:
    pending = st.session_state.get("tab_pdf_pending")
    if not isinstance(pending, dict):
        st.session_state.pop("tab_pdf_pending", None)
        return
    title = str(pending.get("title") or "Guitar Tab")
    st.markdown(
        f'<div class="studio-run-title"><h1>{escape(title)}</h1></div>',
        unsafe_allow_html=True,
    )
    raw_max = pending.get("max_duration_sec")
    max_duration = None if raw_max in (None, "") else float(raw_max)
    tempo_override = float(pending.get("tempo_override") or 0.0)
    config = PipelineConfig(
        separate_stems=bool(pending.get("separate_stems")),
        max_duration_sec=max_duration,
        title=title,
        mix_aware_filtering=bool(pending.get("mix_aware", True)),
        onset_threshold=float(pending.get("onset_threshold") or 0.5),
        frame_threshold=float(pending.get("frame_threshold") or 0.3),
        tempo_bpm_override=tempo_override if tempo_override > 0 else None,
        model=str(pending.get("model") or "htdemucs_6s"),
        guitar_refine=bool(pending.get("guitar_refine")),
        guitar_checkpoint=pending.get("guitar_checkpoint") or None,
        low_end_restore_db=float(pending.get("low_end_restore_db") or 0.0),
        sub_bass_debleed=bool(pending.get("sub_bass_debleed")),
        bleed_gate=bool(pending.get("bleed_gate")),
        adaptive_fold_gain=bool(pending.get("adaptive_fold_gain")),
        guitar_ensemble=bool(pending.get("guitar_ensemble")),
        tuning_name=str(pending.get("tuning_name") or "Standard (EADGBE)"),
        capo=int(pending.get("capo") or 0),
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

    audio_raw = str(pending.get("audio_path") or "").strip()
    audio_path = Path(audio_raw) if audio_raw else None
    url = str(pending.get("youtube_url") or "").strip() or None
    output_dir = run_output_dir()
    try:
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
        st.session_state["tab_pdf_title"] = title
        st.session_state["tab_pdf_skipped_separation"] = bool(pending.get("skipped_separation"))
        st.session_state["tab_pdf_source_audio_path"] = str(audio_path) if audio_path else None
        st.session_state["tab_pdf_details"] = {
            "onset": config.onset_threshold,
            "frame": config.frame_threshold,
            "mix_aware": config.mix_aware_filtering,
            "separate": config.separate_stems,
        }
        st.session_state["tab_result_tuning"] = config.tuning_name
        st.session_state["tab_result_capo"] = int(config.capo)
        st.session_state["tab_result_transpose"] = 0
        st.session_state["tab_result_bars"] = 4
        st.session_state["tab_pdf_export_sig"] = [config.tuning_name, int(config.capo), 0, 4]
        st.session_state.pop("tab_pdf_error", None)
        st.session_state.pop("tab_pdf_error_detail", None)
        st.session_state.pop("tab_pdf_pending", None)
        write_run_metadata(
            output_dir,
            page="tab_pdf",
            title=title,
            artifacts=artifacts,
        )
        st.rerun()
    except (
        EmptyTranscriptionError,
        YouTubeDownloadError,
        FFmpegMissingError,
        RoFormerTooLongError,
    ) as exc:
        st.session_state.pop("tab_pdf_pending", None)
        record_failure(st.session_state, exc)
        st.rerun()
    except (FileNotFoundError, OSError) as exc:
        logger.warning("Tab PDF could not read the audio file: %s", exc)
        st.session_state.pop("tab_pdf_pending", None)
        record_failure(st.session_state, exc, message="Could not read that audio file.")
        st.rerun()
    except ValueError as exc:
        st.session_state.pop("tab_pdf_pending", None)
        record_failure(st.session_state, exc)
        st.rerun()
    except Exception as exc:
        logger.exception("Unexpected tab conversion error")
        st.session_state.pop("tab_pdf_pending", None)
        record_failure(st.session_state, exc)
        st.rerun()


def main() -> None:
    inject_studio_theme()
    if st.session_state.get("tab_pdf_pending"):
        _execute_pending()
        return
    if st.session_state.get("tab_pdf_artifacts"):
        _render_success(st.session_state["tab_pdf_artifacts"])
        return
    _render_entry()


if __name__ == "__main__":
    main()
