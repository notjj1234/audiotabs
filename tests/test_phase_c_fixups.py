from pathlib import Path


def test_execute_pending_enables_gp5_export():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    assert "export_gp5=True" in source


def test_reopen_restores_pdf_details_from_meta():
    page = Path(__file__).resolve().parents[1] / "ui" / "tab_pdf.py"
    source = page.read_text(encoding="utf-8")
    reopen = source[source.find("def _reopen_run") : source.find("def _clear_failure_state")]
    assert 'run.get("details")' in reopen or "run.get('details')" in reopen
    assert "tab_pdf_details" in reopen


def test_write_run_metadata_accepts_details():
    from ui.common import write_run_metadata
    import inspect

    sig = inspect.signature(write_run_metadata)
    assert "details" in sig.parameters
