"""
Machine-readable issue storage.

Every published issue is also written as JSON next to its HTML
(docs/newsletters/newsletter-YYYY-MM-DD.json). The weekly digest and the
per-story SEO pages are built from these files instead of scraping HTML.
"""

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from ..models import Newsletter
from ..logger import get_logger

logger = get_logger(__name__)


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    return str(value)


def issue_json_path(newsletters_dir: Path, date: datetime) -> Path:
    return newsletters_dir / f"newsletter-{date.strftime('%Y-%m-%d')}.json"


def save_issue_json(newsletter: Newsletter, newsletters_dir: Path) -> Path:
    """Serialize the full issue (stories, hits, number, grid, signals)."""
    newsletters_dir.mkdir(parents=True, exist_ok=True)
    path = issue_json_path(newsletters_dir, newsletter.date)
    payload = {
        "date": newsletter.date.strftime('%Y-%m-%d'),
        "title": newsletter.title,
        "email_subject": getattr(newsletter, 'email_subject', ""),
        "preheader": getattr(newsletter, 'preheader', ""),
        "intro_text": newsletter.intro_text,
        "stories": [asdict(s) for s in newsletter.stories],
        "quick_hits": [asdict(h) for h in (newsletter.quick_hits or [])],
        "big_number": asdict(newsletter.big_number) if newsletter.big_number else None,
        "perspective_grid": asdict(newsletter.perspective_grid) if newsletter.perspective_grid else None,
        "signals": [asdict(s) for s in (newsletter.signals or [])],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, default=_json_default)
    logger.info(f"Issue JSON saved: {path}")
    return path


def prune_orphaned_json(newsletters_dir: Path) -> int:
    """Remove issue JSONs whose HTML was rotated out of the archive."""
    removed = 0
    for json_file in newsletters_dir.glob("newsletter-*.json"):
        if not json_file.with_suffix('.html').exists():
            json_file.unlink()
            removed += 1
    return removed


def load_recent_issues(newsletters_dir: Path, days: int = 7) -> List[dict]:
    """Load the most recent `days` issues, oldest first."""
    files = sorted(newsletters_dir.glob("newsletter-*.json"))[-days:]
    issues = []
    for path in files:
        try:
            with open(path, encoding='utf-8') as f:
                issues.append(json.load(f))
        except Exception as e:
            logger.warning(f"Skipping unreadable issue JSON {path}: {e}")
    return issues


def story_slug(title: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "story"
