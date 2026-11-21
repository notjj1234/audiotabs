import pytest


def test_accuracy_feedback_roundtrip():
    from audio_to_tab.accuracy_feedback import (
        get_accuracy_feedback,
        set_accuracy_feedback,
    )

    state: dict = {}
    assert get_accuracy_feedback(state, "run-a") is None
    set_accuracy_feedback(state, "run-a", "yes")
    assert get_accuracy_feedback(state, "run-a") == "yes"
    set_accuracy_feedback(state, "run-a", "no")
    assert get_accuracy_feedback(state, "run-a") == "no"
    set_accuracy_feedback(state, "run-b", "yes")
    assert get_accuracy_feedback(state, "run-a") == "no"
    assert get_accuracy_feedback(state, "run-b") == "yes"


def test_accuracy_feedback_rejects_bad_value():
    from audio_to_tab.accuracy_feedback import set_accuracy_feedback

    with pytest.raises(ValueError):
        set_accuracy_feedback({}, "run-a", "maybe")
