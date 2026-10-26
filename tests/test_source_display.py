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


def test_folha_english_edition_domain_is_named_1026():
    """10-26: the Brazil-runoff grid listed 'folha.com.br' as an outlet — the
    English edition's domain differs from the feed host in sources.json."""
    from src.newsletter.source_display import source_display_name
    assert source_display_name("https://www1.folha.com.br/internacional/en/world/2026/10/lula-wins.shtml") == "Folha de S.Paulo"
    assert source_display_name("https://www1.folha.uol.com.br/internacional/en/world/2026/10/lula-wins.shtml") == "Folha de S.Paulo"
