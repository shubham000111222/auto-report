"""Orchestrates analyzers + charts into report sections.
Every section item: {"title", "figure" (or None), "takeaway"}; all numbers are computed here, not by an LLM."""
import pandas as pd

from . import charts
from .analyzers import categorical, numeric, relationships, temporal
from .profiler import typed_frame

SAMPLE = 50_000
SECTIONS = ["quality", "numeric", "categorical", "trends", "relationships", "segments"]


def build_analysis(df: pd.DataFrame, prof: dict, max_cols: int = 12) -> dict:
    typed = typed_frame(df, prof)
    chart_df = typed.sample(SAMPLE, random_state=0) if len(typed) > SAMPLE else typed
    kinds = {c["name"]: c["kind"] for c in prof["columns"]}
    num = sorted([c for c, k in kinds.items() if k == "numeric"],
                 key=lambda c: numeric.spread(typed[c]), reverse=True)
    cat = sorted([c for c, k in kinds.items() if k in ("categorical", "boolean")],
                 key=lambda c: typed[c].nunique())
    dts = [c for c, k in kinds.items() if k == "datetime"]
    out = {k: [] for k in SECTIONS}

    # data quality
    cols = prof["columns"]
    missing = [c for c in cols if c["pct_missing"] > 0]
    if missing:
        worst = max(missing, key=lambda c: c["pct_missing"])
        out["quality"].append({"title": "Missing values", "figure": charts.missing_bar(cols),
                               "takeaway": f"{len(missing)} of {len(cols)} columns have missing values; "
                                           f"worst is {worst['name']} ({worst['pct_missing']}% missing)."})
    dup = prof["n_duplicate_rows"]
    out["quality"].append({"title": "Duplicates", "figure": None,
                           "takeaway": f"{dup} duplicate rows ({100 * dup / max(prof['n_rows'], 1):.1f}%)." if dup
                           else "No duplicate rows found."})
    for c in cols:
        for f in c["flags"]:
            if f.startswith(("inconsistent", "stored as text", "constant", "looks like")):
                out["quality"].append({"title": f"Issue: {c['name']}", "figure": None,
                                       "takeaway": f"{c['name']}: {f}."})

    # per-column profiles
    for c in num[:max_cols]:
        a = numeric.analyze(typed[c])
        out["numeric"].append({"title": c, "figure": charts.numeric_hist(chart_df[c]), "takeaway": a["takeaway"]})
    for c in cat[:max_cols]:
        a = categorical.analyze(typed[c])
        out["categorical"].append({"title": c, "figure": charts.categorical_chart(typed[c]), "takeaway": a["takeaway"]})

    # trends
    if dts:
        for v in num[:3]:
            a = temporal.analyze(typed, dts[0], v)
            if a:
                out["trends"].append({"title": f"{v} over time", "figure": charts.trend_line(a["series"], v, a["noun"], a["agg"]),
                                      "takeaway": a["takeaway"]})

    # relationships
    if len(num) >= 2:
        corr, pairs = relationships.top_pairs(typed[num[:max_cols]])
        if pairs:
            a, b, r = pairs[0]
            heat = (f"{len(pairs)} numeric pair{'s' if len(pairs) > 1 else ''} show a notable correlation "
                    f"(|r| >= 0.5); the strongest is {a} and {b} (r = {r:.2f}).")
        else:
            heat = "No notable correlations (|r| >= 0.5) between numeric columns."
        out["relationships"].append({"title": "Correlation heatmap", "figure": charts.corr_heatmap(corr), "takeaway": heat})
        for a, b, r in pairs[:5]:
            out["relationships"].append({"title": f"{b} vs {a}", "figure": charts.scatter_trend(chart_df, a, b),
                                         "takeaway": relationships.pair_takeaway(a, b, r)})

    # segments
    seg_cats = [c for c in cat if 2 <= typed[c].nunique() <= 15][:3]
    for c in seg_cats:
        for v in num[:2]:
            s = relationships.segment(typed, c, v)
            if s:
                out["segments"].append({"title": f"{v} by {c}", "figure": charts.segment_bar(s["means"], c, v),
                                        "takeaway": s["takeaway"]})
    return out
