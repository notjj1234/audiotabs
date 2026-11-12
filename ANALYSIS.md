# Audiotabs App Analysis

## Overview
**audiotabs** is a Streamlit-based desktop app that converts audio to guitar tab PDF. It wraps a shared engine (`audio_to_tab`) that handles stem separation, note transcription (Basic Pitch), tablature mapping, and PDF generation. The app supports uploading audio files and searching YouTube for conversion.

---

## Pros (Strengths)

### 1. Well-Structured End-to-End Pipeline
The pipeline in `pipeline.py` has a clear sequential flow:
- **Ingest** → **Stem Separation (optional)** → **Transcribe** (Basic Pitch) → **Tab Mapping** → **PDF Generation**
- Proper `PipelineConfig` dataclass with validation in `__post_init__`
- Progress tracking via callback stages
- Clean artifact return (midi, tab, pdf, result, playback)

### 2. Comprehensive Hardware Probing and Recommendations
`hardware.py` provides thorough host detection:
- CPU/MPS/CUDA availability detection
- RAM measurement (macOS, Windows, Linux)
- Performance core detection on Apple Silicon
- Smart speed/quality/device recommendations based on hardware
- `desktop_recommend()` auto-configures optimal settings for the user's machine
- `lite_auto_choice()` for lightweight mode device/speed selection

### 3. Multiple Stem Separation Backends
Users can choose from several separation models:
- **Demucs** (htdemucs_6s) - default, no extra deps
- **RoFormer-SW** (bs_roformer_sw) - optional, better guitar isolation
- **SCNet** - optional, alternative separation
- **Guitar-FT** - community-trained weights on top of htdemucs_6s (330 MB download)
- **Guitar ensemble** - runs RoFormer on top of Demucs stems (much slower, needs RoFormer)

### 4. Robust YouTube Integration
The yt-dlp-based downloader has multiple fallback strategies:
- Three player client variants (`default,-android_sdkless`, `web_safari,tv_embedded,-android_sdkless`, etc.)
- Automatic yt-dlp cache clearing after HTTP 403 errors
- Separate preview video download for thumbnail rendering
- Detailed error reporting with user-facing messages

### 5. Good UI/UX Design (Streamlit)
- Studio theme with custom CSS (dark panel, accent color #e8a317)
- Progress checklist with state-aware rendering
- Hero header, progress card, result header
- Multiple viewing modes: Tab, Chords, Text, Piano roll
- Chord diagrams in sidebar rail
- Recent runs sidebar for re-opening previous conversions
- File download buttons for pdf, midi, tab, and guitar stem

### 6. Extensive Test Coverage
- 15+ test files covering hardware, pipeline, separation, UI, etc.
- Tests for config defaults, trim audio, isolate config, named stem collection
- Tests for RoFormer backend, guitar-FT weights, sub-bass debleed, bleed gate
- Tests for recommended CPU threads, memory pressure, device resolution
- Good mock-based testing without requiring actual GPU/torch

### 7. Advanced Parameters (for power users)
Hidden behind an "Advanced" expander, but still present:
- Low-end restore (dB boost 0-6 Hz for 60-200Hz)
- Subtractive bass de-bleed
- Spectral bleed gate
- Adaptive fold gain
- Cross-model guitar ensemble
- Onset/frame threshold sliders
- Tempo override
- Guitar track radio options (with RoFormer/guitar-ft/refine toggles)

### 8. Chord Recognition
`bundle_chords()` extracts chord names from MIDI, with supporting functions for chord detection and display.

### 9. Lyrics Support
Optional lyrics transcription from vocal stem, with skip reason reporting.

### 10. Cross-Platform Support
- Explicitly supports macOS and Windows
- Python 3.10-3.12 compatibility
- CUDA (NVIDIA GPU), MPS (Apple GPU), CPU device options
- Both frozen (packaged) and source run modes

---

## Cons / Flaws (Especially Problematic)

### 1. YouTube Downloader Unreliability (CRITICAL)
The entire YouTube-dependent workflow is fragile:
- **yt-dlp version skew**: YouTube frequently changes its HTML/JS, and yt-dlp must be kept in sync. The pinned version `yt-dlp>=2026.08` may still break.
- **403 retry loop**: The three-player-client retry with cache clearing often fails. The `_is_403_error` check is simplistic (just checks "403" in error text).
- **No fallback to user-uploaded audio**: When YouTube fails, users are forced to upload audio files instead.
- **Search result cap**: `_SEARCH_MAX_FETCH = 50` means very popular songs may not appear in the first 50 results if they're beyond offset+page_size.
- **Disclaimer not prominent**: "FYI: public YouTube links only. No Private or Unlisted YouTube links" is in a caption users may miss.

### 2. RoFormer Audio Length Limit (CRITICAL for Mac Users)
- **90-second limit on low RAM Macs**: `roformer_max_audio_sec()` returns 90s when free RAM < 12 GB (which includes most base M1/M2/M3/M4 Macs).
- **180-second limit only on ≥12 GB RAM Macs** (Pro/Max/Ultra).
- Users with longer songs on base MacBook Air/MacBook Pro get a `RuntimeError: 90` with no clear path forward.
- The limit is enforced in `_refuse_long_roformer_audio()` and `run_roformer_model()`.
- **No warning before attempting RoFormer** on long audio.

### 3. Demucs Stem Separation Quality Issues
- **Default "fast" quality may produce poor tab results**: Fast mode is quick but produces stems with more musical artifacts, leading to wrong notes in tab.
- **No quality indicator**: Users have no way to know if the stem separation will produce usable tabs for their particular audio.
- **Guitar-ft weights are a 330 MB download that many users won't have**: The community guitar-FT weights (`htdemucs_6s_guitar_ft`) significantly improve guitar isolation but require a separate download. The hint `GUITAR_FT_CACHE_HINT` is non-obvious.
- **Stock Demucs htdemucs_6s was not trained specifically for guitar**: It's a general 6-stem separator; guitar bleed is common.

### 4. Aggressive Transcription Thresholds
When `mix_aware_filtering` is on (default):
- **onset_threshold forced to max(onset, 0.58)** 
- **frame_threshold forced to max(frame, 0.40)**
- **minimum_note_length forced to max(min_len, 90.0 ms)**
These aggressive defaults may:
- Filter out valid notes, especially quiet or short notes
- Produce tabs with too few notes (triggering `EmptyTranscriptionError`)
- Be inappropriate for certain genres (e.g., fingerstyle, classical guitar)

When mix_aware is off, more lenient defaults are used (onset 0.5, frame 0.3, min 58ms), but users may not understand the difference.

### 5. "Safer Length" Trimming Defaults to 90 Seconds
- The default `tab_max_duration_sec = 90` clips audio to 90 seconds maximum.
- Users who uncheck "Safer length (recommended)" to process full tracks:
  - Risk crashes or extremely slow processing
  - May get worse tab results (full mixes have more instrument interference)
  - May hit RoFormer length limits if they also enable stem separation with RoFormer
- The help text says "Tab PDF works best on short solo-guitar segments" but many users may not read it.

### 6. YouTube-Only URL Restriction
- The app **only** accepts YouTube URLs for YouTube-based conversion.
- No support for other video platforms (Vimeo, Dailymotion, etc.).
- No ability to paste a direct media URL for conversion (the `is_direct_media_url` function exists but is not exposed in the UI).
- The disclaimer "Only public YouTube links only. No Private or Unlisted YouTube links" limits usability.

### 7. MIDI Transcription Can Produce Too Few Notes
- `EmptyTranscriptionError` is raised when MIDI has fewer than 3 notes.
- This happens frequently with:
  - Very short audio clips (< 10 seconds)
  - Audio with no clear pitch content
  - Non-guitar audio (e.g., piano, vocals)
- Users get an error message "Too few notes detected for a usable tab. A cleaner solo-guitar clip is needed." but may not understand how to fix it.
- The `minimum_note_length_ms = 58.0` threshold (raised to 90ms in mix_aware mode) may be too strict.

### 8. FFmpeg Dependency (Often Missing)
- `normalize_audio()` requires `ffmpeg` on PATH.
- `_require_ffmpeg()` raises `RuntimeError("ffmpeg is required but not found on PATH")`.
- Many macOS users install ffmpeg via Homebrew, but:
  - Windows users may not have it
  - It's not included in the Python app bundle
  - The error is not caught gracefully in all code paths

### 9. Guitar-FT Weights Download Can Fail
The 330 MB guitar-FT weights download (`download_guitar_ft_weights()`):
- Uses `urllib.request` (no progress bar, no retry with exponential backoff)
- SHA256 hash verification adds complexity
- On failure: "Failed to download guitar-ft weights from {GUITAR_FT_URL}"
- The hint says to "run audio-isolate --guitar-checkpoint htdemucs_6s_guitar_ft" but users may not have that CLI tool.
- If the download fails, users get a RuntimeError and cannot use guitar-FT mode.

### 10. Complex Interacting Options in Advanced Expander
The "Advanced" expander contains many interacting parameters:
- `low_end_restore_db` (0-6 dB)
- `sub_bass_debleed` (checkbox)
- `bleed_gate` (checkbox)
- `adaptive_fold_gain` (checkbox)
- `guitar_ensemble` (checkbox, needs RoFormer)
- `guitar_engine` radio (htdemucs_6s, guitar_roformer, guitar_roformer_refine)
- `tab_model` (htdemucs_6s, bs_roformer_sw, melband_roformer_guitar)
- `guitar_refine` (needs RoFormer)
- `guitar_checkpoint` (guitar-ft weights)
- `mix_aware` (affects transcription thresholds)
- `tempo_override`, `onset_threshold`, `frame_threshold`

These interact in complex ways that even experienced users may not fully understand. For example:
- `guitar_ensemble` + `bleed_gate` + specific model combinations may produce unexpected results.
- `low_end_restore_db` + `sub_bass_debleed` both affect low frequencies but may conflict.
- The radio `guitar_engine` selection determines `tab_model`, which determines available checkboxes.

### 11. No Audio Preview Before Conversion
Users upload audio files but cannot preview them within the app to verify:
- It's the correct clip
- It's actual guitar audio (not piano, vocals, etc.)
- The duration is appropriate
- The quality is sufficient

The uploaded audio is just displayed via `st.audio(uploaded)` but there's no mechanism to listen to a preview before hitting "Convert".

### 12. YouTube Search Limited and Error-Prone
- Search uses `ytsearchN:query` with N capped at 50 results total.
- No API key support (public yt-dlp only), so results depend on yt-dlp's ability to parse YouTube's changing HTML.
- Search errors are caught but displayed as `st.warning()` which users may miss.
- The YouTube search dialog has "Previous" and "Next" pagination but is limited by the 50-result cap.

### 13. Progress Tracking Can Be Misleading
The progress checklist shows stages (ingest, separate, transcribe, tab, pdf, chords, lyrics, done), but:
- Stage names may not match what the user expects (e.g., "Detecting notes" is Basic Pitch, not a generic "detector").
- The progress may jump or stall depending on optional backend availability.
- No stage-specific timing or ETA.
- "Separating stems" may show as active but then fail silently later.

### 14. YouTube URL Validation Is Minimal
- `is_youtube_url()` checks hostname ends with `youtube.com` or `youtu.be`.
- No validation that the URL is playable or that the video has audio content.
- Users can select a YouTube URL that later fails during download with unhelpful error messages.

### 15. No Batch or History Persistence Across Sessions
- Recent runs are stored but cleared when the app restarts.
- No persistent library of conversions.
- Each session starts fresh.

### 16. MIDI Cleanup May Remove Valid Notes
The `cleanup_midi()` function (called during transcription) uses `CleanupConfig` with `min_velocity` and `min_duration_sec` thresholds. The mix-aware config raises these thresholds (to max(cfg.min_velocity, base.min_velocity) and max(cfg.min_duration_sec, base.min_duration_sec)), which may filter out legitimate quiet notes or short rhythmic figures.

### 17. Lyrics Transcription Is Optional and May Fail Silently
- `transcribe_lyrics()` is wrapped in a try/except that logs warning and sets `lyric_lines = []` on failure.
- Users may not realize lyrics were not transcribed.
- `lyrics_skip_reason()` reports the reason, but it may be cryptic.

### 18. Tempo Detection Can Be Wrong
- `resolve_tempo()` estimates BPM from audio or MIDI.
- No user-facing indication of confidence level (except in the "Transcription details" expander).
- `tempo_bpm_override` exists but users may not know to use it.
- Wrong tempo leads to incorrect tab timing.

### 19. Key Detection Depends on MIDI Post-Processing
- `key_for_midi()` determines the song key from the cleaned MIDI.
- If the MIDI cleanup removes key-relevant notes, the key detection may be wrong.
- No user override for key (transpose knob exists but is separate from key detection).

### 20. PDF Rendering May Produce Poor Layouts for Certain Tab Formats
- The tab SVG rendering uses hardcoded ink/line colors (`_INK = "#e8eaef"`, `_LINE = "#3d4553"`).
- No user customization of tab appearance (staff lines, fret numbers, etc.).
- Bars-per-line selector only goes 1-8, may not suit all songs.

### 21. No Integration with Hugging Face Hub for Model Updates
- Models (Demucs, RoFormer, Basic Pitch) are fixed at install time.
- No easy way for users to update to newer model versions.
- Guitar-FT weights have a hardcoded SHA256 and URL.

### 22. Desktop-Specific Issues (Frozen Build)
- The `packaging/` directory contains Windows frozen build configuration.
- Edition detection (`desktop_edition()`) reads from `edition.txt` or `AUDIO_TOOLS_EDITION` env var.
- CUDA-only edition has no CPU fallback option (intentional, but limits usability on machines without NVIDIA GPU).
- The combined ("both") edition lists both GPU and CPU but may mislead users about what's available.

### 23. Memory Pressure Detection Edge Cases
- On macOS, `probe_memory_pressure()` uses `vm_stat` which can be inaccurate under certain configurations (encrypted swap, certain macOS versions).
- `memory_pressure_is_tight()` may give false positives/negatives depending on the host's memory configuration.
- The `MPS_MIN_RAM_GB = 12.0` gate may incorrectly restrict MPS on some 8 GB Macs that could handle RoFormer with reduced performance.

### 24. No Dark/Light Theme Adaptation Beyond Studio CSS
- The studio CSS targets `.stApp` and data-testid selectors but may not cover all Streamlit components.
- Some Streamlit elements may use light mode colors that contrast poorly with the dark studio theme.

### 25. Code Quality Concerns
- **Import cycles**: The graph report notes "None detected" but some modules import from each other in ways that could cause issues.
- **Global state**: `hardware.py` uses `_cached_probe` and `_cached_cpu_brand` globals that require `reset_desktop_probe_cache()` in tests.
- **Suppressed errors**: Several `except Exception` blocks log but may mask real issues.
- **Magic numbers**: Thresholds like `0.58`, `0.40`, `90.0` appear as literals rather than configurable constants in some places.
- **Type ignore comments**: Several files have `# type: ignore` or `# noqa` comments suggesting type checking issues.

---

## Summary of Critical Flaws

| Rank | Flaw | Impact | Fix Priority |
|------|------|--------|-------------|
| 1 | YouTube downloader unreliability | Users can't convert YouTube videos; forced to upload audio | High |
| 2 | RoFormer 90s limit on <12GB RAM Macs | Base Mac users get errors with normal-length songs | High |
| 3 | Demucs guitar stem quality | Tabs have wrong notes, especially with "fast" quality | Medium |
| 4 | Aggressive transcription thresholds | EmptyTranscriptionError for valid audio; notes filtered out | Medium |
| 5 | Safer length 90s default | Users clip songs inappropriately or get worse results | Medium |
| 6 | YouTube-only URL restriction | Limits platform compatibility | Medium |
| 7 | FFmpeg dependency | App crashes on machines without ffmpeg | Medium |
| 8 | Guitar-FT weights download failures | Users can't access improved guitar separation | Medium |
| 9 | Complex interacting advanced options | Power users may configure contradictory settings | Low |
| 10 | No audio preview | Users may convert wrong clips unaware | Low |

---

## Recommendations

1. **Improve YouTube reliability**: Add more player client variants, better 403 detection, and a clearer path to fallback to audio upload.
2. **Warn before RoFormer on long audio**: Show a warning dialog when the user enables stem separation with RoFormer on audio longer than the platform limit.
3. **Better default transcription thresholds**: Make mix_aware defaults less aggressive, or provide a clear explanation of why they're strict.
4. **Make safer length configurable**: Allow users to set their own max duration, with a warning when exceeding 90 seconds.
5. **Expose YouTube direct media URL option**: Add a URL paste field alongside the YouTube search.
6. **Bundle ffmpeg or provide clear install instructions**: Especially for Windows users.
7. **Add progress indicator for guitar-FT weights download**: Show download progress and retry capability.
8. **Simplify advanced options UI**: Group related options, add tooltips explaining interactions, or move some to a " expert mode" toggle.
9. **Add audio preview functionality**: Allow users to trim/listen to uploads before conversion.
10. **Add model update mechanism**: At minimum, check for newer model versions on startup.