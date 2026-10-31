"""Column type detection and basic profiling."""
from dataclasses import dataclass, field, asdict

import re

import numpy as np
import pandas as pd

NUMERIC, CATEGORICAL, DATETIME = "numeric", "categorical", "datetime"
BOOLEAN, TEXT, ID, CONSTANT, EMPTY = "boolean", "text", "id", "constant", "empty"

BOOL_VALUES = {"true", "false", "yes", "no", "y", "n", "t", "f", "0", "1"}
ID_NAME = re.compile(r"(^|[_\s-])(id|key|uuid|guid|code|no|number)$|^id[_\s-]", re.I)
MONTHS = r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"


@dataclass
class ColumnProfile:
    name: str
    kind: str
    dtype: str
    n_missing: int
    pct_missing: float
    n_unique: int
    flags: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _try_numeric(s):
    if pd.api.types.is_numeric_dtype(s):
        return s
    cleaned = s.astype(str).str.replace(r"[,\s$₹€£%]", "", regex=True)
    conv = pd.to_numeric(cleaned, errors="coerce")
    return conv if conv.notna().sum() >= 0.9 * s.notna().sum() > 0 else None


def _try_datetime(s):
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    if pd.api.types.is_numeric_dtype(s):
        return None
    sample = s.dropna().astype(str).head(200)
    if sample.empty or sample.str.contains(rf"[-/:]|{MONTHS}", case=False, regex=True).mean() < 0.8:
        return None
    conv = pd.to_datetime(s, errors="coerce", format="mixed")
    return conv if conv.notna().sum() >= 0.9 * s.notna().sum() else None


def detect_kind(s):
    """Return (kind, parsed_series)."""
    nn = s.dropna()
    if nn.empty:
        return EMPTY, s
    nunique = nn.nunique()
    if nunique == 1:
        return CONSTANT, s
    if pd.api.types.is_bool_dtype(s) or (nunique == 2 and set(nn.astype(str).str.lower().unique()) <= BOOL_VALUES):
        return BOOLEAN, s
    dt = _try_datetime(s)
    if dt is not None:
        return DATETIME, dt
    num = _try_numeric(s)
    if num is not None:
        x = num.dropna()
        if len(nn) > 20 and (x % 1 == 0).all() and nunique / len(nn) > 0.95:
            u = np.sort(x.unique())
            sequential = len(u) > 1 and (np.diff(u) == 1).mean() > 0.9
            if sequential or ID_NAME.search(str(s.name)):
                return ID, num
        return NUMERIC, num
    if nunique == len(nn) and len(nn) > 20:
        return ID, s
    if nn.astype(str).str.len().mean() > 50 and nunique / len(nn) > 0.5:
        return TEXT, s
    return CATEGORICAL, s


def profile_column(s):
    kind, parsed = detect_kind(s)
    n, miss = len(s), int(s.isna().sum())
    p = ColumnProfile(str(s.name), kind, str(s.dtype), miss, round(100 * miss / n, 2) if n else 0.0, int(s.nunique()))
    if p.pct_missing > 50:
        p.flags.append("mostly missing")
    if kind == CONSTANT:
        p.flags.append("constant column")
    if kind == ID:
        p.flags.append("looks like an identifier")
    if (pd.api.types.is_string_dtype(s) or s.dtype == object) and kind in {NUMERIC, DATETIME}:
        p.flags.append(f"stored as text, parsed as {kind}")
    if kind == CATEGORICAL:
        strs = s.dropna().astype(str)
        raw, norm = strs.nunique(), strs.str.strip().str.lower().nunique()
        if norm < raw:
            p.flags.append(f"inconsistent categories ({raw - norm} merge candidates)")
        p.stats["top_values"] = {str(k): int(v) for k, v in s.value_counts().head(10).items()}
    if kind == NUMERIC:
        x = parsed.dropna()
        q1, q3 = x.quantile(0.25), x.quantile(0.75)
        iqr = q3 - q1
        out = int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
        p.stats = {"mean": float(x.mean()), "median": float(x.median()), "std": float(x.std()),
                   "min": float(x.min()), "max": float(x.max()), "skew": float(x.skew()),
                   "n_outliers_iqr": out}
    if kind == DATETIME:
        x = parsed.dropna()
        p.stats = {"min": str(x.min()), "max": str(x.max()), "span_days": int((x.max() - x.min()).days)}
    return p


def profile_frame(df):
    return {
        "n_rows": len(df),
        "n_cols": df.shape[1],
        "n_duplicate_rows": int(df.duplicated().sum()),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 2**20, 2),
        "columns": [asdict(profile_column(df[c])) for c in df.columns],
    }


def typed_frame(df, prof):
    """Copy of df with numeric/datetime columns converted to real dtypes."""
    out = df.copy()
    for c in prof["columns"]:
        if c["kind"] == NUMERIC:
            out[c["name"]] = _try_numeric(df[c["name"]])
        elif c["kind"] == DATETIME:
            out[c["name"]] = _try_datetime(df[c["name"]])
    return out
