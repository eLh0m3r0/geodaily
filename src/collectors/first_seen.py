"""
First-seen dates for feed entries that carry no publication date.

A few feeds (Sixth Tone, Nikkei Asia) publish no <pubDate>. Stamping such
entries with "now" made every item in those feeds look fresh on every run —
which is how a ten-day-old article became an issue's Blindspot. Instead,
the first time an undated URL shows up in a feed is recorded here and used
as its publication date, so an undated entry is fresh for exactly one issue.

The store lives under docs/ so the daily workflow's archive commit persists
it between runs. Entries are pruned once they have been absent from the feed
for RETENTION_DAYS.
"""

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from ..logger import get_logger

logger = get_logger(__name__)


class FirstSeenStore:
    """Thread-safe url -> first-seen timestamp map with JSON persistence."""

    RETENTION_DAYS = 14
    # Feeds are newest-first. When a source has no history yet (first run
    # after deploy, or a newly added feed), only its top entries count as
    # fresh; the rest are recorded as already old so a feed's whole backlog
    # can't flood a single issue.
    BOOTSTRAP_FRESH_ENTRIES = 10

    def __init__(self, path: Optional[Path]):
        self.path = Path(path) if path else None
        self._entries: Optional[Dict[str, dict]] = None
        self._history_sources: set = set()
        self._dirty = False
        self._lock = threading.Lock()

    # -- persistence ------------------------------------------------------

    def _load(self) -> Dict[str, dict]:
        if self._entries is None:
            data: Dict[str, dict] = {}
            if self.path and self.path.exists():
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict) and isinstance(raw.get("entries"), dict):
                        data = raw["entries"]
                except Exception as e:
                    logger.warning(f"Could not read first-seen store {self.path}: {e}")
            self._entries = data
            self._history_sources = {r.get("s") for r in data.values() if isinstance(r, dict)}
        return self._entries

    @staticmethod
    def _parse(ts: str) -> Optional[datetime]:
        try:
            dt = datetime.fromisoformat(ts)
        except (TypeError, ValueError):
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def save(self, now: Optional[datetime] = None) -> bool:
        """Prune entries absent from their feed for RETENTION_DAYS and write.
        Returns True when the file was written."""
        if self.path is None:
            return False
        with self._lock:
            entries = self._load()
            now = now or datetime.now(timezone.utc)
            cutoff = now - timedelta(days=self.RETENTION_DAYS)
            kept = {}
            for url, rec in entries.items():
                last = self._parse(rec.get("l") or rec.get("t") or "")
                if last and last >= cutoff:
                    kept[url] = rec
            if not self._dirty and len(kept) == len(entries):
                return False
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps({"entries": kept}, indent=0, sort_keys=True),
                               encoding="utf-8")
                tmp.replace(self.path)
            except Exception as e:
                logger.warning(f"Could not write first-seen store {self.path}: {e}")
                return False
            self._entries = kept
            self._dirty = False
            logger.info(f"First-seen store saved: {len(kept)} undated entries tracked")
            return True

    # -- lookup -----------------------------------------------------------

    def date_for(self, url: str, source: str, position: int = 0,
                 now: Optional[datetime] = None) -> datetime:
        """Publication date to use for an undated entry: the moment it was
        first seen (recorded now if new). `position` is the entry's index in
        the feed, used only to bootstrap a source without history."""
        now = now or datetime.now(timezone.utc)
        with self._lock:
            entries = self._load()
            rec = entries.get(url)
            if isinstance(rec, dict):
                first = self._parse(rec.get("t") or "")
                if first:
                    rec["l"] = now.isoformat()
                    self._dirty = True
                    return first
            seen = now
            if source not in self._history_sources and position >= self.BOOTSTRAP_FRESH_ENTRIES:
                seen = now - timedelta(days=self.RETENTION_DAYS)
            entries[url] = {"t": seen.isoformat(), "l": now.isoformat(), "s": source}
            self._dirty = True
            return seen
