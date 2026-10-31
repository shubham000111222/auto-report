def fmt(v: float) -> str:
    """Human-friendly number formatting for takeaways."""
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:.2f}M"
    if a >= 100:
        return f"{v:,.0f}"
    return f"{v:.3g}"
