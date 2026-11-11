# Graph Report - audiotabs  (2026-11-11)

## Corpus Check
- 58 files · ~60,563 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .toml 1)

## Summary
- 1286 nodes · 3125 edges · 69 communities (55 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 167 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `18e581d3`
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
- audio_to_tab/pipeline.py
- test_hardware.py
- separate.py
- tab_generate.py
- test_result_studio.py
- hardware.py
- Task 3: Views, bars per line, downloads, player model
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
- _run_demucs_model
- separate_guitar_stem
- is_roformer_backend_available
- edition.py
- Path
- player_bar.py
- desktop_recommend
- Any
- _execute_pending
- lite_auto_choice
- ensure_guitar_prerefine_backup
- get_desktop_probe_without_torch
- lyrics.py
- Studio UI redesign
- is_youtube_url
- apply_fold_other_into_guitar
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
- run_roformer_model
- test_download_does_not_require_js_runtime
- apply_fold_other_gain_search
- analyze_bass_bleed
- apply_bleed_gate
- test_download_retries_after_403_then_succeeds
- _cpu_edition_by_default
- format_region_label_filename
- audio-to-tab-pdf

## God Nodes (most connected - your core abstractions)
1. `separate_stems()` - 43 edges
2. `HostProbe` - 34 edges
3. `separate_guitar_stem()` - 34 edges
4. `run_pipeline()` - 30 edges
5. `generate_metronome_stem()` - 24 edges
6. `TabDocument` - 24 edges
7. `split_lead_rhythm_guitar()` - 23 edges
8. `midi_to_tab()` - 23 edges
9. `_render_success()` - 22 edges
10. `desktop_device_options()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `Task 2: Chords, capo, transpose, tuning` --references--> `ChordHit`  [INFERRED]
  docs/superpowers/plans/2026-11-10-tab-result.md → src/audio_to_tab/chords.py
- `Rulings` --references--> `metronome_grid_times()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-tab-result.md → src/audio_to_tab/metronome.py
- `Rulings` --references--> `clamp_playback_rate()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-tab-result.md → src/audio_to_tab/mixer.py
- `Rulings` --references--> `waveform_peaks()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-tab-result.md → src/audio_to_tab/mixer.py
- `Task 3: Views, bars per line, downloads, player model` --references--> `clamp_bars_per_line()`  [INFERRED]
  docs/superpowers/plans/2026-11-10-tab-result.md → src/audio_to_tab/notation_view.py

## Import Cycles
- None detected.

## Communities (69 total, 14 thin omitted)

### Community 0 - "numpy"
Cohesion: 0.05
Nodes (61): align_click_grid_to_downbeat(), analysis_wav_for_downbeat(), apply_click_rate(), attach_metronome_artifact(), _beat_band_energy(), _beat_impulse_ratios(), _beat_local_rms(), _best_phase() (+53 more)

### Community 1 - "lead_rhythm.py"
Cohesion: 0.08
Nodes (27): _average_role_features(), build_midside_pair(), build_register_pair(), build_spatial_pair(), build_spectral_pair(), _CandidatePair, classify_lead_rhythm_roles(), _dominant_pitch_estimate() (+19 more)

### Community 2 - "mixer.py"
Cohesion: 0.06
Nodes (25): apply_pan(), apply_playback_transform(), apply_true_peak_ceiling(), audible_stems(), clamp_pan(), clamp_playback_semitones(), db_to_linear(), default_muted_for() (+17 more)

### Community 3 - "test_scnet.py"
Cohesion: 0.06
Nodes (16): separator_cache_dir(), _demix_scnet(), download_scnet_weights(), _load_audio_stereo(), _msst_normalize(), scnet_weights_path(), _torch_device(), _write_stem() (+8 more)

### Community 4 - "tab_bundle.py"
Cohesion: 0.12
Nodes (21): _capo_tuning(), ChordHit, chords_from_midi(), _collapse(), _correlate(), detect_key(), _frets_for(), name_chord() (+13 more)

### Community 5 - "notation_view.py"
Cohesion: 0.12
Nodes (22): clamp_bars_per_line(), measure_count(), measure_rows(), _measure_seconds(), screen_tab_text(), _slice_document(), tab_staff_svg(), quantize_tab_document() (+14 more)

### Community 6 - "test_pipeline_guitar.py"
Cohesion: 0.10
Nodes (23): test_apply_guitar_low_end_recovery_default_off(), test_apply_low_end_restore_boost_raises_low_band_share(), test_apply_low_end_restore_zero_db_is_noop(), test_apply_sub_bass_debleed_reduces_low_band_share(), test_collect_named_stems_filters_to_requested_names(), test_isolate_config_clamps_low_end_restore_db(), test_isolate_config_sub_bass_debleed_defaults_off(), test_pipeline_config_quality_backend_defaults() (+15 more)

### Community 7 - "roformer.py"
Cohesion: 0.13
Nodes (19): bs_roformer_sw_paths(), _cap_cpu_threads(), _demix_track(), download_bs_roformer_sw_weights(), download_melband_guitar_weights(), download_sha256_file(), file_sha256(), _instantiate_bs_roformer_model() (+11 more)

### Community 8 - "test_ingest.py"
Cohesion: 0.07
Nodes (17): format_youtube_duration(), _resolve_downloaded_wav(), _title_stem(), _youtube_preview_ydl_opts(), _youtube_ydl_opts(), test_download_youtube_preview_rejects_non_youtube(), test_download_youtube_preview_video_uses_capped_mp4(), test_format_youtube_duration() (+9 more)

### Community 9 - "ingest.py"
Cohesion: 0.13
Nodes (17): _clear_ytdlp_cache(), download_youtube_audio(), download_youtube_preview_video(), _is_403_error(), normalize_audio(), _normalize_in_place(), _require_ffmpeg(), _take_preview_download() (+9 more)

### Community 10 - "tab_pdf.py"
Cohesion: 0.12
Nodes (19): default_guitar_track_option(), guitar_track_radio_ids(), normalize_guitar_track_selection(), _capo_label(), _clear_song(), _clock(), _close_youtube_search(), _download_name() (+11 more)

### Community 11 - "isolate.py"
Cohesion: 0.12
Nodes (17): analyze_guitar_stem_quality(), apply_low_end_restore(), _apply_peak_limit(), apply_sub_bass_debleed(), _bandpass_audio(), blend_guitar_stems(), effective_isolation_quality(), _highpass_rms() (+9 more)

### Community 12 - "pathlib"
Cohesion: 0.11
Nodes (10): main(), _cap_onset_density(), cleanup_midi(), CleanupConfig, estimate_tempo_bpm(), merge_instruments_to_one(), mix_aware_cleanup_config(), solo_guitar_cleanup_config() (+2 more)

### Community 13 - "search_youtube_videos"
Cohesion: 0.07
Nodes (9): search_youtube_videos(), _thumbnail_url_for_entry(), YouTubeSearchError, test_search_youtube_videos_clamps_fetch_to_50(), test_search_youtube_videos_offset_slices_page(), test_search_youtube_videos_rejects_blank_query(), test_search_youtube_videos_uses_ytsearch_and_maps_hits(), test_search_youtube_videos_wraps_backend_errors() (+1 more)

### Community 14 - "audio_to_tab/pipeline.py"
Cohesion: 0.13
Nodes (11): main(), probe_duration_sec(), _trim_audio(), count_midi_notes(), PipelineConfig, _require_usable_transcription(), run_pipeline(), _separate_progress_label() (+3 more)

### Community 15 - "test_hardware.py"
Cohesion: 0.13
Nodes (20): desktop_device_options(), resolve_desktop_speed(), test_apply_recommended_cpu_threads_skips_gpu(), test_both_edition_balanced_speed_uses_cpu_when_no_nvidia_gpu(), test_both_edition_faster_speed_uses_cpu_when_no_nvidia_gpu(), test_both_edition_offers_cuda_even_without_gpu(), test_both_edition_windows_device_options_gpu_first(), test_cuda_edition_windows_device_options_cuda_only() (+12 more)

### Community 16 - "separate.py"
Cohesion: 0.11
Nodes (9): install_soundfile_writer(), apply_recommended_cpu_threads(), effective_demucs_segment(), remap_guitar_ft_state_dict(), run_demucs(), _run_demucs_guitar_cli(), JobAborted, run_process() (+1 more)

### Community 17 - "tab_generate.py"
Cohesion: 0.17
Nodes (13): Global Constraints, Task 2: Chords, capo, transpose, tuning, main(), _filter_playable_positions(), _group_notes_into_events(), midi_to_tab(), _pick_chord_positions(), search() (+5 more)

### Community 18 - "test_result_studio.py"
Cohesion: 0.18
Nodes (18): Review Focus, placed_note(), clamp_playback_rate(), download_menu(), downloads_after_run(), test_bars_per_line_changes_pdf_and_staff_rows(), test_capo_and_transpose_shift_pitch_and_chord_names(), test_chord_names_follow_grouped_midi() (+10 more)

### Community 19 - "hardware.py"
Cohesion: 0.12
Nodes (12): _both_edition_windows(), _cuda_only_edition_windows(), _darwin_available_ram_gb(), _darwin_swap_used_gb(), lite_accelerator_available(), lite_device_choice_ids(), _platform(), probe_memory_pressure() (+4 more)

### Community 20 - "Task 3: Views, bars per line, downloads, player model"
Cohesion: 0.10
Nodes (17): Rulings, Tab result page implementation plan, Task 1: Staff wrap, Task 3: Views, bars per line, downloads, player model, Task 4: Pipeline stages, Task 6: Verify, align_chords_to_lyrics(), chord_diagram_svg() (+9 more)

### Community 21 - "HostProbe"
Cohesion: 0.13
Nodes (16): apple_chip_label(), desktop_recommend_caption(), desktop_system_summary(), HostProbe, _lite_accel_plain_label(), lite_auto_speed_id(), lite_detected_caption(), lite_device_plain_label() (+8 more)

### Community 22 - "test_studio_ui.py"
Cohesion: 0.13
Nodes (13): Task 1: Studio theme tokens, test_entry_screen_css_has_one_hierarchy(), test_entry_screen_offers_two_sources(), test_hero_html_is_title_only(), test_hero_sits_on_the_ground(), test_result_header_html_shows_meta(), test_score_panel_is_dark(), test_studio_css_hides_streamlit_chrome() (+5 more)

### Community 23 - "Path"
Cohesion: 0.16
Nodes (12): download_guitar_ft_weights(), _guitar_ft_digest_sidecar(), guitar_ft_weights_cached(), guitar_ft_weights_path(), guitar_ft_weights_sha256(), load_guitar_ft_state_dict(), run_demucs_guitar_ft_inprocess(), _torch_cache_dir() (+4 more)

### Community 24 - "player_html"
Cohesion: 0.14
Nodes (16): File map, Global Constraints, Review Focus, Studio UI Hybrid Shell Implementation Plan, Task 2: Progress / hero shells, Task 3: Dark studio player, Task 4: Wire `tab_pdf.py` to the studio shell, Task 5: Full verification (+8 more)

### Community 25 - "separate_stems"
Cohesion: 0.15
Nodes (11): progress(), _abort_if(), apply_bass_bleed_mitigation(), apply_emit_stems(), LowEndRestoreDiagnostics, _mark_stage_complete(), separate_stems(), _collect_into_out_dir() (+3 more)

### Community 26 - "common.py"
Cohesion: 0.18
Nodes (10): app_version(), ensure_src_path(), list_recent_runs(), max_upload_caption(), max_upload_mb(), _resolve_data_dir(), run_output_dir(), _safe_upload_name() (+2 more)

### Community 27 - "pdf_render.py"
Cohesion: 0.15
Nodes (7): main(), _count_measures(), _events_in_measure(), render_structured_tab_pdf(), render_tab_pdf(), tab_document_to_pdf(), test_count_measures_does_not_add_empty_trailing_bar()

### Community 28 - "test_youtube_search.py"
Cohesion: 0.16
Nodes (9): YouTubeSearchHit, test_hit_meta_joins_channel_and_duration(), test_hit_meta_keeps_only_the_parts_that_exist(), test_hit_state_serializes_a_search_hit(), test_normalize_page_accepts_int_and_numeric_string(), test_normalize_page_rejects_missing_and_out_of_range(), hit_meta(), hit_state() (+1 more)

### Community 29 - "launcher.py"
Cohesion: 0.22
Nodes (11): health_ok(), log(), main(), on_closed(), on_shown(), pick_port(), port_free(), start_server() (+3 more)

### Community 30 - "test_tab.py"
Cohesion: 0.21
Nodes (10): test_cleanup_midi_writes_filtered(), test_dense_midi_tempo_not_inflated(), test_estimate_tempo_bpm_delegates_to_robust(), test_fret_assignment_avoids_large_jump_in_sequence(), test_midi_to_tab_simple(), test_onset_density_cap(), test_pdf_render(), test_positions_for_open_e() (+2 more)

### Community 31 - "_run_demucs_model"
Cohesion: 0.15
Nodes (10): separate_progress_message(), _collect_stem_wavs(), IsolateConfig, merge_two_pass_stems(), resolve_demucs_overlap(), resolve_demucs_shifts(), _run_demucs_model(), _run_separation_backend() (+2 more)

### Community 32 - "separate_guitar_stem"
Cohesion: 0.14
Nodes (10): apply_guitar_low_end_recovery(), is_scnet_available(), run_scnet_model(), is_demucs_available(), separate_guitar_stem(), _apply_low_end_recovery(), _maybe_bleed_gate(), _maybe_fold_other() (+2 more)

### Community 33 - "is_roformer_backend_available"
Cohesion: 0.13
Nodes (9): _canonical_stem_name(), collect_canonical_stems(), collect_named_stems(), is_audio_separator_available(), is_roformer_backend_available(), refine_guitar_from_stems(), run_melband_guitar(), _run_via_audio_separator() (+1 more)

### Community 34 - "edition.py"
Cohesion: 0.27
Nodes (9): desktop_edition(), edition_app_name(), edition_display_label(), edition_file_candidates(), edition_product_name(), edition_ships_cuda_torch(), edition_window_title(), normalize_edition() (+1 more)

### Community 35 - "Path"
Cohesion: 0.21
Nodes (9): analyze_dual_guitar_candidate(), attach_guitar_refine_backups(), DualGuitarDiagnostics, guitar_prerefine_path(), guitar_refined_path(), has_guitar_prerefine(), _load_stereo(), split_dual_guitar_stem() (+1 more)

### Community 36 - "player_bar.py"
Cohesion: 0.15
Nodes (5): player_peaks(), player_source_labels(), synth_source_available(), _render_player(), _roll_notes()

### Community 37 - "desktop_recommend"
Cohesion: 0.14
Nodes (11): desktop_recommend(), is_low_ram(), _preferred_gpu(), test_auto_cpu_or_mac_without_mps_is_faster_cpu(), test_auto_low_ram_mps_mac_stays_cpu(), test_auto_low_ram_with_cuda_stays_on_gpu(), test_auto_mps_mac_is_balanced_gpu(), test_auto_windows_cuda_is_balanced_gpu() (+3 more)

### Community 38 - "Any"
Cohesion: 0.18
Nodes (4): EnsembleGuitarDiagnostics, GuitarStemQualityDiagnostics, LowEndRecoveryDiagnostics, fake_blend()

### Community 39 - "_execute_pending"
Cohesion: 0.22
Nodes (8): Task 5: Streamlit result page, EmptyTranscriptionError, apply_progress(), new_checklist(), test_checklist_marks_a_skip_and_ignores_unknown_stages(), _execute_pending(), on_progress(), _paint_checklist()

### Community 40 - "lite_auto_choice"
Cohesion: 0.21
Nodes (7): lite_auto_choice(), lite_auto_device(), memory_pressure_is_tight(), MemoryPressure, test_lite_auto_choice_keeps_gpu_under_memory_pressure(), test_memory_pressure_is_tight_thresholds(), test_probe_memory_pressure_darwin_parses_vm_stat()

### Community 41 - "ensure_guitar_prerefine_backup"
Cohesion: 0.24
Nodes (6): ensure_guitar_prerefine_backup(), _maybe_refine_guitar(), save_guitar_refined_backup(), is_guitar_refine_available(), run_guitar_refine(), _maybe_refine_guitar_stem()

### Community 42 - "get_desktop_probe_without_torch"
Cohesion: 0.18
Nodes (7): get_desktop_probe_without_torch(), probe_cpu_brand(), probe_ram_gb(), roformer_max_audio_sec(), test_get_desktop_probe_without_torch_cuda_edition(), test_get_desktop_probe_without_torch_does_not_import_torch(), test_roformer_max_audio_sec()

### Community 43 - "lyrics.py"
Cohesion: 0.31
Nodes (6): _import_transcriber(), _lines_from_segments(), LyricLine, lyrics_skip_reason(), transcribe_lyrics(), test_lyrics_skip_reason_without_a_vocal_stem()

### Community 44 - "Studio UI redesign"
Cohesion: 0.20
Nodes (9): Anti-goals, Approaches, Constraints, Design (builder), Goals, Intent, Layout decisions (2026-11-11), Non-goals (+1 more)

### Community 45 - "is_youtube_url"
Cohesion: 0.20
Nodes (6): download_direct_media(), is_direct_media_url(), is_youtube_url(), _watch_url_from_entry(), test_watch_url_from_flat_search_entry(), test_youtube_url_allowlist()

### Community 46 - "apply_fold_other_into_guitar"
Cohesion: 0.22
Nodes (4): apply_fold_other_into_guitar(), _drop_other_stem(), fold_other_into_guitar(), FoldOtherDiagnostics

### Community 47 - "audiotabs"
Cohesion: 0.22
Nodes (8): audiotabs, CLI, Layout, License, Requirements, Run the UI, Setup, Tests

### Community 49 - "recommended_cpu_threads"
Cohesion: 0.25
Nodes (6): cpu_thread_env(), _physical_perf_cores(), recommended_cpu_threads(), test_cpu_thread_env_keys(), test_recommended_cpu_threads_clamps_by_ram(), threads_for()

### Community 50 - "format_region_label"
Cohesion: 0.22
Nodes (4): format_region_label(), format_time_sec(), RegionError, resolve_region()

### Community 51 - "ensure_cuda_available"
Cohesion: 0.29
Nodes (5): ensure_cuda_available(), probe_torch(), resolve_safe_device(), test_ensure_cuda_available_fail_closed(), test_resolve_safe_device_downgrades_ineligible_mps()

### Community 54 - "detect_present_stems"
Cohesion: 0.29
Nodes (4): detect_present_stems(), _rms_to_dbfs(), _stem_rms(), StemPresence

### Community 55 - "_scnet_architecture_module"
Cohesion: 0.29
Nodes (5): load_scnet_model(), _scnet_architecture_module(), __init__(), test_load_scnet_model_strict(), test_scnet_architecture_output_shape()

### Community 56 - "staff_wrap.py"
Cohesion: 0.33
Nodes (3): _split_body(), strip_ansi_csi(), _wrap_staff()

### Community 57 - "run_roformer_model"
Cohesion: 0.33
Nodes (4): get_desktop_probe(), _refuse_long_roformer_audio(), run_roformer_model(), test_refuse_long_roformer_audio()

## Knowledge Gaps
- **1 isolated node(s):** `audio-to-tab-pdf`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 465 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RegionError` connect `format_region_label` to `separate_stems`, `isolate.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `HostProbe` (e.g. with `test_auto_low_ram_mps_mac_stays_cpu()` and `test_desktop_system_summary_includes_apple_chip()`) actually correct?**
  _`HostProbe` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `audio-to-tab-pdf` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `numpy` be split into smaller, more focused modules?**
  _Cohesion score 0.05455251407493691 - nodes in this community are weakly interconnected._
- **Why does `_YoutubeFileLogger` connect `_YoutubeFileLogger` to `test_ingest.py`, `ingest.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Should `lead_rhythm.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08287961282516637 - nodes in this community are weakly interconnected._
- **Why does `attach_metronome_artifact()` connect `numpy` to `separate_stems`, `isolate.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._