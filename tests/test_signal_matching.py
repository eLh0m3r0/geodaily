"""Polymarket matcher: a ubiquitous name alone must not select a market, and
the grid JSON parser must survive a doubled object / trailing prose."""

import unittest

from src.ai.perspective_analyzer import PerspectiveAnalyzer
from src.enrichment.signals import match_market, _term_hits
from src.models import AIAnalysis


def story(terms, title="x"):
    return AIAnalysis(story_title=title, why_important="w", what_overlooked="o",
                      prediction="p", impact_score=8, sources=["https://w/1"],
                      signal_terms=terms)


class TestGenericTermsNeedCorroboration(unittest.TestCase):
    markets = [
        {"question": "Will Trump acquire Greenland before 2027?", "volume": 9e6},
        {"question": "Will the IEA coordinate a strategic reserve release in 2026?", "volume": 1e5},
        {"question": "Will Trump impose new tariffs on the EU before 2027?", "volume": 5e6},
    ]

    def test_trump_alone_matches_nothing(self):
        self.assertIsNone(match_market(self.markets, story(["Trump", "diesel"])))

    def test_specific_term_matches(self):
        best = match_market(self.markets, story(["International Energy Agency", "IEA", "Trump"]))
        self.assertIsNotNone(best)
        self.assertIn("IEA", best["question"])

    def test_generic_plus_specific_counts_both(self):
        self.assertEqual(_term_hits("Will Trump impose tariffs on the EU?", ["Trump", "tariffs", "EU"]), 0)
        self.assertEqual(_term_hits("Will Trump acquire Greenland?", ["Trump", "Greenland"]), 2)


class TestGridJsonParser(unittest.TestCase):
    def test_doubled_object_parses_first(self):
        text = ('{"views": [{"group": "western", "framing": "a", "quote": "", "quote_article_index": 0}], '
                '"blindspot": null}\n{"views": [], "blindspot": null}')
        data = PerspectiveAnalyzer._parse_json_object(text)
        self.assertEqual(len(data["views"]), 1)

    def test_prose_around_object(self):
        text = 'Here is the analysis:\n```json\n{"views": [], "blindspot": null}\n```\nHope this helps.'
        self.assertEqual(PerspectiveAnalyzer._parse_json_object(text), {"views": [], "blindspot": None})

    def test_no_object(self):
        self.assertIsNone(PerspectiveAnalyzer._parse_json_object("I could not produce the grid."))


if __name__ == "__main__":
    unittest.main()


class TestRecentBlindspotRepeat(unittest.TestCase):
    """The repeat screen must key on the event, not on the shared
    'why it matters' framing every blindspot carries."""

    def setUp(self):
        self.persp = PerspectiveAnalyzer.__new__(PerspectiveAnalyzer)
        self.persp.recent_blindspots = [
            "China is advancing a mobilization law that could strengthen its readiness for a "
            "Taiwan conflict. It matters outside the region because it raises security risks "
            "in East Asia and could disrupt global trade.",
            "Meduza and The Moscow Times report that Russia's budget documents show a 27% rise "
            "in 2027 military spending. No Western outlet in today's pool covered it; the rise "
            "signals sustained war funding.",
        ]

    def test_different_event_with_same_framing_is_kept(self):
        text = ("The United States sanctioned Iran's rail and auto sectors and their foreign "
                "suppliers, Chinese and Iranian outlets report. It matters outside the region "
                "because it raises security risks and could disrupt global trade.")
        self.assertIsNone(self.persp._repeats_recent_blindspot(text))

    def test_same_storyline_reworded_is_still_caught(self):
        text = ("Russia plans record 17.1 trillion rubles for its military in 2027 while cutting "
                "welfare, education, and healthcare, Reuters reported. The budget signals "
                "prolonged war priorities and social strain.")
        self.assertIsNotNone(self.persp._repeats_recent_blindspot(text))


class TestTruncatedGridResponse(unittest.TestCase):
    def test_truncated_outer_object_is_not_mistaken_for_an_inner_view(self):
        text = '{"views": [{"group": "western", "framing": "a", "quote": "", "quote_article_index": 0}, {"group": "east_asia", "fra'
        self.assertIsNone(PerspectiveAnalyzer._parse_json_object(text))


class TestRecentBlindspotNeedsAnchor(unittest.TestCase):
    """Sharing a theme (fuel subsidies before an election) is not sharing a
    storyline: a repeat must also share a name or a figure."""

    def setUp(self):
        self.persp = PerspectiveAnalyzer.__new__(PerspectiveAnalyzer)
        self.persp.recent_blindspots = [
            "Brazil's government announced fuel tax cuts and extended subsidies weeks before a close "
            "presidential runoff. The move could ease inflation and sway voters in a major economy whose "
            "election affects global trade and climate policy."]

    def test_thematic_twin_in_another_country_is_kept(self):
        text = ("Nigeria's finance minister unveiled measures to ease fuel costs before elections, including "
                "subsidies for transport operators. The move could ease inflation and sway voters in Africa's "
                "largest economy, whose election affects regional trade.")
        self.assertIsNone(self.persp._repeats_recent_blindspot(text))

    def test_same_country_rewording_is_caught(self):
        text = ("Brazil's Lula government extended fuel subsidies and cut taxes to curb inflation ahead of "
                "the runoff, Folha reported. The subsidies matter because they tilt a close election.")
        self.assertIsNotNone(self.persp._repeats_recent_blindspot(text))


class TestMultiWordTermNeedsSpecificPart(unittest.TestCase):
    """A generic name inside a multi-word term ("Trump waiver") is not a
    specific hit — 2026-10-15 it selected the Greenland market again."""

    markets = [
        {"question": "Will Trump acquire Greenland before 2027?", "volume": 9e6},
        {"question": "Will the Strait of Hormuz be closed to shipping in 2026?", "volume": 1e6},
    ]

    def test_trump_waiver_does_not_select_trump_market(self):
        self.assertIsNone(match_market(self.markets, story(
            ["Alexander Novak", "Russian diesel", "Giorgia Meloni", "Trump waiver"])))

    def test_distinctive_part_of_multi_word_term_still_matches(self):
        best = match_market(self.markets, story(["Strait of Hormuz closure", "tanker traffic"]))
        self.assertIsNotNone(best)
        self.assertIn("Hormuz", best["question"])
