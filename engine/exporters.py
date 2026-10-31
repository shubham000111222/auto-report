"""HTML, Excel and PDF export."""
import datetime as dt
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from plotly.offline import get_plotlyjs_version

ROOT = Path(__file__).resolve().parents[1]
EXPORT_ORDER = [("quality", "Data quality"), ("numeric", "Column profiles: numeric"),
                ("categorical", "Column profiles: categorical"), ("relationships", "Relationships"),
                ("trends", "Trends over time"), ("segments", "Segment comparisons")]


def render_html(report: dict, prof: dict, narrative: dict, filename: str,
                change_log=(), unverified=()) -> str:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)  # escape user-derived text
    sections = []
    for key, title in EXPORT_ORDER:
        items = []
        for it in report.get(key, []):
            div = None
            if it["figure"] is not None:
                fig = type(it["figure"])(it["figure"])  # copy
                fig.update_layout(template="plotly_white")
                div = fig.to_html(full_html=False, include_plotlyjs=False)
            items.append({"div": div, "takeaway": it["takeaway"]})
        if items:
            sections.append({"title": title, "entries": items})
    return env.get_template("report.html.j2").render(
        filename=filename, prof=prof, narrative=narrative, sections=sections, date=dt.date.today().isoformat(),
        plotly_js=get_plotlyjs_version(), change_log=list(change_log), unverified=list(unverified))


def _safe(df: pd.DataFrame) -> pd.DataFrame:
    """Neutralise spreadsheet formula injection: text starting with = + - @ becomes literal text."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_string_dtype(out[c]) or out[c].dtype == object:
            out[c] = out[c].map(lambda v: "'" + v if isinstance(v, str) and v[:1] in "=+-@" else v)
    out.columns = [("'" + c if c[:1] in "=+-@" else c) for c in map(str, out.columns)]
    return out


def to_excel(df: pd.DataFrame, prof: dict, report: dict, narrative: dict, change_log=()) -> bytes:
    import io
    buf = io.BytesIO()
    summary = pd.DataFrame({"Summary": narrative["summary"]})
    recs = pd.DataFrame({"Recommendations": narrative["recommendations"]})
    profile = pd.DataFrame([{"column": c["name"], "type": c["kind"], "missing %": c["pct_missing"],
                             "unique": c["n_unique"], "flags": "; ".join(c["flags"])} for c in prof["columns"]])
    findings = pd.DataFrame([{"section": k, "title": it["title"], "takeaway": it["takeaway"]}
                             for k, items in report.items() for it in items])
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        _safe(summary).to_excel(xw, sheet_name="Summary", index=False)
        _safe(recs).to_excel(xw, sheet_name="Summary", index=False, startcol=2)
        _safe(profile).to_excel(xw, sheet_name="Column profile", index=False)
        _safe(findings).to_excel(xw, sheet_name="Findings", index=False)
        if change_log:
            pd.DataFrame({"Changes applied": list(change_log)}).to_excel(xw, sheet_name="Changes", index=False)
        _safe(df.head(1_048_575)).to_excel(xw, sheet_name="Data", index=False)  # Excel row limit
        for ws in xw.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(60, max(10, max(len(str(c.value or "")) for c in col[:200]) + 2))
    return buf.getvalue()


def to_pdf(html: str) -> bytes:
    """Render the HTML report to PDF with Playwright (run in a subprocess: safe inside Streamlit on Windows)."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d, "r.html"), Path(d, "r.pdf")
        src.write_text(html, encoding="utf-8")
        p = subprocess.run([sys.executable, "-m", "engine.pdf_worker", str(src), str(dst)],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        if p.returncode != 0 or not dst.exists():
            raise RuntimeError("PDF export needs Playwright: run `pip install playwright` and "
                               "`playwright install chromium`.\n" + p.stderr[-500:])
        return dst.read_bytes()
