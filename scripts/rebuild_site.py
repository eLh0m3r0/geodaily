#!/usr/bin/env python3
"""Re-render the site in docs/ from the issue JSONs — no pipeline run, no AI.

Use after changing the page templates or src/publishers/site.css:

    python scripts/rebuild_site.py            # rebuild docs/
    python scripts/rebuild_site.py --out /tmp/site-preview

Issue pages and their story pages are rebuilt from
docs/newsletters/newsletter-*.json; index, archive, about, how-it-works,
dashboard and the stylesheet are regenerated. The RSS feed and sitemap are
left to the daily run.

The subscribe form needs BUTTONDOWN_USERNAME (or BUTTONDOWN_API_KEY) in the
environment, exactly as in the daily run; without it the pages are written
with no form.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models import (AIAnalysis, BigNumber, DevelopingItem, Newsletter,  # noqa: E402
                        PerspectiveGrid, PerspectiveView, QuickHit, Signal)
from src.publishers.github_pages_publisher import GitHubPagesPublisher  # noqa: E402


def _only(cls, data: dict) -> dict:
    """Drop keys a dataclass does not know (older or newer issue JSON)."""
    known = cls.__dataclass_fields__.keys()
    return {k: v for k, v in data.items() if k in known}


def newsletter_from_json(data: dict) -> Newsletter:
    grid = None
    if data.get("perspective_grid"):
        g = dict(data["perspective_grid"])
        views = [PerspectiveView(**_only(PerspectiveView, v)) for v in g.pop("views", [])]
        grid = PerspectiveGrid(views=views, **_only(PerspectiveGrid, g))
    return Newsletter(
        date=datetime.strptime(data["date"], "%Y-%m-%d"),
        title=data.get("title") or "Geopolitical Daily",
        stories=[AIAnalysis(**_only(AIAnalysis, s)) for s in data.get("stories") or []],
        intro_text=data.get("intro_text") or "",
        quick_hits=[QuickHit(**_only(QuickHit, h)) for h in data.get("quick_hits") or []],
        big_number=BigNumber(**_only(BigNumber, data["big_number"])) if data.get("big_number") else None,
        perspective_grid=grid,
        signals=[Signal(**_only(Signal, s)) for s in data.get("signals") or []],
        email_subject=data.get("email_subject") or "",
        preheader=data.get("preheader") or "",
        meta=data.get("meta") or {},
        developing=[DevelopingItem(**_only(DevelopingItem, d)) for d in data.get("developing") or []],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(ROOT / "docs"), help="site directory (default: docs/)")
    args = parser.parse_args()

    out = Path(args.out)
    publisher = GitHubPagesPublisher(output_dir=str(out))
    rebuilt = 0
    for path in sorted((out / "newsletters").glob("newsletter-*.json")):
        newsletter = newsletter_from_json(json.loads(path.read_text(encoding="utf-8")))
        # keep the issue's original "Generated on" stamp: a re-render is not a new issue
        html_path = path.with_suffix(".html")
        stamp = None
        if html_path.exists():
            found = re.search(r'Generated on (\d{4}-\d{2}-\d{2} at \d{2}:\d{2} UTC)',
                              html_path.read_text(encoding="utf-8"))
            stamp = found.group(1) if found else None
        publisher.generated_at_override = stamp
        html = publisher._generate_newsletter_html(newsletter, newsletter.stories)
        publisher.generated_at_override = None
        html_path.write_text(html, encoding="utf-8")
        publisher._publish_story_page(newsletter, newsletter.stories)
        rebuilt += 1
    publisher._update_index_page()
    publisher._update_archive_page()
    publisher._update_about_page()
    publisher._update_pipeline_page()
    publisher._update_dashboard()
    publisher._copy_assets()
    print(f"Rebuilt {rebuilt} issue pages and the site pages in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
