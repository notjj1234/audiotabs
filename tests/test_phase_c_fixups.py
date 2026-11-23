from pathlib import Path

from app.server.jobs import JobManager


def test_job_manager_enables_gp5_via_real_runner_contract():
    # Jobs always request GP5 on the real pipeline path.
    source = Path(__file__).resolve().parents[1] / "app" / "server" / "jobs.py"
    text = source.read_text(encoding="utf-8")
    assert "export_gp5=True" in text


def test_write_run_metadata_accepts_details():
    import inspect

    from app.server.store import write_run_metadata

    sig = inspect.signature(write_run_metadata)
    assert "details" in sig.parameters


def test_job_manager_constructible(tmp_path):
    manager = JobManager(tmp_path, runner=lambda **kwargs: {})
    assert manager.get("missing") is None
