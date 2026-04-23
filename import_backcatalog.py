"""
One-off Buttondown back-catalog import for geodaily.

Imports newsletter-2026-04-18 through newsletter-2026-04-21 as archived posts
(status=sent, no email sent to subscribers). April 22 was already published live.

Usage (from repo root, with BUTTONDOWN_API_KEY in env):
    python import_backcatalog.py
"""

import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"
DOCS_DIR = Path(__file__).parent / "docs" / "newsletters"

BACKCATALOG = [
    (date(2026, 4, 18), "April 18, 2026"),
    (date(2026, 4, 19), "April 19, 2026"),
    (date(2026, 4, 20), "April 20, 2026"),
    (date(2026, 4, 21), "April 21, 2026"),
]


def _prepare_body(html: str) -> str:
    inner = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    body = inner.group(1).strip() if inner else html
    body = re.sub(r'\s+on\w+="[^"]*"', "", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+on\w+='[^']*'", "", body, flags=re.IGNORECASE)
    return body


def already_exists(api_key: str, subject: str) -> bool:
    """Check if an email with this subject already exists in Buttondown."""
    headers = {
        "Authorization": f"Token {api_key}",
        "Buttondown-Version": "2026-04-01",
    }
    try:
        resp = requests.get(
            f"{BUTTONDOWN_API_BASE}/emails",
            params={"page_size": 50},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        emails = resp.json().get("results", [])
        return any(e.get("subject", "") == subject for e in emails)
    except Exception as exc:
        print(f"  Warning: could not check existing emails: {exc}")
        return False


def import_issue(api_key: str, issue_date: date, date_label: str) -> None:
    filename = f"newsletter-{issue_date.strftime('%Y-%m-%d')}.html"
    html_path = DOCS_DIR / filename
    if not html_path.exists():
        print(f"  SKIP {filename}: file not found")
        return

    subject = f"Geopolitical Daily — {date_label}"

    if already_exists(api_key, subject):
        print(f"  SKIP {filename}: already in Buttondown")
        return

    html = html_path.read_text(encoding="utf-8")
    body = _prepare_body(html)

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Buttondown-Version": "2026-04-01",
    }

    payload = {
        "subject": subject,
        "body": body,
        "status": "imported",
    }

    try:
        resp = requests.post(
            f"{BUTTONDOWN_API_BASE}/emails",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data.get("absolute_url", data.get("id", "?"))
        print(f"  OK  {filename}: {url}")
    except requests.HTTPError as exc:
        print(f"  FAIL {filename}: HTTP {exc.response.status_code} — {exc.response.text[:300]}")
    except Exception as exc:
        print(f"  FAIL {filename}: {exc}")


def main() -> int:
    api_key = os.environ.get("BUTTONDOWN_API_KEY", "")
    if not api_key:
        print("ERROR: BUTTONDOWN_API_KEY not set")
        return 1

    print("Importing back-catalog to Buttondown (status=sent, no emails to subscribers)...")
    for issue_date, label in BACKCATALOG:
        print(f"\nProcessing {label}...")
        import_issue(api_key, issue_date, label)
        time.sleep(1)  # be polite to the API

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
