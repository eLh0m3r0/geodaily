#!/usr/bin/env python3
"""
Sunday weekly digest for subscribers who chose "weekly" at signup.

Compiled from the week's already-published issue JSONs — zero AI cost.
Content: the week's big stories (linked), the blindspots of the week, and
the numbers of the week. Sent via Buttondown to the weekly tag only.

Run: python -m src.weekly_digest        (DRY_RUN=true writes HTML, sends nothing)
"""

import sys
from datetime import datetime
from pathlib import Path

from .config import Config
from .logger import get_logger
from .newsletter.issue_store import load_recent_issues
from .publishers.buttondown_publisher import ButtondownPublisher

logger = get_logger(__name__)

C_NAVY, C_GOLD, C_TEXT, C_MUTED = "#1a2744", "#c9a84c", "#2d3748", "#718096"
C_LIGHT, C_BORDER, C_LINK, C_WHITE = "#f7f8fa", "#e2e8f0", "#2c5282", "#ffffff"
BODY_FONT = "font-family:Georgia,'Times New Roman',serif;"


def build_digest_html(issues) -> str:
    """One email: 5-7 big stories + blindspots + numbers of the week."""
    base = Config.SITE_BASE_URL.rstrip("/")
    heading = (f"font-size:10px;font-weight:bold;text-transform:uppercase;"
               f"letter-spacing:2px;color:{C_MUTED};margin-bottom:12px;")

    story_items = ""
    for issue in issues:
        stories = issue.get("stories") or []
        if not stories:
            continue
        story = stories[0]
        date_str = issue.get("date", "")
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
        except ValueError:
            day = date_str
        url = f'{base}/newsletters/newsletter-{date_str}.html'
        why = (story.get("why_important") or "").split(". ")[0].rstrip(".") + "."
        story_items += (
            f'<div style="margin-bottom:18px;">'
            f'<div style="font-size:10px;font-weight:bold;text-transform:uppercase;'
            f'letter-spacing:1px;color:{C_MUTED};">{day}</div>'
            f'<div style="{BODY_FONT}font-size:17px;font-weight:bold;line-height:1.4;">'
            f'<a href="{url}" style="color:{C_NAVY};text-decoration:none;">{story.get("story_title", "")}</a></div>'
            f'<div style="{BODY_FONT}font-size:14px;line-height:1.6;color:{C_TEXT};">{why}</div>'
            f'</div>'
        )

    blindspots = ""
    for issue in issues:
        grid = issue.get("perspective_grid") or {}
        text = (grid.get("blindspot") or "").strip()
        if not text:
            continue
        arrow = ""
        if grid.get("blindspot_url"):
            arrow = (f' <a href="{grid["blindspot_url"]}" '
                     f'style="color:{C_LINK};text-decoration:none;">&rarr;</a>')
        blindspots += (f'<div style="margin-bottom:10px;{BODY_FONT}font-size:14px;'
                       f'line-height:1.6;color:{C_TEXT};">&#9888; {text}{arrow}</div>')
    blindspot_block = ""
    if blindspots:
        blindspot_block = (
            f'<div style="margin:26px 0;background-color:#fdf3e3;padding:16px 18px;'
            f'border-left:3px solid {C_GOLD};">'
            f'<div style="{heading}">Blindspots of the Week</div>'
            f'<div style="font-size:12px;color:{C_MUTED};margin-bottom:10px;">'
            f'Stories one part of the world covered heavily while the rest looked away.</div>'
            f'{blindspots}</div>'
        )

    numbers = ""
    for issue in issues:
        bn = issue.get("big_number") or {}
        if not bn.get("value"):
            continue
        numbers += (f'<div style="margin-bottom:10px;{BODY_FONT}font-size:14px;'
                    f'line-height:1.6;color:{C_TEXT};"><strong style="color:{C_NAVY};">'
                    f'{bn["value"]}</strong> &mdash; {bn.get("context", "")}</div>')
    numbers_block = ""
    if numbers:
        numbers_block = (
            f'<div style="margin:26px 0;background-color:{C_LIGHT};padding:16px 18px;'
            f'border-left:3px solid {C_NAVY};">'
            f'<div style="{heading}">Numbers of the Week</div>{numbers}</div>'
        )

    today = datetime.now().strftime("%B %-d, %Y")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{Config.NEWSLETTER_TITLE} — Weekly Digest</title></head>
<body style="margin:0;padding:12px;background-color:#f0f2f5;{BODY_FONT}">
<div style="max-width:600px;margin:0 auto;background-color:{C_WHITE};border-radius:6px;overflow:hidden;">
<div style="background-color:{C_NAVY};padding:28px 24px;text-align:center;">
  <div style="{BODY_FONT}font-size:10px;letter-spacing:3px;text-transform:uppercase;color:{C_GOLD};margin-bottom:10px;">Weekly Digest</div>
  <h1 style="{BODY_FONT}font-size:24px;font-weight:bold;color:{C_WHITE};margin:0 0 8px 0;">{Config.NEWSLETTER_TITLE}</h1>
  <div style="{BODY_FONT}font-size:13px;color:#94a3b8;font-style:italic;">{Config.NEWSLETTER_TAGLINE}</div>
  <div style="{BODY_FONT}font-size:13px;color:#64748b;margin-top:6px;">Week ending {today}</div>
</div>
<div style="background-color:{C_GOLD};height:3px;"></div>
<div style="padding:8px 24px 28px 24px;">
  <p style="{BODY_FONT}font-size:15px;line-height:1.7;color:{C_TEXT};">Your week in world news &mdash; the {sum(1 for i in issues if i.get("stories"))} stories that mattered, in five minutes.</p>
  <div style="margin:22px 0;">
    <div style="{heading}">The Week's Big Stories</div>
    {story_items}
  </div>
  {blindspot_block}
  {numbers_block}
  <div style="border-top:2px solid {C_BORDER};margin-top:28px;padding-top:20px;text-align:center;{BODY_FONT}font-size:12px;color:{C_MUTED};line-height:1.8;">
    <p style="margin:0 0 6px 0;">Want this daily instead? Reply with the word "daily".</p>
    <p style="margin:0;">Every story above links to its full edition with all sources.</p>
  </div>
</div>
</div>
</body>
</html>"""


def main() -> int:
    newsletters_dir = Config.PROJECT_ROOT / "docs" / "newsletters"
    issues = load_recent_issues(newsletters_dir, days=7)
    issues = [i for i in issues if i.get("stories")]
    if len(issues) < 3:
        logger.warning(f"Only {len(issues)} issues with stories this week — skipping digest")
        print(f"⏭️  Weekly digest skipped ({len(issues)} issues available, need 3+)")
        return 0

    html = build_digest_html(issues)
    subject = f"🌍 Your week in world news — {datetime.now().strftime('%b %-d')}"

    out = Config.PROJECT_ROOT / "output"
    out.mkdir(exist_ok=True)
    preview = out / f"weekly_digest_{datetime.now().strftime('%Y%m%d')}.html"
    preview.write_text(html, encoding='utf-8')
    logger.info(f"Weekly digest preview written: {preview}")

    if Config.DRY_RUN:
        print(f"✅ DRY_RUN: weekly digest built from {len(issues)} issues -> {preview}")
        return 0

    publisher = ButtondownPublisher()
    if not publisher.enabled:
        print("⏭️  Buttondown not configured — digest built but not sent")
        return 0
    url = publisher.send_email(subject, html,
                               included_tags=[Config.BUTTONDOWN_WEEKLY_TAG])
    if url:
        print(f"✅ Weekly digest sent to '{Config.BUTTONDOWN_WEEKLY_TAG}' subscribers: {url}")
        return 0
    print("❌ Weekly digest send failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
