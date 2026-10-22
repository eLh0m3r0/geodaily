"""
An English newsletter cannot cite an article its readers cannot read: RSS
entries whose title is mostly in a non-Latin script are skipped at
collection (2026-10-21: the Novaya Gazeta Europe feed turned out to be the
Russian-language edition — five quick hits in 10-06..10-21 linked readers
to Russian articles).
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.first_seen import FirstSeenStore
from src.collectors.rss_collector import RSSCollector
from src.models import NewsSource


def _entry(title, link="https://novayagazeta.eu/articles/2026/10/21/x"):
    entry = Mock(spec=["title", "link", "summary"])
    entry.title = title
    entry.link = link
    entry.summary = "summary"
    return entry


class TestNonLatinTitlesAreSkipped(unittest.TestCase):
    def setUp(self):
        self.collector = RSSCollector(fetch_full_content=False)
        self.collector.first_seen = FirstSeenStore(None)
        self.source = NewsSource(name="Novaya Gazeta Europe", url="https://novayagazeta.eu/feed/rss",
                                 category="mainstream", tier="tier1_rss")

    def test_russian_title_is_skipped(self):
        entry = _entry("Осуждённый за антивоенные посты калининградец заявил, что в Литве ему не дали "
                       "запросить убежище")
        self.assertIsNone(self.collector._parse_rss_entry(entry, self.source, position=0))

    def test_cjk_title_is_skipped(self):
        self.assertIsNone(self.collector._parse_rss_entry(
            _entry("美国特使威特科夫抵达圣彼得堡与普京会谈"), self.source, position=0))

    def test_english_title_with_a_foreign_word_is_kept(self):
        article = self.collector._parse_rss_entry(
            _entry("Russia's 'Орешник' missile hits Dnipro, officials say"), self.source, position=0)
        self.assertIsNotNone(article)
        self.assertEqual(article.source, "Novaya Gazeta Europe")

    def test_accented_latin_titles_are_kept(self):
        for title in ("Élections: Sébastien Lecornu refuse de démissionner",
                      "Erdoğan: Türkiye won't recognise Kosovo's new government",
                      "Côte d'Ivoire: 53 killed as Abyei market strike toll rises"):
            self.assertIsNotNone(self.collector._parse_rss_entry(_entry(title), self.source, 0), title)

    def test_mostly_foreign_feed_is_reported(self):
        skipped = [self.collector._parse_rss_entry(_entry(t), self.source, i) for i, t in enumerate(
            ("В Черногории задержали создателя Z-проекта Rybar", "Дроны ударили по двум домам в Харькове",
             "Starlink limits in Ukraine"))]
        self.assertEqual([a is None for a in skipped], [True, True, False])
        self.assertEqual(self.collector.script_skips.get("Novaya Gazeta Europe"), 2)


if __name__ == "__main__":
    unittest.main()


class TestFeedRequestHeaders(unittest.TestCase):
    """Human Rights Watch answered the collector's XML-only Accept header with
    403 and Nation Africa with 404 (every run up to 2026-10-22), while a
    browser-like header set read both; the collector now sends one."""

    def test_feed_requests_look_like_a_browser(self):
        from unittest.mock import patch
        collector = RSSCollector(fetch_full_content=False)
        with patch("src.collectors.rss_collector.connection_pool_manager.make_request") as make_request:
            make_request.return_value = Mock(content=b"<rss/>", raise_for_status=lambda: None)
            collector._fetch_feed_with_retry("https://www.hrw.org/rss.xml", "Human Rights Watch")
        headers = make_request.call_args.kwargs["headers"]
        self.assertIn("*/*", headers["Accept"])
        self.assertTrue(headers["Accept-Language"].startswith("en"))
        self.assertTrue(headers["User-Agent"].startswith("Mozilla/5.0"))
