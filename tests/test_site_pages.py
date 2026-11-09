"""Site shell, how-it-works page and dashboard (src/publishers/site_pages.py)."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.publishers import site_pages
from src.models import AIAnalysis, Newsletter, PerspectiveGrid, QuickHit
from src.publishers.github_pages_publisher import GitHubPagesPublisher


def _issue(date, pipeline=None, **meta):
    meta = dict({"served_model": "vendor/model-x", "analysis_cost_usd": 0.02,
                 "grid_cost_usd": 0.005, "analysis_seconds": 120.0,
                 "readability": {"grade": 11.0, "rewrite": "applied", "rewrite_grade": 9.0}}, **meta)
    if pipeline:
        meta["pipeline"] = pipeline
    return {"date": date, "stories": [{"story_title": "A"}, {"story_title": "B"}],
            "quick_hits": [{"text": "x"}], "developing": [],
            "perspective_grid": {"views": [{"framing": "f"}], "blindspot": "b"}, "meta": meta}


def _site(tmp_path, issues):
    (tmp_path / "newsletters").mkdir()
    for issue in issues:
        (tmp_path / "newsletters" / f"newsletter-{issue['date']}.json").write_text(json.dumps(issue))
    return tmp_path


def test_shell_marks_active_nav_and_keeps_links_relative():
    html = site_pages.page_shell(title="T", description='a "quoted" text', body="<p>x</p>",
                                 active="archive", depth=1)
    assert '<a href="../archive.html" aria-current="page">Archive</a>' in html
    assert 'href="../assets/style.css"' in html
    assert 'href="../how-it-works.html"' in html
    assert '&quot;quoted&quot;' in html


def test_pipeline_page_shows_recorded_counts_only(tmp_path):
    funnel = {"collected": 1311, "after_dedup": 1287, "events": 142,
              "prompt_articles": 60, "stories": 3, "quick_hits": 4, "seconds": 540}
    out = _site(tmp_path, [_issue("2026-11-08"), _issue("2026-11-09", pipeline=funnel)])
    html = site_pages.build_pipeline_page(out).read_text()
    assert "<b>1,311</b> articles" in html
    assert "<b>142</b> events" in html
    assert "November 9, 2026 run" in html
    assert "vendor/model-x" in html


def test_pipeline_page_without_counts_invents_none(tmp_path):
    out = _site(tmp_path, [_issue("2026-11-09")])
    html = site_pages.build_pipeline_page(out).read_text()
    assert "events found" not in html and "articles collected" not in html
    assert "Per-run counts appear" in html


def test_dashboard_uses_billed_cost_and_final_grade(tmp_path):
    out = _site(tmp_path, [_issue("2026-11-09"), _issue("2026-11-08", analysis_cost_usd=0.04)])
    html = site_pages.build_dashboard_page(out).read_text()
    assert "$0.0250" in html and "$0.0450" in html      # issue call + grid call
    assert "$0.035" in html                              # average of the two
    assert "9.0" in html and "2 / 2" in html             # final grade, blindspots
    assert 'aria-current="page">Dashboard' in html


def test_latest_funnel_takes_newest_issue_that_has_one():
    issues = [_issue("2026-11-09"), _issue("2026-11-08", pipeline={"collected": 5})]
    assert site_pages.latest_funnel(issues) == {"collected": 5, "date": "2026-11-08"}


def test_issue_page_has_toc_anchors_and_previous_link(tmp_path):
    publisher = GitHubPagesPublisher(output_dir=str(tmp_path))
    (tmp_path / "newsletters" / "newsletter-2026-11-08.html").write_text("<html></html>")
    stories = [AIAnalysis(story_title=f"Story {n}", why_important="w", what_overlooked="o",
                          prediction="p", impact_score=7, sources=[]) for n in (1, 2)]
    newsletter = Newsletter(date=datetime(2026, 11, 9), title="Geopolitical Daily", stories=stories,
                            quick_hits=[QuickHit(text="hit")],
                            perspective_grid=PerspectiveGrid(blindspot="spot"))
    html = publisher._generate_newsletter_html(newsletter, stories)
    assert '<a href="#story-2">Story 2</a>' in html and 'id="story-2"' in html
    assert 'href="#also-today"' in html and 'id="also-today"' in html
    assert 'href="#blindspot"' in html and 'id="blindspot"' in html
    assert 'href="newsletter-2026-11-08.html"' in html
    assert "Monday, November 9, 2026" in html
    # the RSS builder reads the lead story and intro back out of this markup
    assert '<section class="story" id="story-1">' in html
    assert '<p class="newsletter-intro">' in html
