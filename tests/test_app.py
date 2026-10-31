"""Headless UI smoke test: sample dataset -> cleaning -> exports."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def test_sample_flow():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    [b for b in at.button if "sample" in b.label.lower()][0].click().run()
    assert not at.exception
    assert dict((m.label, m.value) for m in at.metric)["Rows"] == "3,015"

    at.sidebar.multiselect[0].set_value(["normalize:region", "drop_duplicates"]).run()
    assert not at.exception
    metrics = dict((m.label, m.value) for m in at.metric)
    assert metrics["Rows"] == "3,000" and metrics["Duplicate rows"] == "0"

    [b for b in at.button if b.label == "Build export files"][0].click().run()
    assert not at.exception
    assert {"report.html", "report.xlsx"} <= set(at.session_state["exports"][1])
