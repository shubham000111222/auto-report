import pandas as pd
from ..utils import fmt


def analyze(s: pd.Series) -> dict:
    x = s.dropna()
    q1, q3 = x.quantile(0.25), x.quantile(0.75)
    iqr = q3 - q1
    n_out = int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    skew = float(x.skew()) if len(x) > 2 else 0.0
    shape = "roughly symmetric" if abs(skew) < 0.5 else ("right-skewed" if skew > 0 else "left-skewed")
    takeaway = f"{s.name}: median {fmt(x.median())}, mean {fmt(x.mean())} ({shape})."
    if n_out:
        takeaway += f" {n_out} outliers ({100 * n_out / len(x):.1f}% of values) by the IQR rule."
    return {"median": float(x.median()), "mean": float(x.mean()), "skew": skew,
            "n_outliers": n_out, "takeaway": takeaway}


def spread(s: pd.Series) -> float:
    """Coefficient of variation, used to rank columns by how informative they are."""
    x = s.dropna()
    if len(x) < 2 or x.mean() == 0:
        return 0.0
    return float(abs(x.std() / x.mean()))
