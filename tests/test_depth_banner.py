from pathlib import Path


def test_depth_banner_actions_omit_unavailable(tmp_path: Path):
    from audio_to_tab.depth_banner import depth_banner_actions

    assert depth_banner_actions(artifacts=None, details=None, has_midi=False) == []

    gp5 = tmp_path / "song.gp5"
    gp5.write_bytes(b"gp5")
    actions = depth_banner_actions(
        artifacts={"gp5": str(gp5)},
        details={"separate": False},
        has_midi=True,
    )
    ids = [item["id"] for item in actions]
    assert ids == ["piano_roll", "try_separation", "guitar_pro"]

    no_sep = depth_banner_actions(
        artifacts={"gp5": str(gp5)},
        details={"separate": True},
        has_midi=False,
    )
    assert [item["id"] for item in no_sep] == ["guitar_pro"]
