import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from engine import clean, exporters, narrative
from engine.analysis import SECTIONS, build_analysis
from engine.loader import LoadError, load_file
from engine.profiler import profile_frame

st.set_page_config(page_title="Auto Analytics Report", layout="wide")
st.title("Auto Analytics Report")
st.caption("Upload any CSV or Excel file and get a full analytics report with charts, plain-language findings and exports.")

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "retail_sales.csv"
HAS_PDF = importlib.util.find_spec("playwright") is not None

TITLES = {"quality": "Data quality", "numeric": "Numeric columns", "categorical": "Categorical columns",
          "trends": "Trends over time", "relationships": "Relationships", "segments": "Segment comparisons"}


@st.cache_data(show_spinner=False, ttl=3600, max_entries=8)  # uploads expire from memory after 1 hour
def get_sheets(name: str, raw: bytes):
    return load_file(name, raw)


@st.cache_data(show_spinner="Analyzing...", ttl=3600, max_entries=8)
def run(name: str, raw: bytes, sheet: str, fixes: tuple):
    df0 = get_sheets(name, raw)[sheet]
    if not fixes:
        prof = profile_frame(df0)
        return df0, [], prof, build_analysis(df0, prof)
    df, log = clean.apply(df0, set(fixes))
    prof = profile_frame(df)
    return df, log, prof, build_analysis(df, prof)


up = st.file_uploader("Upload CSV or Excel", type=["csv", "tsv", "txt", "xlsx", "xls", "json"])
name = raw = None
if up:
    name, raw = up.name, up.getvalue()
else:
    if st.button("Or try the sample dataset (synthetic retail orders)"):
        st.session_state["sample"] = True
    if st.session_state.get("sample"):
        name, raw = SAMPLE.name, SAMPLE.read_bytes()
        st.info(f"Using the sample dataset: {name}")

if name:
    try:
        names = list(get_sheets(name, raw))
        sheet = st.selectbox("Sheet", names) if len(names) > 1 else names[0]
        df0, _, prof0, _ = run(name, raw, sheet, ())
    except LoadError as e:
        st.error(str(e))
        st.stop()

    # sidebar: cleaning + AI summary
    with st.sidebar:
        st.header("Cleaning")
        sugg = clean.suggest(df0, prof0)
        labels = dict(sugg)
        chosen = st.multiselect("Suggested fixes (nothing changes unless you pick it)", list(labels),
                                format_func=labels.get) if sugg else []
        if not sugg:
            st.caption("No fixes suggested.")
        st.header("AI summary")
        st.caption("Claude receives computed statistics and findings only, never your raw rows. "
                   "Category names that appear in findings are included.")
        api_key = st.text_input("Anthropic API key (optional)", type="password",
                                help="Used only for this request and never stored. Without a key, a rule-based summary is shown.")

    df, log, prof, report = run(name, raw, sheet, tuple(sorted(chosen)))
    payload = narrative.build_payload(prof, report, name)
    skey = f"{name}|{sheet}|{sorted(chosen)}"
    with st.sidebar:
        if st.button("Write summary with Claude", disabled=not api_key):
            try:
                with st.spinner("Asking Claude..."):
                    st.session_state["narr"] = (skey, narrative.ask_claude(payload, api_key))
            except Exception as e:
                st.error(f"Claude request failed: {e}")
    saved = st.session_state.get("narr")
    narr = saved[1] if saved and saved[0] == skey else narrative.rule_based(payload)
    unverified = narrative.verify_numbers(narr, payload) if narr["source"] == "claude" else []

    a, b, c, d = st.columns(4)
    a.metric("Rows", f"{prof['n_rows']:,}")
    b.metric("Columns", prof["n_cols"])
    c.metric("Duplicate rows", prof["n_duplicate_rows"])
    d.metric("Memory (MB)", prof["memory_mb"])
    if log:
        st.info("Cleaning applied: " + "; ".join(log))

    tab_report, tab_profile, tab_data = st.tabs(["Report", "Column profile", "Data"])
    with tab_report:
        st.header("Executive summary")
        st.caption(f"Written by: {narr['source']}")
        for s in narr["summary"]:
            st.write("• " + s)
        if unverified:
            st.warning("These numbers in the AI summary don't match any computed statistic: "
                       + ", ".join(unverified))

        st.subheader("Export")
        use_pdf = st.checkbox("Include PDF", disabled=not HAS_PDF,
                              help=None if HAS_PDF else "Install Playwright to enable PDF export (see README).")
        if st.button("Build export files"):
            with st.spinner("Building..."):
                html = exporters.render_html(report, prof, narr, name, log, unverified)
                files = {"report.html": html.encode("utf-8"),
                         "report.xlsx": exporters.to_excel(df, prof, report, narr, log)}
                if use_pdf:
                    try:
                        files["report.pdf"] = exporters.to_pdf(html)
                    except Exception as e:
                        st.error(str(e))
                st.session_state["exports"] = (skey, files)
        ex = st.session_state.get("exports")
        if ex and ex[0] == skey:
            cols = st.columns(len(ex[1]))
            for col, (fname, data) in zip(cols, ex[1].items()):
                col.download_button(f"Download {fname}", data, file_name=fname)

        for key in SECTIONS:
            items = report[key]
            if not items:
                continue
            st.header(TITLES[key])
            for it in items:
                if it["figure"] is not None:
                    st.plotly_chart(it["figure"], width="stretch")
                    st.caption(it["takeaway"])
                else:
                    st.write("• " + it["takeaway"])
        st.header("Recommendations")
        for s in narr["recommendations"]:
            st.write("• " + s)
        st.header("Caveats")
        for s in narr["caveats"]:
            st.write("• " + s)
    with tab_profile:
        st.dataframe(pd.DataFrame([
            {"column": x["name"], "type": x["kind"], "missing %": x["pct_missing"],
             "unique": x["n_unique"], "flags": "; ".join(x["flags"])}
            for x in prof["columns"]
        ]), width="stretch", hide_index=True)
    with tab_data:
        st.dataframe(df.head(100), width="stretch")

st.divider()
st.caption("Privacy: files are processed in memory and not saved by this app; cached results expire after 1 hour. "
           "If you use the AI summary, only computed statistics and findings are sent to Anthropic, never your raw rows.")
