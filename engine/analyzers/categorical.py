import pandas as pd


def analyze(s: pd.Series) -> dict:
    vc = s.dropna().astype(str).value_counts()
    total = int(vc.sum())
    top, share = vc.index[0], 100 * vc.iloc[0] / total
    takeaway = f"{s.name}: '{top}' is the most common value ({share:.0f}% of rows) among {len(vc)} distinct values."
    return {"counts": vc, "takeaway": takeaway}
