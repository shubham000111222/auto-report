"""LLM narrative. Claude only sees computed statistics (never raw rows) and must not invent numbers;
every number it writes is checked against the payload afterwards."""
import json
import re

MODEL = "claude-sonnet-5-5"

SYSTEM = (
    "You are a careful data analyst. You receive JSON with computed statistics and findings about a dataset. "
    "Write for a non-technical reader. Use ONLY numbers that appear in the JSON; never calculate new numbers. "
    "Return ONLY a JSON object with keys: "
    '"summary" (5-8 short bullet strings, most important first), '
    '"recommendations" (3-5 concrete next steps), "caveats" (2-4 limitations). No markdown, no extra text.'
)


def build_payload(prof: dict, report: dict, filename: str) -> dict:
    cols = []
    for c in prof["columns"]:
        d = {k: c[k] for k in ("name", "kind", "pct_missing", "n_unique", "flags")}
        stats = {k: v for k, v in c["stats"].items() if k != "top_values"}
        if stats:
            d["stats"] = stats
        cols.append(d)
    findings = [{"section": k, "title": it["title"], "takeaway": it["takeaway"]}
                for k, items in report.items() for it in items]
    return {"file": filename, "rows": prof["n_rows"], "n_columns": prof["n_cols"],
            "duplicate_rows": prof["n_duplicate_rows"], "columns": cols, "findings": findings}


def rule_based(payload: dict) -> dict:
    """Deterministic fallback: no API key needed, every sentence comes straight from computed findings."""
    f = payload["findings"]
    by = lambda s: [x["takeaway"] for x in f if x["section"] == s]
    summary = [f"The dataset has {payload['rows']:,} rows and {payload['n_columns']} columns."]
    summary += by("quality")[:3] + by("trends")[:1] + by("relationships")[:2] + by("segments")[:1] + by("numeric")[:1]
    recs = []
    for c in payload["columns"]:
        for fl in c["flags"]:
            if fl.startswith("inconsistent"):
                recs.append(f"Merge inconsistent spellings in '{c['name']}' before analysing it by group.")
            elif fl == "mostly missing":
                recs.append(f"Check whether '{c['name']}' is worth keeping: it is mostly empty.")
            elif fl == "looks like an identifier":
                recs.append(f"Treat '{c['name']}' as a key, not as a metric.")
    if payload["duplicate_rows"]:
        recs.append("Review and remove duplicate rows.")
    recs = recs[:5] or ["No data quality fixes are needed; explore the strongest relationships next."]
    caveats = ["Correlation does not imply causation.",
               "Outliers are flagged by a statistical rule and may be legitimate values.",
               "Findings describe this file only and may not generalise."]
    return {"summary": summary[:8], "recommendations": recs, "caveats": caveats, "source": "rule-based"}


def ask_claude(payload: dict, api_key: str | None = None, client=None) -> dict:
    if client is None:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                 messages=[{"role": "user", "content": json.dumps(payload)}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    out = {k: [str(x) for x in data.get(k, [])] for k in ("summary", "recommendations", "caveats")}
    if not out["summary"]:
        raise ValueError("Model returned no summary")
    out["source"] = "claude"
    return out


_NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s?([kKmMbB])?(?![\w])")
_SCALE = {"k": 1e3, "m": 1e6, "b": 1e9}


def verify_numbers(narr: dict, payload: dict) -> list[str]:
    """Return numbers in the narrative that do not appear in the computed payload."""
    pool = {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", json.dumps(payload))}
    bad = []
    text = " ".join(narr["summary"] + narr["recommendations"] + narr["caveats"])
    for m in _NUM.finditer(text):
        raw, suf = m.group(1), m.group(2)
        n = float(raw.replace(",", ""))
        if not suf and n == int(n) and n <= 12:
            continue  # small counts ("3 steps") are not statistics
        if suf:
            n *= _SCALE[suf.lower()]
            ok = any(abs(n - p) <= 0.01 * max(abs(p), 1) for p in pool)
        else:
            d = len(raw.split(".")[1]) if "." in raw else 0
            ok = any(round(p, d) == round(n, d) for p in pool)
        if not ok:
            bad.append(m.group(0).strip())
    return bad
