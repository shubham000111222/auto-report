import io
import json
from types import SimpleNamespace

import openpyxl
import pandas as pd
from engine import clean, exporters, narrative
from engine.analysis import build_analysis
from engine.profiler import profile_frame


def frame():
    return pd.DataFrame({"city": ["Delhi", "delhi ", "Delhi", "Mumbai"] * 10, "v": range(40),
                         "empty": [None] * 40})


def test_clean_is_opt_in_and_logged():
    df = frame()
    prof = profile_frame(df)
    keys = dict(clean.suggest(df, prof))
    assert "normalize:city" in keys and "drop_col:empty" in keys
    out, log = clean.apply(df, {"normalize:city", "drop_col:empty"})
    assert set(out["city"]) == {"Delhi", "Mumbai"} and "empty" not in out.columns and len(log) == 2
    assert set(df["city"]) == {"Delhi", "delhi ", "Mumbai"}  # original untouched


def make_report():
    df = frame()
    prof = profile_frame(df)
    return df, prof, build_analysis(df, prof)


class FakeClient:
    def __init__(self, text):
        self.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)]))


def test_claude_narrative_and_number_verification():
    df, prof, report = make_report()
    payload = narrative.build_payload(prof, report, "f.csv")
    assert "Delhi" not in json.dumps(payload["columns"])  # no raw values in column stats
    good = f"The file has {prof['n_rows']} rows"
    reply = json.dumps({"summary": [good, "Revenue grew 9999 percent"], "recommendations": ["Fix city spellings"],
                        "caveats": ["Small sample"]})
    out = narrative.ask_claude(payload, client=FakeClient("Sure! " + reply))
    assert out["source"] == "claude"
    assert narrative.verify_numbers(out, payload) == ["9999"]


def test_rule_based_fallback():
    _, prof, report = make_report()
    n = narrative.rule_based(narrative.build_payload(prof, report, "f.csv"))
    assert n["summary"] and n["recommendations"] and n["source"] == "rule-based"


def test_html_export_is_escaped_and_complete():
    bad = "</script><script>alert(1)</script>"
    df = pd.DataFrame({"c": [bad, "b", "b", "c"] * 10, "v": range(40)})
    prof = profile_frame(df)
    rep = build_analysis(df, prof)
    html = exporters.render_html(rep, prof, narrative.rule_based(narrative.build_payload(prof, rep, "x")), "x.csv")
    assert "<script>alert(1)</script>" not in html
    assert "Executive summary" in html and "plotly" in html


def test_excel_export_blocks_formulas():
    df = pd.DataFrame({"a": ["=1+1", "+cmd", "ok"], "b": [1, 2, 3]})
    prof = profile_frame(df)
    rep = build_analysis(df, prof)
    data = exporters.to_excel(df, prof, rep, narrative.rule_based(narrative.build_payload(prof, rep, "x")), ["note"])
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert {"Summary", "Column profile", "Findings", "Changes", "Data"} <= set(wb.sheetnames)
    cell = wb["Data"]["A2"]
    assert cell.data_type == "s" and cell.value.startswith("'")


def test_text_stored_numbers_are_flagged():
    df = pd.DataFrame({"amt": [f"${i * 10:,}" for i in range(40)], "d": pd.date_range("2024-01-01", periods=40).astype(str)})
    flags = {c["name"]: c["flags"] for c in profile_frame(df)["columns"]}
    assert any("stored as text" in f for f in flags["amt"]) and any("stored as text" in f for f in flags["d"])
