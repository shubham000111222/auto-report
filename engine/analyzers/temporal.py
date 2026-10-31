import re

import pandas as pd
from ..utils import fmt


def pick_freq(span_days: int):
    if span_days <= 60:
        return "D", "day"
    if span_days <= 400:
        return "W", "week"
    return "MS", "month"


MEAN_NAMES = re.compile(r"price|rate|discount|ratio|pct|percent|score|avg|average|mean|age|days|temp|margin|share", re.I)


def choose_agg(name: str, s: pd.Series) -> str:
    """Rates, prices and durations are averaged; everything else is treated as additive and summed."""
    x = s.dropna()
    if len(x) and x.between(0, 1).all() or MEAN_NAMES.search(str(name)):
        return "mean"
    return "sum"


def analyze(df: pd.DataFrame, date_col: str, value_col: str):
    d = df[[date_col, value_col]].dropna()
    if len(d) < 3:
        return None
    span = (d[date_col].max() - d[date_col].min()).days
    if span < 1:
        return None
    freq, noun = pick_freq(span)
    g = d.set_index(date_col)[value_col].resample(freq)
    agg = choose_agg(value_col, d[value_col])
    total, counts = (g.mean() if agg == "mean" else g.sum()), g.count()
    if len(total) < 3:
        return None
    mean = total.mean()
    peak = total.idxmax()
    text = f"{'Average ' if agg == 'mean' else ''}{value_col} peaks in the {noun} of {peak:%Y-%m-%d} at {fmt(total.max())}"
    text += f", {total.max() / mean:.1f}x the average {noun}." if mean > 0 else "."
    half = len(total) // 2
    first, last = total.iloc[:half].mean(), total.iloc[half:].mean()
    if first > 0:
        change = (last / first - 1) * 100
        if abs(change) < 1:
            text += " The second half of the period is roughly flat compared with the first."
        else:
            direction = "higher" if change > 0 else "lower"
            text += f" The second half of the period is {abs(change):.0f}% {direction} than the first half."
    gaps = int((counts == 0).sum())
    if gaps:
        text += f" {gaps} {noun}s have no records."
    return {"series": total, "freq": freq, "noun": noun, "agg": agg, "takeaway": text}
