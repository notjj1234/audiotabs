# Graph Report - audiotabs  (2026-11-11)

## Corpus Check
- 58 files · ~60,854 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .toml 1, .ico 1)

## Summary
- 1292 nodes · 3134 edges · 76 communities (60 shown, 16 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 188 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3eebfd86`
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
- ingest.py
- tab_pdf.py
- isolate.py
- pathlib
- search_youtube_videos
- run_pipeline
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
- scnet.py
- separate_guitar_stem
- tempo.py
- edition.py
- Path
- player_bar.py
- desktop_recommend
- Any
- _execute_pending
- lite_auto_choice
- normalize_audio
- get_desktop_probe_without_torch
- lyrics.py
- Studio UI redesign
- is_youtube_url
- pathlib
- audiotabs
- typing
- recommended_cpu_threads
- format_region_label
- ensure_cuda_available
- test_download_403_twice_raises_user_error
- _YoutubeFileLogger
- detect_present_stems
- _scnet_architecture_module
- staff_wrap.py
- blend_guitar_stems
- test_download_does_not_require_js_runtime
- pytest
- analyze_bass_bleed
- apply_bleed_gate
- test_download_retries_after_403_then_succeeds
- _cpu_edition_by_default
- format_region_label_filename
- audio-to-tab-pdf
- analyze_dual_guitar_candidate
- test_download_youtube_preview_video_uses_capped_mp4
- test_search_youtube_videos_offset_slices_page
- LowEndRecoveryDiagnostics
- show_convert_action

## God Nodes (most connected - your core abstractions)
1. `separate_stems()` - 43 edges
2. `HostProbe` - 34 edges
3. `separate_guitar_stem()` - 34 edges
4. `run_pipeline()` - 30 edges
5. `TabDocument` - 24 edges
6. `generate_metronome_stem()` - 24 edges
7. `midi_to_tab()` - 23 edges
8. `split_lead_rhythm_guitar()` - 23 edges
9. `_render_entry()` - 22 edges
10. `_render_success()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Review Focus` --references--> `test_studio_theme_defines_tokens()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-studio-ui.md → tests/test_studio_ui.py
- `Task 4: Wire `tab_pdf.py` to the studio shell` --references--> `progress_card_html()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-studio-ui.md → ui/studio_shell.py
- `File map` --references--> `inject_studio_theme()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-studio-ui.md → ui/studio_theme.py
- `Task 4: Wire `tab_pdf.py` to the studio shell` --references--> `inject_studio_theme()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-studio-ui.md → ui/studio_theme.py
- `Review Focus` --references--> `EmptyTranscriptionError`  [INFERRED]
  docs/superpowers/plans/2026-11-10-tab-result.md → src/audio_to_tab/pipeline.py

## Import Cycles
- None detected.

## Communities (76 total, 16 thin omitted)

### Community 0 - "numpy"
Cohesion: 0.05
Nodes (61): align_click_grid_to_downbeat(), analysis_wav_for_downbeat(), apply_click_rate(), attach_metronome_artifact(), _beat_band_energy(), _beat_impulse_ratios(), _beat_local_rms(), _best_phase() (+53 more)

### Community 1 - "lead_rhythm.py"
Cohesion: 0.08
Nodes (27): _average_role_features(), build_midside_pair(), build_register_pair(), build_spatial_pair(), build_spectral_pair(), _CandidatePair, classify_lead_rhythm_roles(), _dominant_pitch_estimate() (+19 more)

### Community 2 - "mixer.py"
Cohesion: 0.09
Nodes (18): apply_pan(), apply_playback_transform(), apply_true_peak_ceiling(), audible_stems(), clamp_pan(), clamp_playback_semitones(), db_to_linear(), default_muted_for() (+10 more)

### Community 3 - "test_scnet.py"
Cohesion: 0.10
Nodes (6): test_download_scnet_weights_pins_url_and_sha256(), test_pipeline_progress_label_scnet(), test_run_scnet_model_writes_four_stems_and_no_other(), test_scnet_availability_follows_torch(), test_separate_guitar_stem_scnet_requires_runtime(), _tone_wav()

### Community 4 - "tab_bundle.py"
Cohesion: 0.13
Nodes (21): _capo_tuning(), ChordHit, chords_from_midi(), _collapse(), _correlate(), detect_key(), _frets_for(), name_chord() (+13 more)

### Community 5 - "notation_view.py"
Cohesion: 0.18
Nodes (13): _slice_document(), quantize_tab_document(), quantize_time(), sec_per_sixteenth(), _finite(), tab_document_from_dict(), tab_document_to_dict(), tab_measure_spans() (+5 more)

### Community 6 - "test_pipeline_guitar.py"
Cohesion: 0.09
Nodes (26): test_apply_guitar_low_end_recovery_debleed_writes_diagnostics(), test_apply_guitar_low_end_recovery_default_off(), test_apply_low_end_restore_boost_raises_low_band_share(), test_apply_low_end_restore_zero_db_is_noop(), test_apply_sub_bass_debleed_reduces_low_band_share(), test_collect_named_stems_filters_to_requested_names(), test_guitar_ft_weights_cached_false_when_missing(), test_guitar_ft_weights_cached_true_when_hash_matches() (+18 more)

### Community 7 - "roformer.py"
Cohesion: 0.07
Nodes (34): get_desktop_probe(), bs_roformer_sw_paths(), _canonical_stem_name(), _cap_cpu_threads(), collect_canonical_stems(), collect_named_stems(), _demix_track(), download_bs_roformer_sw_weights() (+26 more)

### Community 8 - "test_ingest.py"
Cohesion: 0.12
Nodes (11): format_youtube_duration(), _resolve_downloaded_wav(), _title_stem(), test_download_youtube_preview_rejects_non_youtube(), test_download_youtube_rejects_non_youtube(), test_format_youtube_duration(), test_resolve_downloaded_wav_no_candidates_raises(), test_resolve_downloaded_wav_no_title_match_uses_newest_normalized() (+3 more)

### Community 9 - "ingest.py"
Cohesion: 0.16
Nodes (13): _clear_ytdlp_cache(), download_direct_media(), download_youtube_audio(), download_youtube_preview_video(), _is_403_error(), _take_preview_download(), _unlink_quiet(), _user_facing_youtube_error() (+5 more)

### Community 10 - "tab_pdf.py"
Cohesion: 0.19
Nodes (15): default_guitar_track_option(), guitar_track_radio_ids(), normalize_guitar_track_selection(), _capo_label(), _clear_song(), _clock(), _download_name(), _init_setup_state() (+7 more)

### Community 11 - "isolate.py"
Cohesion: 0.11
Nodes (20): analyze_guitar_stem_quality(), apply_fold_other_gain_search(), apply_fold_other_into_guitar(), apply_guitar_low_end_recovery(), apply_low_end_restore(), _apply_peak_limit(), apply_sub_bass_debleed(), _bandpass_audio() (+12 more)

### Community 12 - "pathlib"
Cohesion: 0.11
Nodes (12): main(), _cap_onset_density(), cleanup_midi(), CleanupConfig, merge_instruments_to_one(), mix_aware_cleanup_config(), solo_guitar_cleanup_config(), _cleanup_config_for_pipeline() (+4 more)

### Community 13 - "search_youtube_videos"
Cohesion: 0.09
Nodes (8): search_youtube_videos(), _thumbnail_url_for_entry(), YouTubeSearchError, test_search_youtube_videos_clamps_fetch_to_50(), test_search_youtube_videos_rejects_blank_query(), test_search_youtube_videos_uses_ytsearch_and_maps_hits(), test_search_youtube_videos_wraps_backend_errors(), test_thumbnail_url_prefers_entry_then_cdn_fallback()

### Community 14 - "run_pipeline"
Cohesion: 0.25
Nodes (5): main(), count_midi_notes(), _require_usable_transcription(), run_pipeline(), _trim_audio()

### Community 15 - "test_hardware.py"
Cohesion: 0.12
Nodes (21): desktop_device_options(), resolve_desktop_speed(), test_apply_recommended_cpu_threads_skips_gpu(), test_both_edition_balanced_speed_uses_cpu_when_no_nvidia_gpu(), test_both_edition_faster_speed_uses_cpu_when_no_nvidia_gpu(), test_both_edition_offers_cuda_even_without_gpu(), test_both_edition_windows_device_options_gpu_first(), test_cuda_edition_windows_device_options_cuda_only() (+13 more)

### Community 16 - "separate.py"
Cohesion: 0.14
Nodes (6): apply_recommended_cpu_threads(), run_demucs(), JobAborted, run_process(), _stop_process(), subprocess_run_kwargs()

### Community 17 - "tab_generate.py"
Cohesion: 0.17
Nodes (12): Global Constraints, Task 2: Chords, capo, transpose, tuning, _filter_playable_positions(), _group_notes_into_events(), midi_to_tab(), _pick_chord_positions(), search(), _pick_single_position() (+4 more)

### Community 18 - "test_result_studio.py"
Cohesion: 0.18
Nodes (18): Review Focus, placed_note(), clamp_playback_rate(), download_menu(), downloads_after_run(), test_capo_and_transpose_shift_pitch_and_chord_names(), test_chord_names_follow_grouped_midi(), test_consecutive_identical_chords_collapse() (+10 more)

### Community 19 - "hardware.py"
Cohesion: 0.10
Nodes (14): _both_edition_windows(), _cuda_only_edition_windows(), _darwin_available_ram_gb(), _darwin_swap_used_gb(), lite_accelerator_available(), lite_device_choice_ids(), lite_device_plain_label(), _platform() (+6 more)

### Community 20 - "notation_view.py"
Cohesion: 0.15
Nodes (14): Task 3: Views, bars per line, downloads, player model, align_chords_to_lyrics(), chord_diagram_svg(), clamp_bars_per_line(), measure_count(), measure_rows(), _measure_seconds(), piano_roll_svg() (+6 more)

### Community 21 - "HostProbe"
Cohesion: 0.15
Nodes (14): apple_chip_label(), desktop_recommend_caption(), desktop_system_summary(), HostProbe, _lite_accel_plain_label(), lite_auto_speed_id(), lite_detected_caption(), lite_using_caption() (+6 more)

### Community 22 - "test_studio_ui.py"
Cohesion: 0.11
Nodes (16): Task 1: Studio theme tokens, test_entry_screen_css_has_one_hierarchy(), test_entry_screen_offers_two_sources(), test_hero_html_can_include_app_icon(), test_hero_html_is_title_only(), test_hero_sits_on_the_ground(), test_progress_row_puts_the_state_after_the_label(), test_result_header_html_shows_meta() (+8 more)

### Community 23 - "Path"
Cohesion: 0.17
Nodes (11): download_guitar_ft_weights(), _guitar_ft_digest_sidecar(), guitar_ft_weights_cached(), guitar_ft_weights_path(), guitar_ft_weights_sha256(), load_guitar_ft_state_dict(), remap_guitar_ft_state_dict(), run_demucs_guitar_ft_inprocess() (+3 more)

### Community 24 - "player_html"
Cohesion: 0.15
Nodes (14): File map, Global Constraints, Review Focus, Studio UI Hybrid Shell Implementation Plan, Task 2: Progress / hero shells, Task 3: Dark studio player, Task 4: Wire `tab_pdf.py` to the studio shell, Task 5: Full verification (+6 more)

### Community 25 - "separate_stems"
Cohesion: 0.10
Nodes (19): progress(), separate_progress_message(), _abort_if(), apply_bass_bleed_mitigation(), apply_emit_stems(), _collect_stem_wavs(), IsolateConfig, _mark_stage_complete() (+11 more)

### Community 26 - "common.py"
Cohesion: 0.17
Nodes (13): app_icon_data_uri(), app_icon_png(), list_recent_runs(), max_upload_caption(), max_upload_mb(), _resolve_data_dir(), run_output_dir(), _safe_upload_name() (+5 more)

### Community 27 - "pdf_render.py"
Cohesion: 0.12
Nodes (9): main(), main(), _count_measures(), _events_in_measure(), render_structured_tab_pdf(), render_tab_pdf(), tab_document_to_pdf(), tab_to_ascii() (+1 more)

### Community 28 - "test_youtube_search.py"
Cohesion: 0.12
Nodes (13): YouTubeSearchHit, test_hit_meta_joins_channel_and_duration(), test_hit_meta_keeps_only_the_parts_that_exist(), test_hit_state_serializes_a_search_hit(), test_normalize_page_accepts_int_and_numeric_string(), test_normalize_page_rejects_missing_and_out_of_range(), _close_youtube_search(), _run_youtube_search() (+5 more)

### Community 29 - "launcher.py"
Cohesion: 0.19
Nodes (12): health_ok(), log(), main(), on_closed(), on_shown(), pick_port(), port_free(), start_server() (+4 more)

### Community 30 - "test_tab.py"
Cohesion: 0.21
Nodes (10): test_cleanup_midi_writes_filtered(), test_dense_midi_tempo_not_inflated(), test_estimate_tempo_bpm_delegates_to_robust(), test_fret_assignment_avoids_large_jump_in_sequence(), test_midi_to_tab_simple(), test_onset_density_cap(), test_pdf_render(), test_positions_for_open_e() (+2 more)

### Community 31 - "scnet.py"
Cohesion: 0.15
Nodes (11): _demix_scnet(), download_scnet_weights(), is_scnet_available(), _load_audio_stereo(), _msst_normalize(), run_scnet_model(), scnet_weights_path(), _torch_device() (+3 more)

### Community 32 - "separate_guitar_stem"
Cohesion: 0.17
Nodes (8): effective_demucs_segment(), is_guitar_refine_available(), _maybe_refine_guitar_stem(), _run_demucs_guitar_cli(), separate_guitar_stem(), _apply_low_end_recovery(), _maybe_bleed_gate(), _maybe_fold_other()

### Community 33 - "tempo.py"
Cohesion: 0.23
Nodes (6): estimate_tempo_bpm(), _clamp_bpm(), estimate_tempo_from_audio(), estimate_tempo_from_midi_robust(), resolve_tempo(), TempoEstimate

### Community 34 - "edition.py"
Cohesion: 0.27
Nodes (9): desktop_edition(), edition_app_name(), edition_display_label(), edition_file_candidates(), edition_product_name(), edition_ships_cuda_torch(), edition_window_title(), normalize_edition() (+1 more)

### Community 35 - "Path"
Cohesion: 0.16
Nodes (10): attach_guitar_refine_backups(), ensure_guitar_prerefine_backup(), guitar_prerefine_path(), guitar_refined_path(), has_guitar_prerefine(), merge_two_pass_stems(), probe_duration_sec(), save_guitar_refined_backup() (+2 more)

### Community 36 - "player_bar.py"
Cohesion: 0.22
Nodes (5): player_click_times(), player_peaks(), player_source_labels(), player_speed(), synth_source_available()

### Community 37 - "desktop_recommend"
Cohesion: 0.14
Nodes (11): desktop_recommend(), is_low_ram(), _preferred_gpu(), test_auto_cpu_or_mac_without_mps_is_faster_cpu(), test_auto_low_ram_mps_mac_stays_cpu(), test_auto_low_ram_with_cuda_stays_on_gpu(), test_auto_mps_mac_is_balanced_gpu(), test_auto_windows_cuda_is_balanced_gpu() (+3 more)

### Community 38 - "Any"
Cohesion: 0.15
Nodes (4): AdaptiveFoldGainDiagnostics, FoldOtherDiagnostics, GuitarStemQualityDiagnostics, LowEndRestoreDiagnostics

### Community 39 - "_execute_pending"
Cohesion: 0.13
Nodes (10): Rulings, Tab result page implementation plan, Task 1: Staff wrap, Task 4: Pipeline stages, Task 5: Streamlit result page, Task 6: Verify, EmptyTranscriptionError, apply_progress() (+2 more)

### Community 40 - "lite_auto_choice"
Cohesion: 0.21
Nodes (7): lite_auto_choice(), lite_auto_device(), memory_pressure_is_tight(), MemoryPressure, test_lite_auto_choice_keeps_gpu_under_memory_pressure(), test_memory_pressure_is_tight_thresholds(), test_probe_memory_pressure_darwin_parses_vm_stat()

### Community 41 - "normalize_audio"
Cohesion: 0.17
Nodes (7): normalize_audio(), _normalize_in_place(), _require_ffmpeg(), temporary_output_path(), test_normalize_audio_deletes_temp_on_failure(), test_normalize_audio_temp_output_is_caller_owned(), test_temporary_output_path_closes_fd_and_creates_file()

### Community 42 - "get_desktop_probe_without_torch"
Cohesion: 0.18
Nodes (7): get_desktop_probe_without_torch(), probe_cpu_brand(), probe_ram_gb(), roformer_max_audio_sec(), test_get_desktop_probe_without_torch_cuda_edition(), test_get_desktop_probe_without_torch_does_not_import_torch(), test_roformer_max_audio_sec()

### Community 43 - "lyrics.py"
Cohesion: 0.27
Nodes (7): _import_transcriber(), _lines_from_segments(), LyricLine, lyrics_skip_reason(), transcribe_lyrics(), test_lyrics_skip_reason_without_a_vocal_stem(), _lyric_lines()

### Community 44 - "Studio UI redesign"
Cohesion: 0.20
Nodes (9): Anti-goals, Approaches, Constraints, Design (builder), Goals, Intent, Layout decisions (2026-11-11), Non-goals (+1 more)

### Community 45 - "is_youtube_url"
Cohesion: 0.25
Nodes (5): is_direct_media_url(), is_youtube_url(), _watch_url_from_entry(), test_watch_url_from_flat_search_entry(), test_youtube_url_allowlist()

### Community 46 - "pathlib"
Cohesion: 0.24
Nodes (3): app_version(), ensure_src_path(), inject_studio_theme()

### Community 47 - "audiotabs"
Cohesion: 0.25
Nodes (7): About, audiotabs, Quickstart, Quickstart, Table of contents, Tester, Tester

### Community 48 - "typing"
Cohesion: 0.22
Nodes (3): install_soundfile_writer(), main(), save_audio()

### Community 49 - "recommended_cpu_threads"
Cohesion: 0.25
Nodes (6): cpu_thread_env(), _physical_perf_cores(), recommended_cpu_threads(), test_cpu_thread_env_keys(), test_recommended_cpu_threads_clamps_by_ram(), threads_for()

### Community 50 - "format_region_label"
Cohesion: 0.22
Nodes (4): format_region_label(), format_time_sec(), RegionError, resolve_region()

### Community 51 - "ensure_cuda_available"
Cohesion: 0.29
Nodes (5): ensure_cuda_available(), probe_torch(), resolve_safe_device(), test_ensure_cuda_available_fail_closed(), test_resolve_safe_device_downgrades_ineligible_mps()

### Community 53 - "_YoutubeFileLogger"
Cohesion: 0.23
Nodes (4): _youtube_ydl_opts(), _YoutubeFileLogger, test_youtube_ydl_opts_forwards_file_logger_to_ytdlp(), test_youtube_ydl_opts_sets_noplaylist_and_client()

### Community 54 - "detect_present_stems"
Cohesion: 0.29
Nodes (4): detect_present_stems(), _rms_to_dbfs(), _stem_rms(), StemPresence

### Community 55 - "_scnet_architecture_module"
Cohesion: 0.29
Nodes (5): load_scnet_model(), _scnet_architecture_module(), __init__(), test_load_scnet_model_strict(), test_scnet_architecture_output_shape()

### Community 56 - "staff_wrap.py"
Cohesion: 0.31
Nodes (4): _split_body(), strip_ansi_csi(), _wrap_staff(), wrap_tab_staff()

### Community 57 - "blend_guitar_stems"
Cohesion: 0.25
Nodes (4): blend_guitar_stems(), EnsembleGuitarDiagnostics, _log_band_edges(), fake_blend()

### Community 59 - "pytest"
Cohesion: 0.32
Nodes (4): is_demucs_available(), test_is_demucs_available(), _click_track(), test_estimate_tempo_from_real_audio()

### Community 69 - "analyze_dual_guitar_candidate"
Cohesion: 0.38
Nodes (4): analyze_dual_guitar_candidate(), DualGuitarDiagnostics, _load_stereo(), split_dual_guitar_stem()

### Community 73 - "show_convert_action"
Cohesion: 0.67
Nodes (3): format_size_kb(), show_convert_action(), test_file_chip_and_convert_visibility()

## Knowledge Gaps
- **1 isolated node(s):** `audio-to-tab-pdf`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 466 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `separate_guitar_stem()` connect `separate_guitar_stem` to `test_pipeline_guitar.py`, `roformer.py`, `normalize_audio`, `isolate.py`, `pathlib`, `run_pipeline`, `Path`, `blend_guitar_stems`, `pytest`, `apply_bleed_gate`, `scnet.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `HostProbe` (e.g. with `test_auto_low_ram_mps_mac_stays_cpu()` and `test_desktop_system_summary_includes_apple_chip()`) actually correct?**
  _`HostProbe` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `audio-to-tab-pdf` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `numpy` be split into smaller, more focused modules?**
  _Cohesion score 0.05387397677517609 - nodes in this community are weakly interconnected._
- **Why does `test_download_youtube_preview_video_uses_capped_mp4()` connect `test_download_youtube_preview_video_uses_capped_mp4` to `test_ingest.py`, `ingest.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Should `lead_rhythm.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08287961282516637 - nodes in this community are weakly interconnected._
- **Why does `test_search_youtube_videos_offset_slices_page()` connect `test_search_youtube_videos_offset_slices_page` to `test_ingest.py`, `search_youtube_videos`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._