import numpy as np
import pandas as pd
from engine.analysis import build_analysis
from engine.profiler import profile_frame


def run(df):
    return build_analysis(df, profile_frame(df))


def make():
    rng = np.random.default_rng(1)
    n = 400
    x = rng.normal(50, 10, n)
    return pd.DataFrame({
        "order_id": range(1, n + 1),
        "date": pd.date_range("2023-01-01", periods=n).astype(str),
        "city": rng.choice(["Delhi", "Mumbai", "Pune"], n),
        "price": x,
        "revenue": x * 3 + rng.normal(0, 5, n),
        "qty": rng.integers(1, 10, n),
    })


def test_full_report_has_all_sections():
    rep = run(make())
    for k in ["quality", "numeric", "categorical", "trends", "relationships", "segments"]:
        assert rep[k], k
    assert all(it["takeaway"] for items in rep.values() for it in items)
    assert any("price" in it["takeaway"] and "revenue" in it["takeaway"] and "correlation" in it["takeaway"]
               for it in rep["relationships"])


def test_trend_takeaway_mentions_peak_and_ratio():
    t = run(make())["trends"][0]["takeaway"]
    assert "peaks" in t and "x the average" in t


def test_edge_cases_do_not_crash():
    run(pd.DataFrame({"x": [None] * 10}))
    run(pd.DataFrame({"y": range(30)}))
    run(pd.DataFrame({"a": ["u", "v"] * 20}))
    run(pd.DataFrame({"a": [1.0] * 30, "b": range(30)}))


def test_id_with_duplicates_and_rates_handled():
    from engine.analyzers import temporal
    n = 100
    df = pd.DataFrame({"order_id": list(range(1, n + 1)) + [5, 6, 7], "v": range(n + 3)})
    assert {c["name"]: c["kind"] for c in profile_frame(df)["columns"]}["order_id"] == "id"
    assert temporal.choose_agg("discount", pd.Series([0, 0.1, 0.2])) == "mean"
    assert temporal.choose_agg("unit_price", pd.Series([10, 200])) == "mean"
    assert temporal.choose_agg("revenue", pd.Series([10, 200])) == "sum"


def test_sample_dataset_report():
    from pathlib import Path
    from engine.loader import load_file
    raw = (Path(__file__).resolve().parents[1] / "sample_data" / "retail_sales.csv").read_bytes()
    df = load_file("retail_sales.csv", raw)["data"]
    prof = profile_frame(df)
    kinds = {c["name"]: c["kind"] for c in prof["columns"]}
    assert kinds["order_id"] == "id" and kinds["order_date"] == "datetime" and prof["n_duplicate_rows"] == 15
    rep = build_analysis(df, prof)
    assert any("inconsistent" in it["takeaway"] for it in rep["quality"])
    assert len({it["takeaway"] for it in rep["relationships"]}) == len(rep["relationships"])  # no repeated findings
