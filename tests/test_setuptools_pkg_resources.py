"""resampy (via basic-pitch) still imports pkg_resources; setuptools 81+ drops it."""

from __future__ import annotations

from importlib.metadata import version

from packaging.version import Version


def test_setuptools_keeps_pkg_resources_for_basic_pitch():
    import pkg_resources  # noqa: F401 — import is the contract

    assert Version(version("setuptools")) < Version("81")
