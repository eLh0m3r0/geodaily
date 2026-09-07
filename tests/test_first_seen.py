"""
Undated feed entries: first-seen dating in the collector and the freshness
guard on blindspot candidates (a ten-day-old Sixth Tone item once became
the Blindspot because undated entries were stamped "now" on every run).
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from src.ai.perspective_analyzer import PerspectiveAnalyzer
from src.collectors.first_seen import FirstSeenStore
from src.collectors.rss_collector import RSSCollector
from src.models import AIAnalysis, Article, NewsSource, SourceCategory


NOW = datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc)


class TestFirstSeenStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "first_seen.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_sighting_is_the_date_and_sticks(self):
        store = FirstSeenStore(self.path)
        self.assertEqual(store.date_for("https://x/1", "Sixth Tone", 0, now=NOW), NOW)
        later = store.date_for("https://x/1", "Sixth Tone", 0, now=NOW + timedelta(days=3))
        self.assertEqual(later, NOW)  # three days later it is no longer fresh

    def test_bootstrap_caps_backlog_of_unknown_source(self):
        store = FirstSeenStore(self.path)
        self.assertEqual(store.date_for("https://x/top", "Nikkei", 3, now=NOW), NOW)
        deep = store.date_for("https://x/deep", "Nikkei", 25, now=NOW)
        self.assertLess(deep, NOW - timedelta(days=7))

    def test_known_source_new_entries_are_fresh_at_any_position(self):
        store = FirstSeenStore(self.path)
        store.date_for("https://x/a", "Nikkei", 0, now=NOW)
        self.assertTrue(store.save(now=NOW))
        reopened = FirstSeenStore(self.path)
        self.assertEqual(reopened.date_for("https://x/b", "Nikkei", 40, now=NOW), NOW)

    def test_save_prunes_entries_gone_from_the_feed(self):
        store = FirstSeenStore(self.path)
        store.date_for("https://x/keep", "S", 0, now=NOW)
        store.date_for("https://x/gone", "S", 1, now=NOW - timedelta(days=20))
        self.assertTrue(store.save(now=NOW))
        entries = json.loads(self.path.read_text())["entries"]
        self.assertIn("https://x/keep", entries)
        self.assertNotIn("https://x/gone", entries)

    def test_bootstrap_old_entries_survive_pruning_while_still_in_feed(self):
        store = FirstSeenStore(self.path)
        store.date_for("https://x/deep", "Nikkei", 30, now=NOW)
        store.save(now=NOW)
        again = FirstSeenStore(self.path).date_for("https://x/deep", "Nikkei", 30,
                                                   now=NOW + timedelta(days=1))
        self.assertLess(again, NOW - timedelta(days=7))

    def test_without_path_it_is_memory_only(self):
        store = FirstSeenStore(None)
        self.assertEqual(store.date_for("u", "s", 0, now=NOW), NOW)
        self.assertFalse(store.save())


class TestCollectorDatesUndatedEntries(unittest.TestCase):
    def test_undated_entry_gets_first_seen_date(self):
        collector = RSSCollector(fetch_full_content=False)
        collector.first_seen = FirstSeenStore(None)
        source = NewsSource(name="Sixth Tone", url="https://sixthtone/rss",
                            category="regional", tier="tier1_rss")
        entry = Mock(spec=["title", "link", "summary"])
        entry.title = "Hundreds still missing after mudslide"
        entry.link = "https://sixthtone/news/1"
        entry.summary = "summary"

        self.assertIsNone(collector._parse_date(entry))
        first = collector._parse_rss_entry(entry, source, position=0)
        self.assertIsNotNone(first.published_date)
        again = collector._parse_rss_entry(entry, source, position=0)
        self.assertEqual(again.published_date, first.published_date)


class TestBlindspotFreshness(unittest.TestCase):
    @staticmethod
    def _article(url, cluster, perspective, age_hours):
        return Article(source=url, source_category=SourceCategory.REGIONAL, title=url,
                       url=url, summary="s", cluster_id=cluster, source_perspective=perspective,
                       published_date=datetime.now(timezone.utc) - timedelta(hours=age_hours))

    def test_stale_non_western_cluster_is_not_a_candidate(self):
        fresh = [self._article("f1", "c1", "chinese_state", 5),
                 self._article("f2", "c1", "east_asia", 8)]
        stale = [self._article("s1", "c2", "chinese_state", 240),
                 self._article("s2", "c2", "east_asia", 250)]
        story = AIAnalysis(story_title="x", why_important="w", what_overlooked="o",
                           prediction="p", impact_score=8, sources=["https://w/1"])
        candidates = PerspectiveAnalyzer()._blindspot_candidates([story], fresh + stale)
        self.assertEqual({m.cluster_id for ms in candidates for m in ms}, {"c1"})


if __name__ == "__main__":
    unittest.main()
