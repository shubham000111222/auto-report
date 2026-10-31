"""Chart rules: one function per chart type."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

LAYOUT = dict(margin=dict(l=10, r=10, t=50, b=10))


def _done(fig):
    fig.update_layout(**LAYOUT)
    return fig


def numeric_hist(s: pd.Series):
    df = s.dropna().to_frame(str(s.name))
    return _done(px.histogram(df, x=str(s.name), marginal="box", title=f"Distribution of {s.name}"))


def categorical_chart(s: pd.Series):
    vc = s.dropna().astype(str).value_counts()
    if len(vc) <= 5:
        fig = px.pie(names=vc.index, values=vc.values, hole=0.45, title=f"Share by {s.name}")
        return _done(fig)
    top = vc.head(10)
    if len(vc) > 10:
        top = pd.concat([top, pd.Series({"Other": vc.iloc[10:].sum()})])
    d = pd.DataFrame({s.name: top.index, "count": top.values})
    fig = px.bar(d.iloc[::-1], x="count", y=s.name, orientation="h", title=f"Top values: {s.name}")
    return _done(fig)


def trend_line(series: pd.Series, name: str, noun: str, agg: str = "sum"):
    d = series.reset_index()
    d.columns = ["period", name]
    return _done(px.line(d, x="period", y=name, title=f"{'Average' if agg == 'mean' else 'Total'} {name} per {noun}"))


def corr_heatmap(corr: pd.DataFrame):
    return _done(px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                           zmin=-1, zmax=1, title="Correlation matrix"))


def scatter_trend(df: pd.DataFrame, x: str, y: str):
    d = df[[x, y]].dropna()
    fig = px.scatter(d, x=x, y=y, opacity=0.6, title=f"{y} vs {x}")
    if len(d) > 2 and d[x].nunique() > 1:
        m, b = np.polyfit(d[x], d[y], 1)
        xs = np.array([d[x].min(), d[x].max()])
        fig.add_trace(go.Scatter(x=xs, y=m * xs + b, mode="lines", name="trend", line=dict(width=3)))
    return _done(fig)


def missing_bar(columns: list[dict]):
    d = pd.DataFrame([{"column": c["name"], "missing %": c["pct_missing"]} for c in columns
                      if c["pct_missing"] > 0]).sort_values("missing %")
    return _done(px.bar(d, x="missing %", y="column", orientation="h", title="Missing values by column"))


def segment_bar(means: pd.Series, cat: str, num: str):
    d = means.reset_index()
    d.columns = [cat, num]
    return _done(px.bar(d, x=cat, y=num, title=f"Average {num} by {cat}"))
