"""Parse uploaded files into DataFrames: encoding, delimiter, sheets."""
import csv
import io
import json
from pathlib import Path

import pandas as pd
from charset_normalizer import from_bytes

MAX_BYTES = 200 * 1024 * 1024  # 200 MB cap
ALLOWED = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json"}


class LoadError(ValueError):
    pass


def _read_csv(raw: bytes) -> pd.DataFrame:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # detectors are unreliable on tiny samples; fall back to cp1252 there
        best = from_bytes(raw).best() if len(raw) >= 4096 else None
        text = raw.decode(best.encoding if best else "cp1252", errors="replace")
    sample = text[:50_000]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    return pd.read_csv(io.StringIO(text), sep=delim, low_memory=False)


def _detect_header_row(df: pd.DataFrame, max_scan: int = 10) -> pd.DataFrame:
    """If the first rows are titles/notes, promote the first full row to header."""
    for i in range(min(max_scan, len(df))):
        row = df.iloc[i]
        if row.notna().mean() >= 0.8 and row.astype(str).str.strip().ne("").all():
            out = df.iloc[i + 1:].reset_index(drop=True)
            out.columns = [str(c).strip() for c in row]
            return out
    return df


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols, seen = [], {}
    for i, c in enumerate(df.columns):
        c = str(c).strip() or f"column_{i}"
        seen[c] = seen.get(c, 0) + 1
        cols.append(c if seen[c] == 1 else f"{c}_{seen[c]}")
    df.columns = cols
    return df


def load_file(name: str, raw: bytes) -> dict[str, pd.DataFrame]:
    """Return {sheet_name: DataFrame}. CSV/JSON return a single 'data' entry."""
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise LoadError(f"Unsupported file type: {ext or 'none'}")
    if not raw:
        raise LoadError("File is empty")
    if len(raw) > MAX_BYTES:
        raise LoadError(f"File exceeds {MAX_BYTES // 2**20} MB limit")

    if ext in {".csv", ".tsv", ".txt"}:
        sheets = {"data": _read_csv(raw)}
    elif ext == ".json":
        sheets = {"data": pd.json_normalize(json.loads(raw.decode("utf-8")))}
    else:
        # pandas returns cached cell values; formulas/macros are never executed
        book = pd.read_excel(io.BytesIO(raw), sheet_name=None, header=None)
        sheets = {}
        for sheet, df in book.items():
            df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
            if not df.empty:
                sheets[sheet] = _detect_header_row(df)

    sheets = {k: _clean_columns(v) for k, v in sheets.items() if not v.empty}
    if not sheets:
        raise LoadError("No data found in file")
    return sheets
