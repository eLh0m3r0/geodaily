#!/usr/bin/env python3
"""
Quality report for one published issue.

A run can succeed technically and still ship a degraded issue — 2026-10-03
went out with no perspective-grid rows and no blindspot, and nothing said
so. This script reads the issue JSON, prints a checklist (to the GitHub
step summary when available) and emits ::warning:: annotations for every
degraded section. It never fails the job: the email is already out.

Usage: python scripts/issue_quality_report.py [docs/newsletters/newsletter-YYYY-MM-DD.json]
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _sentence_stats(texts):
    try:
        from src.ai.editorial import sentence_stats
        return sentence_stats(texts)
    except Exception:
        return None, None


def check(issue: dict) -> list:
    """[(status, label, detail)] where status is 'ok' | 'warn' | 'info'."""
    rows = []

    def add(ok, label, detail, warn_if_false=True):
        rows.append(("ok" if ok else ("warn" if warn_if_false else "info"), label, detail))

    stories = issue.get("stories") or []
    add(len(stories) >= 2, "Stories", f"{len(stories)}")

    grid = issue.get("perspective_grid") or {}
    views = grid.get("views") or []
    framed = [v for v in views if (v.get("framing") or "").strip() and not v.get("wire_copy")]
    add(len(framed) >= 2, "Grid rows with an angle", f"{len(framed)} of {len(views)} groups")
    add(bool(grid.get("blindspot")), "Blindspot", "present" if grid.get("blindspot") else "missing")

    hits = issue.get("quick_hits") or []
    add(len(hits) >= 5, "Also today", f"{len(hits)} items")
    regions = {h.get("region") for h in hits}
    add(len(regions) >= 4, "Also today regions", f"{len(regions)} regions", warn_if_false=False)

    developing = issue.get("developing") or []
    rows.append(("info", "Developing", f"{len(developing)} running-story updates"))

    add(bool(issue.get("big_number")), "Big number",
        (issue.get("big_number") or {}).get("value", "missing") if issue.get("big_number") else "missing",
        warn_if_false=False)

    texts = [t for s in stories for t in (s.get("why_important", ""), s.get("what_overlooked", ""),
                                           s.get("prediction", ""))]
    avg, frag = _sentence_stats(texts)
    if avg is not None:
        add(avg >= 10.5 and frag <= 0.25, "Sentence shape", f"{avg} words/sentence, {frag:.0%} fragments")

    meta = issue.get("meta") or {}
    for flag in meta.get("quality_flags") or []:
        rows.append(("warn", "Editorial flag", flag))
    readability = meta.get("readability") or {}
    if readability:
        rows.append(("info", "Readability",
                     f"grade {readability.get('grade')} → {readability.get('rewrite_grade', '—')} "
                     f"({readability.get('rewrite')})"))
    model, served = meta.get("model"), meta.get("served_model")
    if model and served:
        add(served.split(":")[0] == model.split(":")[0], "Model", f"{served} (requested {model})")
    cost = (meta.get("analysis_cost_usd") or 0) + (meta.get("grid_cost_usd") or 0)
    if cost:
        rows.append(("info", "AI cost", f"${cost:.3f}"))
    return rows


def main(argv):
    if len(argv) > 1:
        path = Path(argv[1])
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = ROOT / "docs" / "newsletters" / f"newsletter-{today}.json"
    if not path.exists():
        print(f"ℹ️ No issue JSON at {path} — nothing to report.")
        return 0
    issue = json.loads(path.read_text(encoding="utf-8"))
    rows = check(issue)

    icon = {"ok": "✅", "warn": "⚠️", "info": "ℹ️"}
    lines = [f"## Issue quality — {issue.get('date', path.stem)}", "",
             "| | Check | Result |", "|---|---|---|"]
    for status, label, detail in rows:
        lines.append(f"| {icon[status]} | {label} | {re.sub(r'[|]', '/', str(detail))} |")
        if status == "warn":
            print(f"::warning title=Issue quality: {label}::{detail}")
    report = "\n".join(lines) + "\n"
    print(report)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
