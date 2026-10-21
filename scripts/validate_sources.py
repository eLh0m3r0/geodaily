#!/usr/bin/env python3
"""
Validate all RSS sources in sources.json.

Checks every tier1 feed for reachability, valid RSS/Atom structure, entry
count and freshness of the newest entry. Use it to catch dead or stale feeds
before they silently degrade the newsletter's article pool.

Usage:
    python scripts/validate_sources.py            # human-readable report
    python scripts/validate_sources.py --strict   # exit 1 if any feed is dead
    python scripts/validate_sources.py --max-age-days 14

Intended to run from CI (GitHub Actions has open egress) or a dev machine;
sandboxed environments with restricted networking will report false failures.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import re
import socket
import urllib.parse
import urllib.request

try:
    import feedparser
except ImportError:
    print("feedparser is required: pip install feedparser")
    sys.exit(2)

# One stuck feed must not hang the run: feedparser has no timeout of its own
# and the results are printed only once every feed has answered
socket.setdefaulttimeout(20)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = PROJECT_ROOT / "sources.json"
# Match the collector's browser UA so validation reflects production behavior
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


_FEED_LINK = re.compile(
    r"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*>""", re.I)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)


def discover_feeds(url: str) -> str:
    """When a candidate URL is a web page rather than a feed, list the feeds
    the page advertises (<link rel="alternate" type="application/rss+xml">),
    so vetting can start from an outlet's homepage or language edition."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            head = resp.read(400_000).decode("utf-8", "replace")
    except Exception:
        return ""
    found = []
    for tag in _FEED_LINK.findall(head):
        m = _HREF.search(tag)
        if m:
            href = m.group(1)
            if href.startswith("/"):
                href = urllib.parse.urljoin(url, href)
            if href not in found:
                found.append(href)
    return f"; page advertises feeds: {', '.join(found[:6])}" if found else ""


def check_feed(source: dict, max_age_days: int) -> dict:
    name, url = source["name"], source["url"]
    result = {"name": name, "url": url, "status": "ok", "entries": 0, "newest": None, "detail": "",
              "sample": ""}
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
        status = getattr(feed, "status", None)
        if status and status >= 400:
            result.update(status="dead", detail=f"HTTP {status}")
            return result
        if feed.bozo and not feed.entries:
            result.update(status="dead", detail=f"parse error: {feed.bozo_exception}")
            result["detail"] += discover_feeds(url)
            return result
        result["entries"] = len(feed.entries)
        if not feed.entries:
            result.update(status="dead", detail="no entries" + discover_feeds(url))
            return result
        # The newest title shows what a feed really carries — language and
        # section — which the entry count alone hides (the Novaya Gazeta
        # Europe feed validated fine for six weeks while serving the
        # Russian-language edition to an English newsletter)
        result["sample"] = " ".join(str(feed.entries[0].get("title", "")).split())[:70]

        newest = None
        for entry in feed.entries:
            parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            if parsed:
                dt = datetime(*parsed[:6], tzinfo=timezone.utc)
                if newest is None or dt > newest:
                    newest = dt
        if newest:
            result["newest"] = newest.strftime("%Y-%m-%d")
            if datetime.now(timezone.utc) - newest > timedelta(days=max_age_days):
                result.update(status="stale", detail=f"newest entry older than {max_age_days}d")
    except Exception as e:
        result.update(status="dead", detail=str(e)[:120])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate RSS sources")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any feed is dead")
    parser.add_argument("--max-age-days", type=int, default=14,
                        help="mark feed stale if newest entry is older (default 14)")
    parser.add_argument("--file", default=str(SOURCES_FILE),
                        help="sources file to validate (default sources.json; use a "
                             "candidates file to vet feeds before adding them)")
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as f:
        sources = json.load(f)

    tier1 = sources.get("tier1_sources", [])
    print(f"Validating {len(tier1)} tier1 RSS sources...\n")

    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(check_feed, s, args.max_age_days) for s in tier1]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: (r["status"], r["name"]))
    icon = {"ok": "✅", "stale": "⚠️ ", "dead": "❌"}
    for r in results:
        extra = f" — {r['detail']}" if r["detail"] else ""
        newest = f", newest {r['newest']}" if r["newest"] else ""
        sample = f' — "{r["sample"]}"' if r["sample"] else ""
        print(f"{icon[r['status']]} {r['name']}: {r['entries']} entries{newest}{extra}{sample}")

    dead = [r for r in results if r["status"] == "dead"]
    stale = [r for r in results if r["status"] == "stale"]
    print(f"\nSummary: {len(results) - len(dead) - len(stale)} ok, {len(stale)} stale, {len(dead)} dead")
    if dead:
        print("Dead feeds should be fixed or removed from sources.json:")
        for r in dead:
            print(f"  - {r['name']}: {r['url']}")

    return 1 if (args.strict and dead) else 0


if __name__ == "__main__":
    sys.exit(main())
