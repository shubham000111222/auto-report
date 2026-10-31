# Auto Analytics Report

Upload any CSV or Excel file and get a complete analytics report: automatic column-type detection, data-quality checks, charts chosen by data type, plain-language findings, and one-click export to HTML, Excel and PDF.

**Live demo:** _add your Streamlit Cloud link here_

<!-- Add a screenshot at docs/screenshot.png, then uncomment:
![Report preview](docs/screenshot.png)
-->

## What it does

- **Reads messy files:** CSV, TSV, JSON, XLSX, XLS. Detects encoding and delimiter, handles multiple sheets, skips title rows above the header, and enforces a size cap.
- **Profiles every column:** numeric, categorical, datetime, boolean, text, ID, constant or empty. Flags text-stored numbers, inconsistent categories ("Delhi" vs "delhi "), mostly-missing columns, duplicates and identifiers.
- **Cleans only when you say so:** fixes are suggested in the sidebar, nothing changes unless ticked, and every change is logged and shown in the report.
- **Charts from column types:** histogram with box plot, top-10 bars (donut for 5 or fewer categories), trend lines with automatic day/week/month resampling, correlation heatmap, scatter plots with trendlines for correlated pairs, segment comparisons, missing-value bars. Charts per section are capped so wide files stay readable.
- **One-line takeaway under every chart**, computed in code (for example, "revenue peaks in the month of 2024-11-01, 2.1x the average month").
- **AI summary (optional):** Claude turns the computed findings into an executive summary, recommendations and caveats. Without an API key, a rule-based summary is used.
- **Exports:** interactive HTML, Excel (summary, profile, findings, change log, cleaned data), and PDF.

## Design decisions

- **The LLM never does the math.** All statistics are computed in pandas. Claude only sees computed statistics and findings, never raw rows.
- **Every number in the AI summary is verified.** After generation, each number is matched against the computed statistics, and anything that does not match is flagged in the report.
- **Safe by default.** Uploaded formulas and macros are never executed (values are read, not evaluated). Text that starts with `=`, `+`, `-` or `@` is neutralised on Excel export to prevent formula injection. User-derived text in the HTML export is escaped. Uploads live in memory only, and cached results expire after one hour.
- **Scales.** Charts use a sample for large files while statistics stay exact. A 1M-row file runs through the full pipeline in a few seconds in the test suite.

## Architecture

```
flowchart LR
  A["Upload"] --> B["loader - encoding, delimiter, sheets, headers"]
  B --> C["profiler - types, quality flags"]
  C --> D["clean - opt-in fixes + change log"]
  D --> E["analyzers - numeric, categorical, temporal, relationships"]
  E --> F["charts - rules by column type"]
  E --> G["narrative - Claude or rule-based"]
  F --> H["exporters - HTML, Excel, PDF"]
  G --> H
  F --> I["Streamlit UI"]
  G --> I
```

```
auto-report/
├── app/streamlit_app.py
├── engine/
│   ├── loader.py        # parsing
│   ├── profiler.py      # type detection and quality flags
│   ├── clean.py         # opt-in fixes
│   ├── analyzers/       # numeric, categorical, temporal, relationships
│   ├── charts.py        # chart rules
│   ├── analysis.py      # builds report sections
│   ├── narrative.py     # AI / rule-based summary + number verification
│   └── exporters.py     # HTML, Excel, PDF
├── templates/report.html.j2
├── sample_data/retail_sales.csv
├── tests/               # unit tests, ugly-file corpus, UI smoke test
└── .github/workflows/ci.yml
```

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use: source .venv/bin/activate on Mac/Linux
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

For the AI summary, paste an Anthropic API key into the sidebar. For PDF export:

```bash
pip install playwright
playwright install chromium
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The suite includes a corpus of ugly files (empty, one column, all nulls, mixed encodings, 500 columns, merged Excel cells, formula injection, 1M rows) that must pass through the whole pipeline without crashing, plus a headless UI test. CI runs it on every push.

## Limitations and roadmap

- Not implemented yet: clustering, feature importance against a chosen target, forecasting, Cramér's V for categorical pairs.
- Trend charts sum additive measures and average rates, prices and durations, chosen by a simple name and range heuristic.
- Planned: connect the uploaded file to DuckDB so a text-to-SQL copilot can answer plain-English questions on it.

## License

MIT
