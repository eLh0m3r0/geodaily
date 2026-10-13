"""Outlet names never leak as raw domains: mirror domains map to the outlet."""

import unittest

from src.newsletter.source_display import source_display_name


class TestSourceDisplayName(unittest.TestCase):
    def test_rt_mirror_domain_maps_to_rt(self):
        self.assertEqual(source_display_name(
            "https://rt-english.com/news/647110-uk-iran-false-flag-plot/?utm_source=rss"), "RT")

    def test_rt_main_domain_maps_to_rt(self):
        self.assertEqual(source_display_name("https://www.rt.com/news/647110-uk-iran/"), "RT")

    def test_known_outlet(self):
        self.assertEqual(source_display_name("https://www.scmp.com/news/china/article/1"),
                         "South China Morning Post")


if __name__ == "__main__":
    unittest.main()
