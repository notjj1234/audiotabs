"""Lead/rhythm per-stem transcription paths and technique heuristics."""

from __future__ import annotations

import numpy as np
import pretty_midi
import soundfile as sf

from audio_to_tab.lead_rhythm_tab import (
    StemNote,
    StemTranscription,
    _canonical_voicing_map,
    _energy_gate,
    _rhythm_chord_events,
    apply_canonical_voicings,
    technique_marks_for,
    transcribe_lead_stem,
    transcribe_rhythm_stem,
    write_stem_midis,
)
from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote

SR = 44100


def _note(pitch, start, end, velocity=100):
    return StemNote(pitch=pitch, start=start, end=end, velocity=velocity, confidence=velocity / 127.0)


def _write_midi(path, notes):
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=25)
    inst.notes = [
        pretty_midi.Note(
            velocity=max(1, min(127, int(n.velocity))),
            pitch=n.pitch,
            start=n.start,
            end=n.end,
        )
        for n in notes
    ]
    pm.instruments.append(inst)
    pm.write(str(path))
    return path


def _patch_transcribe(monkeypatch, notes):
    def fake_transcribe(audio_path, output_midi_path, **kwargs):
        return _write_midi(output_midi_path, notes)

    monkeypatch.setattr(
        "audio_to_tab.lead_rhythm_tab.transcribe_audio", fake_transcribe
    )


def _loud_then_quiet_wav(path, seconds=4.0):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    loud = 0.5 * np.sin(2 * np.pi * 220 * t[: n // 2])
    quiet = 0.004 * np.sin(2 * np.pi * 220 * t[n // 2 :])
    mono = np.concatenate([loud, quiet]).astype(np.float32)
    sf.write(str(path), np.column_stack([mono, mono]), SR)
    return path


class TestLeadPath:
    def test_keeps_highest_velocity_note_per_onset_window(self, tmp_path, monkeypatch):
        notes = [
            _note(60, 0.0, 0.4, velocity=50),
            _note(64, 0.0, 0.4, velocity=110),
            _note(67, 0.01, 0.4, velocity=30),
            _note(62, 1.0, 1.3, velocity=90),
        ]
        _patch_transcribe(monkeypatch, notes)
        audio = tmp_path / "lead.wav"
        _loud_then_quiet_wav(audio, seconds=4.0)
        tx = transcribe_lead_stem(audio, tmp_path / "lead.mid")
        assert tx.role == "lead"
        assert [n.pitch for n in tx.notes] == [64, 62]

    def test_all_notes_confidence_between_zero_and_one(self, tmp_path, monkeypatch):
        _patch_transcribe(monkeypatch, [_note(60, 0.0, 0.3), _note(62, 0.5, 0.8)])
        audio = tmp_path / "lead.wav"
        _loud_then_quiet_wav(audio, seconds=2.0)
        tx = transcribe_lead_stem(audio, tmp_path / "lead.mid")
        assert all(0.0 <= n.confidence <= 1.0 for n in tx.notes)


class TestRhythmPath:
    def test_strum_fragments_merge_into_chord_event(self):
        # Onsets spread past the 30 ms grouping threshold but inside the
        # 60 ms strum window must still collapse into one chord event.
        notes = [
            _note(40, 0.00, 0.50),
            _note(45, 0.035, 0.50),
            _note(50, 0.055, 0.50),
            _note(52, 1.00, 1.50),
        ]
        events = _rhythm_chord_events(notes)
        assert [sorted(n.pitch for n in ev) for ev in events] == [[40, 45, 50], [52]]

    def test_strum_merge_requires_three_overlapping_onsets(self):
        notes = [
            _note(40, 0.00, 0.50),
            _note(45, 0.030, 0.50),
            _note(47, 1.00, 1.50),
        ]
        events = _rhythm_chord_events(notes)
        # Only two onsets inside the 60 ms window: no collapse.
        assert [sorted(n.pitch for n in ev) for ev in events] == [[40, 45], [47]]

    def test_repeated_progression_shares_one_voicing(self):
        e_major = [_note(40, 0.0, 1.0), _note(44, 0.0, 1.0), _note(47, 0.0, 1.0)]
        g_major = [_note(43, 1.0, 2.0), _note(47, 1.0, 2.0), _note(50, 1.0, 2.0)]
        e_major_again = [_note(40, 2.0, 3.0), _note(44, 2.0, 3.0), _note(47, 2.0, 3.0)]
        g_major_again = [_note(43, 3.0, 4.0), _note(47, 3.0, 4.0), _note(50, 3.0, 4.0)]
        events = _rhythm_chord_events(e_major + g_major + e_major_again + g_major_again)
        voicings = _canonical_voicing_map(events)
        e_keys = [k for k in voicings if set(k) == {40 % 12, 44 % 12, 47 % 12}]
        g_keys = [k for k in voicings if set(k) == {43 % 12, 47 % 12, 50 % 12}]
        assert len(e_keys) == 1 and len(g_keys) == 1
        assert len(voicings) == 2  # E and G each canonicalized once

    def test_apply_canonical_voicings_rewrites_matching_events(self):
        e_major = [_note(40, 0.0, 1.0), _note(44, 0.0, 1.0), _note(47, 0.0, 1.0)]
        g_major = [_note(43, 1.0, 2.0), _note(47, 1.0, 2.0), _note(50, 1.0, 2.0)]
        e_major_again = [_note(40, 2.0, 3.0), _note(44, 2.0, 3.0), _note(47, 2.0, 3.0)]
        g_major_again = [_note(43, 3.0, 4.0), _note(47, 3.0, 4.0), _note(50, 3.0, 4.0)]
        events = _rhythm_chord_events(e_major + g_major + e_major_again + g_major_again)
        voicings = _canonical_voicing_map(events)

        def doc_for(pitches, start):
            return TabEvent(
                start=start,
                notes=[
                    TabNote(start=start, end=start + 1.0, string=0, fret=p - 40, pitch=p)
                    for p in pitches
                ],
            )

        doc = TabDocument(
            events=[
                doc_for([40, 44, 47], 0.0),
                doc_for([43, 47, 50], 1.0),
                doc_for([40, 44, 47], 2.0),
                doc_for([43, 47, 50], 3.0),
            ]
        )
        out = apply_canonical_voicings(doc, voicings)
        first = sorted((n.string, n.fret) for n in out.events[0].notes)
        again = sorted((n.string, n.fret) for n in out.events[2].notes)
        g_first = sorted((n.string, n.fret) for n in out.events[1].notes)
        g_again = sorted((n.string, n.fret) for n in out.events[3].notes)
        assert first == again
        assert g_first == g_again

    def test_rhythm_transcription_keeps_polyphony(self, tmp_path, monkeypatch):
        notes = [
            _note(40, 0.0, 0.5),
            _note(45, 0.02, 0.5),
            _note(50, 0.04, 0.5),
        ]
        _patch_transcribe(monkeypatch, notes)
        audio = tmp_path / "rhythm.wav"
        _loud_then_quiet_wav(audio, seconds=2.0)
        tx = transcribe_rhythm_stem(audio, tmp_path / "rhythm.mid")
        assert tx.role == "rhythm"
        assert len(tx.notes) == 3


class TestEnergyGate:
    def test_drops_notes_in_quiet_region(self, tmp_path):
        audio = tmp_path / "stem.wav"
        _loud_then_quiet_wav(audio, seconds=4.0)
        notes = [_note(50, 0.5, 1.0), _note(52, 3.0, 3.5)]
        kept, dropped = _energy_gate(notes, audio)
        assert [n.pitch for n in kept] == [50]
        assert [n.pitch for n in dropped] == [52]

    def test_without_audio_keeps_everything(self):
        notes = [_note(50, 0.5, 1.0)]
        kept, dropped = _energy_gate(notes, None)
        assert kept == notes
        assert dropped == []


class TestTechniques:
    def test_hammer_on_moderate_gap(self):
        # C3 -> E3 (4 semitones, 20 ms onset gap): no same-string close-fret
        # move, so the legato heuristic wins over the slide heuristic.
        notes = [_note(48, 0.0, 0.20), _note(52, 0.02, 0.50)]
        marks = technique_marks_for("lead", notes)
        kinds = [m.kind for m in marks]
        assert "hammer_on" in kinds
        assert "slide" not in kinds
        mark = next(m for m in marks if m.kind == "hammer_on")
        assert mark.confidence == "medium"
        assert mark.evidence

    def test_pull_off_descending(self):
        notes = [_note(52, 0.0, 0.20), _note(48, 0.03, 0.50)]
        marks = technique_marks_for("lead", notes)
        assert "pull_off" in [m.kind for m in marks]

    def test_wide_leap_gets_no_legato_mark(self):
        notes = [_note(45, 0.0, 0.20), _note(52, 0.23, 0.50)]
        marks = technique_marks_for("lead", notes)
        assert not any(m.kind in ("hammer_on", "pull_off", "slide") for m in marks)

    def test_slide_same_string_close_frets(self):
        # G2 (43) low-E fret 3 -> A2 (45) low-E fret 5, 50 ms onset gap.
        notes = [_note(43, 0.0, 0.20), _note(45, 0.05, 0.60)]
        marks = technique_marks_for("lead", notes)
        slides = [m for m in marks if m.kind == "slide"]
        assert slides and slides[0].confidence == "medium"

    def test_palm_mute_quiet_short_notes_in_rhythm(self):
        velocities = [100] * 6 + [20, 20]
        notes = [
            StemNote(
                pitch=40,
                start=i * 0.15,
                end=i * 0.15 + 0.08,
                velocity=velocities[i],
                confidence=velocities[i] / 127.0,
            )
            for i in range(8)
        ]
        marks = technique_marks_for("rhythm", notes)
        mutes = [m for m in marks if m.kind == "palm_mute"]
        assert len(mutes) == 2
        assert all(m.confidence == "low" for m in mutes)

    def test_no_bend_or_vibrato_without_evidence(self):
        notes = [_note(45, 0.0, 0.5), _note(47, 0.6, 1.0), _note(45, 1.1, 1.5)]
        marks = technique_marks_for("lead", notes)
        assert not any(m.kind in ("bend", "vibrato") for m in marks)

    def test_all_marks_carry_confidence_label_and_evidence(self):
        velocities = [100] * 6 + [20, 20]
        notes = [
            StemNote(
                pitch=40,
                start=i * 0.15,
                end=i * 0.15 + 0.08,
                velocity=velocities[i],
                confidence=velocities[i] / 127.0,
            )
            for i in range(8)
        ] + [_note(43, 2.0, 2.2), _note(45, 2.05, 2.6)]
        marks = technique_marks_for("rhythm", notes)
        assert marks
        for mark in marks:
            assert mark.confidence in ("low", "medium")
            assert mark.evidence


class TestStemMidis:
    def test_writes_three_files_with_two_track_stems(self, tmp_path):
        lead = StemTranscription(
            role="lead",
            notes=[_note(60, 0.0, 0.5)],
            techniques=[],
            low_confidence_regions=[],
            source_midi=tmp_path / "lead.mid",
        )
        rhythm = StemTranscription(
            role="rhythm",
            notes=[_note(40, 0.0, 0.5), _note(45, 0.0, 0.5)],
            techniques=[],
            low_confidence_regions=[],
            source_midi=tmp_path / "rhythm.mid",
        )
        out = write_stem_midis(lead, rhythm, tmp_path)
        assert set(out) == {"lead_midi", "rhythm_midi", "stems_midi"}
        for path in out.values():
            assert path.is_file()
        pm = pretty_midi.PrettyMIDI(str(out["stems_midi"]))
        assert len(pm.instruments) == 2
        assert {inst.name for inst in pm.instruments} == {"Lead", "Rhythm"}
        assert sum(len(i.notes) for i in pm.instruments) == 3
