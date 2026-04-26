"""
Fix existing Buttondown archive entries that were imported with broken HTML.

The back-catalog entries (Apr 18-22) were imported using raw GitHub Pages HTML,
which Buttondown rendered as Markdown code blocks. This script:
  1. Fetches all emails from Buttondown
  2. Matches them to local newsletter HTML files by subject
  3. Re-generates each one with proper inline-styled email HTML
  4. PATCHes the Buttondown entry with the corrected body

Usage (from repo root, with BUTTONDOWN_API_KEY in env):
    python fix_buttondown_archives.py
    python fix_buttondown_archives.py --dry-run   # preview without patching
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"
DOCS_DIR = Path(__file__).parent / "docs" / "newsletters"


def github_pages_to_email_html(html: str) -> str:
    """Convert GitHub Pages newsletter HTML to inline-styled email-safe HTML."""
    from bs4 import BeautifulSoup

    C_NAVY   = "#1a2744"
    C_GOLD   = "#c9a84c"
    C_TEXT   = "#2d3748"
    C_MUTED  = "#718096"
    C_LIGHT  = "#f7f8fa"
    C_BORDER = "#e2e8f0"
    C_LINK   = "#2c5282"
    C_WHITE  = "#ffffff"

    soup = BeautifulSoup(html, "lxml")
    article = soup.find("article", class_="newsletter")
    if not article:
        return "<!-- buttondown-editor-mode: fancy -->\n" + html

    # --- Header ---
    nh = article.find("header", class_="newsletter-header")
    title_text = nh.find("h1").get_text(strip=True) if nh and nh.find("h1") else "Geopolitical Daily"
    time_el = nh.find("time") if nh else None
    date_text = time_el.get_text(strip=True) if time_el else ""
    intro_el = nh.find("p", class_="newsletter-intro") if nh else None
    intro_text = intro_el.get_text(strip=True) if intro_el else ""

    header_html = (
        f'<div style="background-color:{C_NAVY};padding:36px 28px;text-align:center;">'
        f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:10px;letter-spacing:3px;'
        f'text-transform:uppercase;color:{C_GOLD};margin-bottom:12px;">Intelligence Briefing</div>'
        f'<h1 style="font-family:Georgia,\'Times New Roman\',serif;font-size:30px;font-weight:bold;'
        f'color:{C_WHITE};margin:0 0 8px 0;line-height:1.2;">{title_text}</h1>'
        f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:13px;color:#94a3b8;'
        f'margin-bottom:10px;font-style:italic;">Strategic Intelligence Beyond the Headlines</div>'
        f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:13px;color:#64748b;">{date_text}</div>'
        f'</div>'
        f'<div style="background-color:{C_GOLD};height:3px;"></div>'
    )

    intro_html = ""
    if intro_text:
        intro_html = (
            f'<div style="background-color:{C_LIGHT};border-left:4px solid {C_GOLD};padding:20px 24px;'
            f'margin:28px 0;font-family:Georgia,\'Times New Roman\',serif;font-size:16px;line-height:1.75;'
            f'color:{C_TEXT};">{intro_text}</div>'
        )

    # --- Stories ---
    stories_div = article.find("div", class_="stories")
    stories_html = ""
    if stories_div:
        sections = stories_div.find_all("section", class_="story")
        for i, section in enumerate(sections):
            is_last = (i == len(sections) - 1)

            sh = section.find("header", class_="story-header")
            story_title_text = sh.find("h2").get_text(strip=True) if sh and sh.find("h2") else ""

            meta = sh.find("div", class_="story-meta") if sh else None
            impact_el = meta.find("span", class_="impact-score") if meta else None
            impact_text = impact_el.get_text(strip=True) if impact_el else ""
            region_el = meta.find("span", class_="region-tag") if meta else None
            region_text = region_el.get_text(strip=True) if region_el else ""

            impact_color = "#27ae60"
            if impact_el:
                cls = impact_el.get("class", [])
                if "impact-high" in cls:
                    impact_color = "#e74c3c"
                elif "impact-medium" in cls:
                    impact_color = "#f39c12"

            content_parts = []
            story_content = section.find("div", class_="story-content")
            if story_content:
                for asc in story_content.find_all("div", class_="analysis-section"):
                    h3 = asc.find("h3")
                    p = asc.find("p")
                    if h3 and p:
                        sec_title = h3.get_text(strip=True)
                        sec_text = p.get_text(strip=True)
                        if "What Others Are Missing" in sec_title:
                            content_parts.append(
                                f'<div style="margin-bottom:20px;background-color:{C_LIGHT};'
                                f'padding:16px 18px;border-left:3px solid {C_GOLD};">'
                                f'<div style="font-size:10px;font-weight:bold;text-transform:uppercase;'
                                f'letter-spacing:1px;color:{C_MUTED};margin-bottom:8px;">{sec_title}</div>'
                                f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:16px;'
                                f'line-height:1.75;color:{C_TEXT};">{sec_text}</div></div>'
                            )
                        else:
                            content_parts.append(
                                f'<div style="margin-bottom:20px;">'
                                f'<div style="font-size:10px;font-weight:bold;text-transform:uppercase;'
                                f'letter-spacing:1px;color:{C_MUTED};margin-bottom:8px;">{sec_title}</div>'
                                f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:16px;'
                                f'line-height:1.75;color:{C_TEXT};">{sec_text}</div></div>'
                            )

            sources_el = section.find("div", class_="sources")
            src_html = ""
            if sources_el:
                links = sources_el.find_all("a")
                if links:
                    lhtml = "".join(
                        f'<a href="{a.get("href","#")}" style="color:{C_LINK};text-decoration:none;'
                        f'font-size:13px;display:inline-block;margin-right:12px;margin-bottom:4px;">'
                        f'{a.get_text(strip=True)}</a>'
                        for a in links
                    )
                    src_html = (
                        f'<div style="border-top:1px solid {C_BORDER};margin-top:20px;padding-top:14px;">'
                        f'<div style="font-size:10px;font-weight:bold;text-transform:uppercase;'
                        f'letter-spacing:1px;color:{C_MUTED};margin-bottom:8px;">Sources</div>'
                        f'<div>{lhtml}</div></div>'
                    )

            border_bottom = "" if is_last else f"border-bottom:1px solid {C_BORDER};"
            badges = ""
            if impact_text:
                badges += (
                    f'<span style="display:inline-block;background-color:{impact_color};color:#ffffff;'
                    f'font-size:10px;font-weight:bold;padding:4px 8px;border-radius:10px;'
                    f'margin-right:6px;margin-bottom:4px;">Impact {impact_text}</span>'
                )
            if region_text:
                badges += (
                    f'<span style="display:inline-block;background-color:{C_LIGHT};color:#4a5568;'
                    f'font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;'
                    f'padding:4px 8px;border-radius:10px;border:1px solid {C_BORDER};margin-bottom:4px;">'
                    f'{region_text}</span>'
                )

            stories_html += (
                f'<div style="{border_bottom}margin-bottom:36px;padding-bottom:36px;padding-top:28px;">'
                f'<div style="margin-bottom:14px;">{badges}</div>'
                f'<h2 style="font-family:Georgia,\'Times New Roman\',serif;font-size:22px;font-weight:bold;'
                f'color:{C_NAVY};margin:0 0 22px 0;line-height:1.35;">{story_title_text}</h2>'
                f'{"".join(content_parts)}'
                f'{src_html}'
                f'</div>'
            )

    # --- Footer ---
    footer_el = article.find("footer", class_="newsletter-footer")
    footer_note = ""
    if footer_el:
        fp = footer_el.find("p")
        if fp:
            footer_note = fp.get_text(strip=True)

    _footer_note_html = f'<p style="margin:0 0 12px 0;">{footer_note}</p>' if footer_note else ""
    footer_html = (
        f'<div style="border-top:2px solid {C_BORDER};margin-top:32px;padding-top:24px;text-align:center;'
        f'font-family:Georgia,\'Times New Roman\',serif;font-size:12px;color:{C_MUTED};line-height:1.8;">'
        f'<p style="margin:0 0 6px 0;font-weight:bold;color:{C_TEXT};">Geopolitical Daily</p>'
        f'<p style="margin:0 0 12px 0;">Geopolitical Intelligence for Decision Makers</p>'
        f'{_footer_note_html}'
        f'<p style="margin:0;font-size:11px;color:{C_MUTED};">You are receiving this because you subscribed to Geopolitical Daily.</p>'
        f'</div>'
    )

    return (
        f'<!-- buttondown-editor-mode: fancy -->\n'
        f'<div style="max-width:600px;margin:0 auto;background-color:{C_WHITE};">'
        f'{header_html}'
        f'<div style="padding:0 32px 32px 32px;">'
        f'{intro_html}{stories_html}{footer_html}'
        f'</div></div>'
    )


def _date_from_subject(subject: str) -> str | None:
    """Extract YYYY-MM-DD from subject like 'Geopolitical Daily — April 22, 2026'."""
    import calendar
    m = re.search(r"(\w+ \d+, \d{4})$", subject)
    if not m:
        return None
    try:
        from datetime import datetime
        d = datetime.strptime(m.group(1), "%B %d, %Y")
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_all_emails(api_key: str) -> list:
    headers = {
        "Authorization": f"Token {api_key}",
        "Buttondown-Version": "2026-04-01",
    }
    emails = []
    url = f"{BUTTONDOWN_API_BASE}/emails"
    while url:
        try:
            resp = requests.get(url, params={"page_size": 50}, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            emails.extend(data.get("results", []))
            url = data.get("next")
        except Exception as exc:
            print(f"ERROR fetching emails: {exc}")
            break
    return emails


def patch_email(api_key: str, email_id: str, body: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"    [DRY RUN] would PATCH email {email_id}")
        return True
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Buttondown-Version": "2026-04-01",
    }
    try:
        resp = requests.patch(
            f"{BUTTONDOWN_API_BASE}/emails/{email_id}",
            json={"body": body},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except requests.HTTPError as exc:
        print(f"    FAIL PATCH: HTTP {exc.response.status_code} — {exc.response.text[:300]}")
        return False
    except Exception as exc:
        print(f"    FAIL PATCH: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix Buttondown archive email formatting")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without patching")
    args = parser.parse_args()

    api_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if not api_key:
        print("ERROR: BUTTONDOWN_API_KEY not set")
        return 1

    print("Fetching all emails from Buttondown...")
    emails = fetch_all_emails(api_key)
    print(f"Found {len(emails)} email(s).\n")

    fixed = 0
    skipped = 0

    for email in emails:
        subject = email.get("subject", "")
        email_id = email.get("id", "")
        status = email.get("status", "")

        if "Geopolitical Daily" not in subject:
            continue

        date_str = _date_from_subject(subject)
        if not date_str:
            print(f"  SKIP (no date): {subject}")
            skipped += 1
            continue

        html_path = DOCS_DIR / f"newsletter-{date_str}.html"
        if not html_path.exists():
            print(f"  SKIP (no local file): {subject}")
            skipped += 1
            continue

        print(f"  Processing: {subject} (id={email_id[:8]}… status={status})")
        html = html_path.read_text(encoding="utf-8")
        body = github_pages_to_email_html(html)

        ok = patch_email(api_key, email_id, body, args.dry_run)
        if ok:
            print(f"    {'[DRY RUN] ' if args.dry_run else ''}✓ Fixed")
            fixed += 1
        time.sleep(0.5)

    print(f"\nDone. Fixed: {fixed}, Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
