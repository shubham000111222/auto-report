"""Suggest fixes; apply only the ones the user ticks, and log every change."""
import pandas as pd


def suggest(df: pd.DataFrame, prof: dict) -> list[tuple[str, str]]:
    """Return [(key, label)]. Nothing is changed until apply() is called with chosen keys."""
    out = []
    for c in prof["columns"]:
        if c["kind"] == "empty":
            out.append((f"drop_col:{c['name']}", f"Drop column '{c['name']}' (all values missing)"))
        if any(f.startswith("inconsistent categories") for f in c["flags"]):
            out.append((f"normalize:{c['name']}", f"Normalize case/spacing in '{c['name']}' ({c['flags'][-1]})"))
    if prof["n_duplicate_rows"]:
        out.append(("drop_duplicates", f"Remove {prof['n_duplicate_rows']} duplicate rows"))
    return out


def _normalize(df: pd.DataFrame, col: str):
    s = df[col]
    mask = s.notna()
    orig = s[mask].astype(str)
    stripped = orig.str.strip()
    key = stripped.str.lower()
    canon = stripped.groupby(key).agg(lambda x: x.value_counts().idxmax())
    new = key.map(canon)
    changed = int((new != orig).sum())
    df[col] = s.astype(object)
    df.loc[mask, col] = new
    return changed


def apply(df: pd.DataFrame, keys: set[str]):
    """Return (new_df, change_log). Order: normalize, drop columns, then duplicates."""
    out, log = df.copy(), []
    for k in sorted(k for k in keys if k.startswith("normalize:")):
        col = k.split(":", 1)[1]
        if col in out.columns:
            log.append(f"Normalized '{col}': {_normalize(out, col)} cells changed")
    for k in sorted(k for k in keys if k.startswith("drop_col:")):
        col = k.split(":", 1)[1]
        if col in out.columns:
            out = out.drop(columns=col)
            log.append(f"Dropped column '{col}'")
    if "drop_duplicates" in keys:
        n = len(out)
        out = out.drop_duplicates().reset_index(drop=True)
        log.append(f"Removed {n - len(out)} duplicate rows")
    return out, log
