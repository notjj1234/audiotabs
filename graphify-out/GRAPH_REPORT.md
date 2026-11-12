# Graph Report - audiotabs  (2026-11-12)

## Corpus Check
- 62 files · ~66,289 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .toml 1, .ico 1)

## Summary
- 1425 nodes · 3379 edges · 84 communities (63 shown, 21 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 299 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `921eadcc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- numpy
- lead_rhythm.py
- mixer.py
- test_scnet.py
- tab_bundle.py
- notation_view.py
- test_pipeline_guitar.py
- roformer.py
- test_ingest.py
- download_youtube_audio
- tab_pdf.py
- isolate.py
- pathlib
- search_youtube_videos
- audio_to_tab/pipeline.py
- test_hardware.py
- separate.py
- tab_generate.py
- test_result_studio.py
- hardware.py
- notation_view.py
- HostProbe
- test_studio_ui.py
- Path
- player_html
- separate_stems
- common.py
- pdf_render.py
- test_youtube_search.py
- launcher.py
- test_tab.py
- rebake_metronome_artifact
- separate_guitar_stem
- tempo.py
- Cons / Flaws (Especially Problematic)
- Path
- player_bar.py
- desktop_recommend
- Any
- _execute_pending
- lite_auto_choice
- normalize_audio
- get_desktop_probe
- lyrics.py
- Studio UI redesign
- ingest.py
- YouTubeDownloadError
- audiotabs
- typing
- recommended_cpu_threads
- format_region_label
- metronome.py
- test_download_403_twice_raises_user_error
- _YoutubeFileLogger
- detect_present_stems
- _scnet_architecture_module
- run_roformer_model
- blend_guitar_stems
- test_download_does_not_require_js_runtime
- generate_metronome_stem
- analyze_bass_bleed
- apply_bleed_gate
- test_download_retries_after_403_then_succeeds
- PipelineConfig
- lite_detected_caption
- audio-to-tab-pdf
- Path
- _is_403_error
- argparse
- metronome_grid_times
- test_download_guitar_ft_retries_then_succeeds
- _require_ffmpeg
- os
- test_failure_ux_contracts.py
- test_download_guitar_ft_resumes_partial_part_file
- test_download_403_retry_does_not_delete_unrelated_wav
- test_download_retries_three_clients_on_403
- LowEndRestoreDiagnostics

## God Nodes (most connected - your core abstractions)
1. `separate_stems()` - 43 edges
2. `_render_entry()` - 37 edges
3. `HostProbe` - 35 edges
4. `separate_guitar_stem()` - 34 edges
5. `run_pipeline()` - 30 edges
6. `Cons / Flaws (Especially Problematic)` - 26 edges
7. `TabDocument` - 24 edges
8. `generate_metronome_stem()` - 24 edges
9. `midi_to_tab()` - 23 edges
10. `split_lead_rhythm_guitar()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `1. Well-Structured End-to-End Pipeline` --references--> `PipelineConfig`  [INFERRED]
  ANALYSIS.md → src/audio_to_tab/pipeline.py
- `9. Guitar-FT Weights Download Can Fail` --references--> `download_guitar_ft_weights()`  [INFERRED]
  ANALYSIS.md → src/audio_to_tab/separate.py
- `8. Chord Recognition` --references--> `bundle_chords()`  [INFERRED]
  ANALYSIS.md → src/audio_to_tab/tab_bundle.py
- `18. Tempo Detection Can Be Wrong` --references--> `resolve_tempo()`  [INFERRED]
  ANALYSIS.md → src/audio_to_tab/tempo.py
- `14. YouTube URL Validation Is Minimal` --references--> `is_youtube_url()`  [INFERRED]
  ANALYSIS.md → src/audio_to_tab/ingest.py

## Import Cycles
- None detected.

## Communities (84 total, 21 thin omitted)

### Community 0 - "numpy"
Cohesion: 0.11
Nodes (20): align_click_grid_to_downbeat(), apply_click_rate(), _beat_band_energy(), _beat_impulse_ratios(), _beat_local_rms(), _best_phase(), click_grid_for_playback(), _downbeat_phase() (+12 more)

### Community 1 - "lead_rhythm.py"
Cohesion: 0.08
Nodes (27): _average_role_features(), build_midside_pair(), build_register_pair(), build_spatial_pair(), build_spectral_pair(), _CandidatePair, classify_lead_rhythm_roles(), _dominant_pitch_estimate() (+19 more)

### Community 2 - "mixer.py"
Cohesion: 0.08
Nodes (20): apply_pan(), apply_playback_transform(), apply_true_peak_ceiling(), audible_stems(), clamp_pan(), clamp_playback_semitones(), db_to_linear(), default_muted_for() (+12 more)

### Community 3 - "test_scnet.py"
Cohesion: 0.07
Nodes (16): _demix_scnet(), download_scnet_weights(), _load_audio_stereo(), _msst_normalize(), run_scnet_model(), scnet_weights_path(), _torch_device(), _write_stem() (+8 more)

### Community 4 - "tab_bundle.py"
Cohesion: 0.10
Nodes (23): 19. Key Detection Depends on MIDI Post-Processing, _capo_tuning(), ChordHit, chords_from_midi(), _collapse(), _correlate(), detect_key(), _frets_for() (+15 more)

### Community 5 - "notation_view.py"
Cohesion: 0.19
Nodes (13): _slice_document(), quantize_tab_document(), quantize_time(), sec_per_sixteenth(), _finite(), tab_document_from_dict(), tab_document_to_dict(), tab_measure_spans() (+5 more)

### Community 6 - "test_pipeline_guitar.py"
Cohesion: 0.11
Nodes (23): test_apply_guitar_low_end_recovery_default_off(), test_apply_low_end_restore_boost_raises_low_band_share(), test_apply_low_end_restore_zero_db_is_noop(), test_apply_sub_bass_debleed_reduces_low_band_share(), test_collect_named_stems_filters_to_requested_names(), test_guitar_ft_weights_cached_false_when_missing(), test_isolate_config_clamps_low_end_restore_db(), test_isolate_config_sub_bass_debleed_defaults_off() (+15 more)

### Community 7 - "roformer.py"
Cohesion: 0.13
Nodes (19): bs_roformer_sw_paths(), _cap_cpu_threads(), _demix_track(), download_bs_roformer_sw_weights(), download_melband_guitar_weights(), download_sha256_file(), file_sha256(), _instantiate_bs_roformer_model() (+11 more)

### Community 8 - "test_ingest.py"
Cohesion: 0.11
Nodes (12): format_youtube_duration(), _resolve_downloaded_wav(), _title_stem(), test_download_youtube_preview_rejects_non_youtube(), test_download_youtube_rejects_non_youtube(), test_format_youtube_duration(), test_resolve_downloaded_wav_no_candidates_raises(), test_resolve_downloaded_wav_no_title_match_uses_newest_normalized() (+4 more)

### Community 9 - "download_youtube_audio"
Cohesion: 0.16
Nodes (13): _cleanup_attempt_artifacts(), _clear_ytdlp_cache(), download_youtube_audio(), download_youtube_preview_video(), _snapshot_dir(), _take_preview_download(), _unlink_quiet(), _youtube_debug_enabled() (+5 more)

### Community 10 - "tab_pdf.py"
Cohesion: 0.13
Nodes (19): ffmpeg_available(), default_guitar_track_option(), guitar_track_radio_ids(), normalize_guitar_track_selection(), _apply_transcription_preset(), _capo_label(), _clear_song(), _clock() (+11 more)

### Community 11 - "isolate.py"
Cohesion: 0.11
Nodes (19): analyze_guitar_stem_quality(), apply_fold_other_gain_search(), apply_fold_other_into_guitar(), apply_low_end_restore(), _apply_peak_limit(), apply_sub_bass_debleed(), _bandpass_audio(), _drop_other_stem() (+11 more)

### Community 12 - "pathlib"
Cohesion: 0.12
Nodes (9): 16. MIDI Cleanup May Remove Valid Notes, _cap_onset_density(), cleanup_midi(), CleanupConfig, estimate_tempo_bpm(), merge_instruments_to_one(), mix_aware_cleanup_config(), solo_guitar_cleanup_config() (+1 more)

### Community 13 - "search_youtube_videos"
Cohesion: 0.08
Nodes (8): search_youtube_videos(), _thumbnail_url_for_entry(), test_search_youtube_videos_clamps_fetch_to_50(), test_search_youtube_videos_offset_slices_page(), test_search_youtube_videos_rejects_blank_query(), test_search_youtube_videos_uses_ytsearch_and_maps_hits(), test_search_youtube_videos_wraps_backend_errors(), test_thumbnail_url_prefers_entry_then_cdn_fallback()

### Community 14 - "audio_to_tab/pipeline.py"
Cohesion: 0.18
Nodes (8): count_midi_notes(), _require_usable_transcription(), run_pipeline(), _separate_progress_label(), _trim_audio(), subprocess_run_kwargs(), tab_document_for(), test_pipeline_trim_raises_on_ffmpeg_failure()

### Community 15 - "test_hardware.py"
Cohesion: 0.11
Nodes (21): desktop_device_options(), resolve_desktop_speed(), _cpu_edition_by_default(), test_both_edition_balanced_speed_uses_cpu_when_no_nvidia_gpu(), test_both_edition_faster_speed_uses_cpu_when_no_nvidia_gpu(), test_both_edition_offers_cuda_even_without_gpu(), test_both_edition_windows_device_options_gpu_first(), test_cuda_edition_windows_device_options_cuda_only() (+13 more)

### Community 16 - "separate.py"
Cohesion: 0.11
Nodes (10): install_soundfile_writer(), apply_recommended_cpu_threads(), effective_demucs_segment(), remap_guitar_ft_state_dict(), run_demucs(), _run_demucs_guitar_cli(), JobAborted, run_process() (+2 more)

### Community 17 - "tab_generate.py"
Cohesion: 0.12
Nodes (18): Global Constraints, Rulings, Tab result page implementation plan, Task 1: Staff wrap, Task 2: Chords, capo, transpose, tuning, Task 4: Pipeline stages, Task 6: Verify, _filter_playable_positions() (+10 more)

### Community 18 - "test_result_studio.py"
Cohesion: 0.18
Nodes (18): Review Focus, placed_note(), clamp_playback_rate(), download_menu(), downloads_after_run(), test_capo_and_transpose_shift_pitch_and_chord_names(), test_chord_names_follow_grouped_midi(), test_consecutive_identical_chords_collapse() (+10 more)

### Community 19 - "hardware.py"
Cohesion: 0.10
Nodes (15): 23. Memory Pressure Detection Edge Cases, _both_edition_windows(), _cuda_only_edition_windows(), _darwin_available_ram_gb(), _darwin_swap_used_gb(), lite_accelerator_available(), lite_device_choice_ids(), lite_device_plain_label() (+7 more)

### Community 20 - "notation_view.py"
Cohesion: 0.13
Nodes (13): measure_count(), measure_rows(), _measure_seconds(), piano_roll_svg(), screen_tab_text(), tab_staff_svg(), _split_body(), strip_ansi_csi() (+5 more)

### Community 21 - "HostProbe"
Cohesion: 0.18
Nodes (14): 2. RoFormer Audio Length Limit (CRITICAL for Mac Users), desktop_recommend_caption(), desktop_system_summary(), HostProbe, lite_auto_speed_id(), roformer_max_audio_sec(), _refuse_long_roformer_audio(), test_cuda_edition_system_summary_shows_nvidia_not_cpu() (+6 more)

### Community 22 - "test_studio_ui.py"
Cohesion: 0.09
Nodes (13): test_entry_screen_css_has_one_hierarchy(), test_entry_screen_offers_two_sources(), test_hero_html_can_include_app_icon(), test_hero_html_is_title_only(), test_hero_sits_on_the_ground(), test_progress_row_puts_the_state_after_the_label(), test_result_header_html_shows_meta(), test_score_panel_is_dark() (+5 more)

### Community 23 - "Path"
Cohesion: 0.16
Nodes (12): download_guitar_ft_weights(), _guitar_ft_digest_sidecar(), guitar_ft_weights_cached(), guitar_ft_weights_corrupt(), guitar_ft_weights_path(), guitar_ft_weights_sha256(), load_guitar_ft_state_dict(), run_demucs_guitar_ft_inprocess() (+4 more)

### Community 24 - "player_html"
Cohesion: 0.17
Nodes (14): File map, Global Constraints, Review Focus, Studio UI Hybrid Shell Implementation Plan, Task 1: Studio theme tokens, Task 2: Progress / hero shells, Task 3: Dark studio player, Task 5: Full verification (+6 more)

### Community 25 - "separate_stems"
Cohesion: 0.11
Nodes (18): progress(), separate_progress_message(), _abort_if(), _collect_stem_wavs(), IsolateConfig, _mark_stage_complete(), _maybe_refine_guitar(), resolve_demucs_overlap() (+10 more)

### Community 26 - "common.py"
Cohesion: 0.16
Nodes (12): app_icon_data_uri(), app_icon_png(), app_version(), ensure_src_path(), list_recent_runs(), max_upload_caption(), max_upload_mb(), _resolve_data_dir() (+4 more)

### Community 27 - "pdf_render.py"
Cohesion: 0.11
Nodes (10): main(), main(), clamp_bars_per_line(), _count_measures(), _events_in_measure(), render_structured_tab_pdf(), render_tab_pdf(), tab_document_to_pdf() (+2 more)

### Community 28 - "test_youtube_search.py"
Cohesion: 0.12
Nodes (13): YouTubeSearchHit, test_hit_meta_joins_channel_and_duration(), test_hit_meta_keeps_only_the_parts_that_exist(), test_hit_state_serializes_a_search_hit(), test_normalize_page_accepts_int_and_numeric_string(), test_normalize_page_rejects_missing_and_out_of_range(), _close_youtube_search(), _run_youtube_search() (+5 more)

### Community 29 - "launcher.py"
Cohesion: 0.17
Nodes (13): health_ok(), log(), main(), on_closed(), on_shown(), pick_port(), port_free(), start_server() (+5 more)

### Community 30 - "test_tab.py"
Cohesion: 0.23
Nodes (9): test_cleanup_midi_writes_filtered(), test_dense_midi_tempo_not_inflated(), test_estimate_tempo_bpm_delegates_to_robust(), test_fret_assignment_avoids_large_jump_in_sequence(), test_midi_to_tab_simple(), test_onset_density_cap(), test_pdf_render(), test_resolve_tempo_override() (+1 more)

### Community 31 - "rebake_metronome_artifact"
Cohesion: 0.15
Nodes (16): analysis_wav_for_downbeat(), attach_metronome_artifact(), _bpm_curve_from_payload(), coerce_metronome_rate(), coerce_metronome_render_options(), coerce_metronome_sound(), load_metronome_diagnostics(), _metronome_source_candidates() (+8 more)

### Community 32 - "separate_guitar_stem"
Cohesion: 0.17
Nodes (9): apply_guitar_low_end_recovery(), is_demucs_available(), separate_guitar_stem(), _apply_low_end_recovery(), _maybe_bleed_gate(), _maybe_fold_other(), test_apply_guitar_low_end_recovery_debleed_writes_diagnostics(), test_separate_guitar_stem_rejects_unknown_fold_mode() (+1 more)

### Community 33 - "tempo.py"
Cohesion: 0.29
Nodes (5): _clamp_bpm(), estimate_tempo_from_audio(), estimate_tempo_from_midi_robust(), resolve_tempo(), TempoEstimate

### Community 34 - "Cons / Flaws (Especially Problematic)"
Cohesion: 0.06
Nodes (39): 10. Complex Interacting Options in Advanced Expander, 10. Cross-Platform Support, 11. No Audio Preview Before Conversion, 12. YouTube Search Limited and Error-Prone, 13. Progress Tracking Can Be Misleading, 15. No Batch or History Persistence Across Sessions, 18. Tempo Detection Can Be Wrong, 1. Well-Structured End-to-End Pipeline (+31 more)

### Community 35 - "Path"
Cohesion: 0.11
Nodes (9): ensure_guitar_prerefine_backup(), format_region_label_filename(), merge_two_pass_stems(), probe_duration_sec(), save_guitar_refined_backup(), _trim_audio(), is_guitar_refine_available(), run_guitar_refine() (+1 more)

### Community 36 - "player_bar.py"
Cohesion: 0.13
Nodes (12): Task 3: Views, bars per line, downloads, player model, align_chords_to_lyrics(), chord_diagram_svg(), player_click_times(), player_peaks(), player_source_labels(), player_speed(), synth_source_available() (+4 more)

### Community 37 - "desktop_recommend"
Cohesion: 0.14
Nodes (11): desktop_recommend(), is_low_ram(), _preferred_gpu(), test_auto_cpu_or_mac_without_mps_is_faster_cpu(), test_auto_low_ram_mps_mac_stays_cpu(), test_auto_low_ram_with_cuda_stays_on_gpu(), test_auto_mps_mac_is_balanced_gpu(), test_auto_windows_cuda_is_balanced_gpu() (+3 more)

### Community 38 - "Any"
Cohesion: 0.15
Nodes (4): AdaptiveFoldGainDiagnostics, FoldOtherDiagnostics, GuitarStemQualityDiagnostics, LowEndRecoveryDiagnostics

### Community 39 - "_execute_pending"
Cohesion: 0.14
Nodes (13): 4. Aggressive Transcription Thresholds, 7. MIDI Transcription Can Produce Too Few Notes, Task 4: Wire `tab_pdf.py` to the studio shell, Task 5: Streamlit result page, EmptyTranscriptionError, apply_progress(), new_checklist(), test_checklist_marks_a_skip_and_ignores_unknown_stages() (+5 more)

### Community 40 - "lite_auto_choice"
Cohesion: 0.19
Nodes (8): 2. Comprehensive Hardware Probing and Recommendations, lite_auto_choice(), lite_auto_device(), memory_pressure_is_tight(), MemoryPressure, test_lite_auto_choice_keeps_gpu_under_memory_pressure(), test_memory_pressure_is_tight_thresholds(), test_probe_memory_pressure_darwin_parses_vm_stat()

### Community 41 - "normalize_audio"
Cohesion: 0.33
Nodes (3): normalize_audio(), test_normalize_audio_deletes_temp_on_failure(), test_normalize_audio_temp_output_is_caller_owned()

### Community 42 - "get_desktop_probe"
Cohesion: 0.13
Nodes (11): ensure_cuda_available(), get_desktop_probe(), get_desktop_probe_without_torch(), probe_cpu_brand(), probe_ram_gb(), probe_torch(), resolve_safe_device(), test_ensure_cuda_available_fail_closed() (+3 more)

### Community 43 - "lyrics.py"
Cohesion: 0.36
Nodes (5): 17. Lyrics Transcription Is Optional and May Fail Silently, _import_transcriber(), lyrics_skip_reason(), transcribe_lyrics(), test_lyrics_skip_reason_without_a_vocal_stem()

### Community 44 - "Studio UI redesign"
Cohesion: 0.20
Nodes (9): Anti-goals, Approaches, Constraints, Design (builder), Goals, Intent, Layout decisions (2026-11-11), Non-goals (+1 more)

### Community 45 - "ingest.py"
Cohesion: 0.12
Nodes (14): 14. YouTube URL Validation Is Minimal, 6. YouTube-Only URL Restriction, download_direct_media(), is_direct_media_url(), is_youtube_url(), _looks_like_video_id(), validate_youtube_url_shape(), _watch_url_from_entry() (+6 more)

### Community 46 - "YouTubeDownloadError"
Cohesion: 0.11
Nodes (7): FFmpegMissingError, probe_youtube_availability(), YouTubeDownloadError, YouTubeSearchError, RoFormerTooLongError, user_facing_message(), test_probe_youtube_unavailable_raises_user_error()

### Community 47 - "audiotabs"
Cohesion: 0.25
Nodes (7): About, audiotabs, Quickstart, Quickstart, Table of contents, Tester, Tester

### Community 49 - "recommended_cpu_threads"
Cohesion: 0.25
Nodes (6): cpu_thread_env(), _physical_perf_cores(), recommended_cpu_threads(), test_cpu_thread_env_keys(), test_recommended_cpu_threads_clamps_by_ram(), threads_for()

### Community 50 - "format_region_label"
Cohesion: 0.22
Nodes (4): format_region_label(), format_time_sec(), RegionError, resolve_region()

### Community 51 - "metronome.py"
Cohesion: 0.13
Nodes (12): collapse_brief_octave_runs(), curve_confidence(), detect_beats_per_measure(), estimate_meter(), _fixed_window_rms(), _median_filter_1d(), MeterEstimate, octave_snap_bpm() (+4 more)

### Community 54 - "detect_present_stems"
Cohesion: 0.29
Nodes (4): detect_present_stems(), _rms_to_dbfs(), _stem_rms(), StemPresence

### Community 55 - "_scnet_architecture_module"
Cohesion: 0.29
Nodes (5): load_scnet_model(), _scnet_architecture_module(), __init__(), test_load_scnet_model_strict(), test_scnet_architecture_output_shape()

### Community 56 - "run_roformer_model"
Cohesion: 0.12
Nodes (11): _canonical_stem_name(), collect_canonical_stems(), collect_named_stems(), is_audio_separator_available(), is_roformer_available(), is_roformer_backend_available(), refine_guitar_from_stems(), run_melband_guitar() (+3 more)

### Community 57 - "blend_guitar_stems"
Cohesion: 0.25
Nodes (4): blend_guitar_stems(), EnsembleGuitarDiagnostics, _log_band_edges(), fake_blend()

### Community 59 - "generate_metronome_stem"
Cohesion: 0.22
Nodes (9): build_click_times(), _conf_at(), _period_at(), _downsample_bpm_curve(), generate_metronome_stem(), integrate_tempo_curve(), local_period_at(), _onset_envelope() (+1 more)

### Community 63 - "PipelineConfig"
Cohesion: 0.30
Nodes (8): _apply_mix_aware_floors(), _cleanup_config_for_pipeline(), PipelineConfig, _transcription_thresholds(), test_cleanup_config_separated_mix_aware_raises_velocity(), test_cleanup_config_solo_mix_aware_flag_does_not_raise_velocity(), test_transcription_thresholds_separated_mix_aware_keeps_floors(), test_transcription_thresholds_solo_ignores_mix_aware_floors()

### Community 64 - "lite_detected_caption"
Cohesion: 0.25
Nodes (5): apple_chip_label(), _lite_accel_plain_label(), lite_detected_caption(), test_apple_chip_label_only_keeps_apple_brands(), test_lite_detected_and_using_captions_plain_language()

### Community 69 - "Path"
Cohesion: 0.15
Nodes (11): analyze_dual_guitar_candidate(), apply_bass_bleed_mitigation(), apply_emit_stems(), attach_guitar_refine_backups(), DualGuitarDiagnostics, guitar_prerefine_path(), guitar_refined_path(), has_guitar_prerefine() (+3 more)

### Community 70 - "_is_403_error"
Cohesion: 0.15
Nodes (9): 1. YouTube Downloader Unreliability (CRITICAL), _is_403_error(), _user_facing_youtube_error(), test_download_youtube_preview_video_uses_capped_mp4(), __init__(), test_is_403_error(), test_is_403_error_reads_http_error_chain(), __init__() (+1 more)

### Community 72 - "metronome_grid_times"
Cohesion: 0.29
Nodes (4): coerce_metronome_follow(), metronome_grid_times(), _render_times_for_follow(), steady_click_times()

### Community 75 - "_require_ffmpeg"
Cohesion: 0.33
Nodes (5): 8. FFmpeg Dependency (Often Missing), ffmpeg_install_hint(), _require_ffmpeg(), test_ffmpeg_install_hint_mentions_platform(), test_require_ffmpeg_missing_raises_typed_hint()

### Community 76 - "os"
Cohesion: 0.33
Nodes (3): _normalize_in_place(), temporary_output_path(), test_temporary_output_path_closes_fd_and_creates_file()

## Knowledge Gaps
- **1 isolated node(s):** `audio-to-tab-pdf`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 538 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Cons / Flaws (Especially Problematic)` connect `Cons / Flaws (Especially Problematic)` to `tab_bundle.py`, `_is_403_error`, `_execute_pending`, `lyrics.py`, `pathlib`, `ingest.py`, `_require_ffmpeg`, `hardware.py`, `HostProbe`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `_render_entry()` (e.g. with `get_desktop_probe()` and `lite_accelerator_available()`) actually correct?**
  _`_render_entry()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `audio-to-tab-pdf` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `numpy` be split into smaller, more focused modules?**
  _Cohesion score 0.11260504201680673 - nodes in this community are weakly interconnected._
- **Why does `Pros (Strengths)` connect `Cons / Flaws (Especially Problematic)` to `lite_auto_choice`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Should `lead_rhythm.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08287961282516637 - nodes in this community are weakly interconnected._
- **Why does `test_download_guitar_ft_retries_then_succeeds()` connect `test_download_guitar_ft_retries_then_succeeds` to `test_pipeline_guitar.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._