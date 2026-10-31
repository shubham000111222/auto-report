"""Run the whole pipeline on deliberately ugly files. Nothing may crash; only empty files may raise LoadError."""
import io
import os
import time

import numpy as np
import openpyxl
import pandas as pd
import pytest
from engine import exporters, narrative
from engine.analysis import build_analysis
from engine.loader import LoadError, load_file
from engine.profiler import profile_frame

BIG_ROWS = int(os.getenv("CORPUS_ROWS", 1_000_000))


def corpus():
    rng = np.random.default_rng(0)
    files = {
        "one_column.csv": b"x\n" + b"\n".join(str(i).encode() for i in range(50)),
        "all_nulls.csv": b"a,b\n" + b",\n" * 30,
        "latin1.csv": "name;city\nJosé;Zürich\nÅsa;Köln\n".encode("latin-1"),
        "mixed_encoding.csv": "name,city\nCafé,Paris\n".encode("utf-8") + b"Caf\xe9,Lyon\n",
        "single_row.csv": b"a,b,c\n1,2,3\n",
        "header_only.csv": b"a,b,c\n",
        "wide_500.csv": pd.DataFrame(rng.normal(size=(200, 500)),
                                     columns=[f"c{i}" for i in range(500)]).to_csv(index=False).encode(),
        "duplicate_headers.csv": b"a,a,a\n1,2,3\n4,5,6\n",
        "injection.csv": b"name,amt\n=HYPERLINK(\"http://x\"),1\n+cmd,2\nok,3\n",
    }
    big = pd.DataFrame({"id": np.arange(BIG_ROWS), "v": rng.normal(size=BIG_ROWS),
                        "g": rng.choice(list("abcde"), BIG_ROWS)})
    files["big.csv"] = big.to_csv(index=False).encode()
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Quarterly report"
    ws.merge_cells("A1:C1")
    ws.append([])
    ws.append(["region", "sales", "units"])
    for i in range(40):
        ws.append([["N", "S"][i % 2], 100 + i, i])
    ws.merge_cells("A5:A6")
    wb.create_sheet("empty_sheet")
    wb.save(buf)
    files["merged_cells.xlsx"] = buf.getvalue()
    return files


@pytest.fixture(scope="module")
def files():
    return corpus()


def pipeline(name, raw):
    for sheet, df in load_file(name, raw).items():
        prof = profile_frame(df)
        rep = build_analysis(df, prof)
        narr = narrative.rule_based(narrative.build_payload(prof, rep, name))
        exporters.render_html(rep, prof, narr, name)
        exporters.to_excel(df.head(1000), prof, rep, narr)


@pytest.mark.parametrize("name", ["one_column.csv", "all_nulls.csv", "latin1.csv", "mixed_encoding.csv", "single_row.csv",
                          "wide_500.csv", "duplicate_headers.csv", "injection.csv", "merged_cells.xlsx"])
def test_ugly_file(files, name):
    pipeline(name, files[name])


def test_empty_file_is_a_clean_error():
    with pytest.raises(LoadError):
        load_file("empty.csv", b"")


def test_header_only_is_a_clean_error(files):
    with pytest.raises(LoadError):
        load_file("header_only.csv", files["header_only.csv"])


def test_big_file_is_fast_enough(files):
    t = time.time()
    pipeline("big.csv", files["big.csv"])
    assert time.time() - t < 120
