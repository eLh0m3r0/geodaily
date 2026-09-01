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

INK, SUB, FAINT = "#14181D", "#57616B", "#9AA3AB"
LINE, WASH, ACCENT, AMBER = "#E6E9EC", "#F5F7F9", "#1F6FEB", "#B26B00"
BODY_FONT = ("font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
             "'Helvetica Neue',Arial,sans-serif;")


def build_digest_html(issues) -> str:
    """One email: 5-7 big stories + blindspots + numbers of the week."""
    from .perspectives import spectrum_bar_html
    base = Config.SITE_BASE_URL.rstrip("/")

    def kicker(text):
        return (f'<div style="margin-top:26px;">'
                f'<div style="width:28px;height:3px;background-color:{INK};margin-bottom:7px;font-size:0;line-height:0;">&nbsp;</div>'
                f'<div style="{BODY_FONT}font-size:11px;font-weight:800;letter-spacing:2px;'
                f'text-transform:uppercase;color:{INK};margin-bottom:12px;">{text}</div></div>')

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
            f'<div style="margin-bottom:16px;">'
            f'<div style="{BODY_FONT}font-size:10px;font-weight:800;text-transform:uppercase;'
            f'letter-spacing:1px;color:{ACCENT};">{day}</div>'
            f'<div style="{BODY_FONT}font-size:16.5px;font-weight:800;letter-spacing:-0.2px;line-height:1.35;">'
            f'<a href="{url}" style="color:{INK};text-decoration:none;">{story.get("story_title", "")}</a></div>'
            f'<div style="{BODY_FONT}font-size:14px;line-height:1.6;color:{SUB};">{why}</div>'
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
                     f'style="color:{ACCENT};text-decoration:none;">&rarr;</a>')
        blindspots += (f'<div style="border-left:3px solid {AMBER};padding:2px 0 2px 12px;'
                       f'margin-bottom:10px;{BODY_FONT}font-size:14px;'
                       f'line-height:1.6;color:{INK};">{text}{arrow}</div>')
    blindspot_block = ""
    if blindspots:
        blindspot_block = (
            f'{kicker("Blindspots of the Week")}'
            f'<div style="{BODY_FONT}font-size:12px;color:{FAINT};margin:-6px 0 12px 0;">'
            f'Stories one part of the world covered heavily while the rest looked away.</div>'
            f'{blindspots}'
        )

    numbers = ""
    for issue in issues:
        bn = issue.get("big_number") or {}
        if not bn.get("value"):
            continue
        numbers += (f'<div style="margin-bottom:8px;{BODY_FONT}font-size:14px;'
                    f'line-height:1.6;color:{SUB};"><strong style="color:{INK};font-size:16px;">'
                    f'{bn["value"]}</strong> &mdash; {bn.get("context", "")}</div>')
    numbers_block = f'{kicker("Numbers of the Week")}{numbers}' if numbers else ""

    today = datetime.now().strftime("%B %-d, %Y")
    story_count = sum(1 for i in issues if i.get("stories"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{Config.NEWSLETTER_TITLE} — Weekly Digest</title></head>
<body style="margin:0;padding:0;background-color:#EEF1F4;{BODY_FONT}">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">The week's big stories, the blindspots the world missed, and the numbers that mattered.{"&nbsp;&zwnj;" * 96}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#EEF1F4" style="background-color:#EEF1F4;">
<tr><td align="center" style="padding:14px 10px;">
<table role="presentation" width="600" align="center" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
<tr><td style="background-color:#ffffff;border:1px solid {LINE};border-radius:8px;overflow:hidden;">
{spectrum_bar_html(5)}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:22px 24px 0 24px;">
  <tr>
    <td style="{BODY_FONT}font-size:14px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:{INK};">{Config.NEWSLETTER_TITLE}</td>
    <td align="right" style="{BODY_FONT}font-size:12px;color:{FAINT};">Weekly Digest</td>
  </tr>
  <tr>
    <td colspan="2" style="{BODY_FONT}font-size:12px;color:{FAINT};padding-top:3px;">{Config.NEWSLETTER_TAGLINE} &middot; Week ending {today}</td>
  </tr>
</table>
<div style="padding:4px 24px 26px 24px;">
  <p style="{BODY_FONT}font-size:15px;line-height:1.65;color:{SUB};margin:16px 0 0 0;">Your week in world news &mdash; the {story_count} stories that mattered, in five minutes.</p>
  {kicker("The Week's Big Stories")}
  {story_items}
  {blindspot_block}
  {numbers_block}
  <div style="border-top:1px solid {LINE};margin-top:26px;padding-top:16px;text-align:center;{BODY_FONT}font-size:12px;color:{FAINT};line-height:1.8;">
    <p style="margin:0 0 4px 0;">Want this daily instead? Reply with the word "daily".</p>
    <p style="margin:0;">Every story above links to its full edition with all sources.</p>
  </div>
</div>
</td></tr>
</table>
</td></tr>
</table>
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
    subject = f"🌍 Your week in world news — {Config.NEWSLETTER_TITLE}"

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
    if not publisher.has_tag(Config.BUTTONDOWN_WEEKLY_TAG):
        # Nobody has opted into weekly yet (or the Buttondown plan doesn't
        # include tags) — nothing to send to, and that's not a failure.
        print(f"⏭️  No '{Config.BUTTONDOWN_WEEKLY_TAG}' subscribers yet — digest built, not sent")
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
