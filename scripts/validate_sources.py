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

try:
    import feedparser
except ImportError:
    print("feedparser is required: pip install feedparser")
    sys.exit(2)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = PROJECT_ROOT / "sources.json"
# Match the collector's browser UA so validation reflects production behavior
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def check_feed(source: dict, max_age_days: int) -> dict:
    name, url = source["name"], source["url"]
    result = {"name": name, "url": url, "status": "ok", "entries": 0, "newest": None, "detail": ""}
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
        status = getattr(feed, "status", None)
        if status and status >= 400:
            result.update(status="dead", detail=f"HTTP {status}")
            return result
        if feed.bozo and not feed.entries:
            result.update(status="dead", detail=f"parse error: {feed.bozo_exception}")
            return result
        result["entries"] = len(feed.entries)
        if not feed.entries:
            result.update(status="dead", detail="no entries")
            return result

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
    args = parser.parse_args()

    with open(SOURCES_FILE, encoding="utf-8") as f:
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
        print(f"{icon[r['status']]} {r['name']}: {r['entries']} entries{newest}{extra}")

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
