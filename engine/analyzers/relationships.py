import numpy as np
import pandas as pd
from ..utils import fmt


def top_pairs(df: pd.DataFrame, threshold: float = 0.5):
    corr = df.corr(numeric_only=True)
    pairs = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r) and abs(r) >= threshold:
                pairs.append((a, b, float(r)))
    pairs.sort(key=lambda t: -abs(t[2]))
    return corr, pairs


def pair_takeaway(a: str, b: str, r: float) -> str:
    label = "very strong" if abs(r) >= 0.8 else "strong" if abs(r) >= 0.65 else "moderate"
    sign = "positive" if r > 0 else "negative"
    return f"{a} and {b} have a {label} {sign} correlation (r = {r:.2f})."


def segment(df: pd.DataFrame, cat: str, num: str):
    g = df.groupby(cat, observed=True)[num].mean().dropna().sort_values(ascending=False)
    if len(g) < 2:
        return None
    hi, lo = g.index[0], g.index[-1]
    text = f"'{hi}' has the highest average {num} ({fmt(g.iloc[0])}); '{lo}' has the lowest ({fmt(g.iloc[-1])})"
    if g.iloc[-1] > 0 and g.iloc[0] > 0:
        text += f", a gap of {g.iloc[0] / g.iloc[-1]:.1f}x"
    return {"means": g, "takeaway": text + "."}
