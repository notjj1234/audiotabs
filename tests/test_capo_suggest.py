def test_suggest_capo_skips_friendly_and_unknown():
    from audio_to_tab.capo_suggest import suggest_capo_for_key

    assert suggest_capo_for_key("G major") is None
    assert suggest_capo_for_key("A minor") is None
    assert suggest_capo_for_key("Unknown") is None
    assert suggest_capo_for_key("") is None


def test_suggest_capo_finds_lowest_friendly():
    from audio_to_tab.capo_suggest import suggest_capo_for_key

    # F major → Capo 1 plays as E major (friendly)
    assert suggest_capo_for_key("F major") == 1
    # F# major → Capo 2 plays as E major
    assert suggest_capo_for_key("F# major") == 2
    # Already on that capo → skip to next or None if only match equals current
    assert suggest_capo_for_key("F major", current_capo=1) == 3
