"""Instrument inventory: rows, defaults, plain-English reasons."""

from __future__ import annotations

from audio_to_tab.inventory import (
    LeadRhythmOutcome,
    PartCandidate,
    build_inventory,
    presence_reason_text,
)
from audio_to_tab.isolate import StemPresence


def _p(present: bool, share: float = 0.2, conf: float = 0.8) -> StemPresence:
    return StemPresence(
        present=present,
        confidence=conf,
        mean_dbfs=-20.0 if present else -70.0,
        energy_share=share,
        reason="mean level -20.0 dBFS (floor -45.0) — technical",
    )


SIX = {
    "vocals": _p(True, 0.3),
    "drums": _p(True, 0.2),
    "bass": _p(True, 0.15),
    "guitar": _p(True, 0.25),
    "piano": _p(False, 0.005, 0.1),
    "other": _p(True, 0.05),
}


def _by_id(rows: list[PartCandidate]) -> dict[str, PartCandidate]:
    return {r.id: r for r in rows}


def test_split_ok_checks_lead_and_rhythm_and_offers_combined_unchecked():
    rows = _by_id(
        build_inventory(
            SIX,
            lead_rhythm=LeadRhythmOutcome(
                ok=True, reason=None, presence={"lead": _p(True), "rhythm": _p(True)}
            ),
        )
    )
    assert rows["lead"].default_selected and rows["rhythm"].default_selected
    assert rows["combined"].default_selected is False
    assert rows["lead"].family == rows["rhythm"].family == rows["combined"].family == "guitar"
    assert rows["lead"].tab_kind == "tab"


def test_split_ok_preselects_barely_audible_lead_and_rhythm():
    rows = _by_id(
        build_inventory(
            SIX,
            lead_rhythm=LeadRhythmOutcome(
                ok=True, reason=None, presence={"lead": _p(False), "rhythm": _p(False)}
            ),
        )
    )
    assert rows["lead"].default_selected and rows["rhythm"].default_selected
    assert rows["lead"].detected is False
    assert rows["lead"].note == "Barely audible, may produce few notes."


def test_split_failed_greys_out_lead_and_rhythm_and_checks_combined():
    rows = _by_id(
        build_inventory(
            SIX,
            lead_rhythm=LeadRhythmOutcome(ok=False, reason="Audio is too long to split.", presence={}),
        )
    )
    assert list(rows)[:3] == ["lead", "rhythm", "combined"]
    for part in ("lead", "rhythm"):
        assert not (rows[part].tabbable or rows[part].detected or rows[part].default_selected)
        assert rows[part].note == ""
    assert rows["combined"].default_selected is True
    assert "too long" in (rows["combined"].note or "")


def test_no_guitar_leaves_combined_unchecked():
    presence = dict(SIX, guitar=_p(False, 0.004, 0.1))
    rows = _by_id(
        build_inventory(presence, lead_rhythm=LeadRhythmOutcome(ok=False, reason="x", presence={}))
    )
    assert rows["combined"].detected is False
    assert rows["combined"].default_selected is False


def test_other_is_never_default_checked_and_undetected_rows_unchecked():
    rows = _by_id(
        build_inventory(SIX, lead_rhythm=LeadRhythmOutcome(ok=False, reason="x", presence={}))
    )
    assert rows["other"].detected is True
    assert rows["other"].default_selected is False
    assert rows["keys"].detected is False
    assert rows["keys"].default_selected is False
    assert rows["keys"].note == "Barely audible, may produce few notes."


def test_tab_kinds_per_family():
    rows = _by_id(
        build_inventory(SIX, lead_rhythm=LeadRhythmOutcome(ok=False, reason="x", presence={}))
    )
    assert rows["bass"].tab_kind == "tab"
    assert rows["vocals"].tab_kind == "staff"
    assert rows["keys"].tab_kind == "staff" and rows["keys"].stem == "piano"
    assert rows["drums"].tab_kind == "drums"
    assert all(r.tabbable for r in rows.values() if r.id not in ("lead", "rhythm"))


def test_reason_text_is_plain_english():
    assert presence_reason_text(_p(True, 0.34)) == "Clearly present: about 34% of the mix"
    assert presence_reason_text(_p(True, 0.05)) == "Present but quiet: about 5% of the mix"
    assert presence_reason_text(_p(False, 0.001)) == "Barely audible: likely not in this song"
    rows = build_inventory(SIX, lead_rhythm=LeadRhythmOutcome(ok=False, reason="x", presence={}))
    assert all("dBFS" not in r.reason for r in rows)


def test_rows_round_trip_through_dict():
    rows = build_inventory(SIX, lead_rhythm=LeadRhythmOutcome(ok=False, reason="x", presence={}))
    assert [PartCandidate.from_dict(r.to_dict()) for r in rows] == rows


def test_split_turned_off_by_choice_reads_as_a_choice_not_a_failure():
    rows = _by_id(
        build_inventory(
            SIX,
            lead_rhythm=LeadRhythmOutcome(
                ok=False, reason="Lead and Rhythm splitting wasn't requested.", skipped=True
            ),
        )
    )
    note = rows["combined"].note or ""
    assert "couldn't" not in note
    assert note == "One tab for all guitars. Lead and Rhythm splitting wasn't requested."
    assert rows["combined"].default_selected is True
