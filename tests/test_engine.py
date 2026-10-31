import io
import pandas as pd
import pytest
from engine.loader import LoadError, load_file
from engine.profiler import profile_frame


def kinds(df):
    return {c["name"]: c["kind"] for c in profile_frame(df)["columns"]}


def test_empty_file():
    with pytest.raises(LoadError):
        load_file("x.csv", b"")


def test_bad_extension():
    with pytest.raises(LoadError):
        load_file("x.exe", b"abc")


def test_semicolon_and_latin1():
    raw = "city;sales\nDelhi;10\nMumbai;20\nCafé;30\n".encode("latin-1")
    df = load_file("a.csv", raw)["data"]
    assert list(df.columns) == ["city", "sales"] and len(df) == 3


def test_types():
    n = 60
    df = pd.DataFrame({
        "id": range(1, n + 1),
        "amount": [f"${i*10:,}" for i in range(n)],
        "date": pd.date_range("2024-01-01", periods=n).astype(str),
        "city": ["Delhi", "delhi ", "Mumbai"] * (n // 3),
        "flag": ["yes", "no"] * (n // 2),
        "const": ["a"] * n,
    })
    k = kinds(df)
    assert k["id"] == "id" and k["amount"] == "numeric" and k["date"] == "datetime"
    assert k["city"] == "categorical" and k["flag"] == "boolean" and k["const"] == "constant"
    flags = {c["name"]: c["flags"] for c in profile_frame(df)["columns"]}
    assert any("inconsistent" in f for f in flags["city"])


def test_excel_with_title_rows():
    df = pd.DataFrame([["Report", None, None], [None, None, None], ["a", "b", "c"], [1, 2, 3], [4, 5, 6]])
    buf = io.BytesIO()
    df.to_excel(buf, header=False, index=False)
    out = load_file("t.xlsx", buf.getvalue())["Sheet1"]
    assert list(out.columns) == ["a", "b", "c"] and len(out) == 2


def test_all_null_and_one_column():
    assert kinds(pd.DataFrame({"x": [None] * 5}))["x"] == "empty"
    assert profile_frame(pd.DataFrame({"y": range(30)}))["n_cols"] == 1
