"""
Editorial-quality guardrails, pinned to real failures from the 2026-09
issue review (dates in the test names refer to those issues).
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai import editorial
from src.ai.perspective_analyzer import PerspectiveAnalyzer
from src.ai.simple_multi_stage_analyzer import SimplifiedMultiStageAnalyzer
from src.models import (AIAnalysis, Article, BigNumber, IssueContent, Newsletter,
                        PerspectiveGrid, PerspectiveView, QuickHit, SourceCategory)
from src.perspectives import blindspot_sources_line, coverage_summary, wire_copy_line


def art(title, url, source="Outlet", perspective="western_mainstream", state=False,
        cluster=None, summary="", hours_old=2):
    return Article(
        source=source, source_category=SourceCategory.MAINSTREAM, title=title, url=url,
        summary=summary or title, published_date=datetime.now(timezone.utc) - timedelta(hours=hours_old),
        cluster_id=cluster, source_perspective=perspective, state_affiliated=state,
    )


def story(title, why="", overlooked="", pred="", sources=None, impact=8):
    return AIAnalysis(story_title=title, why_important=why, what_overlooked=overlooked,
                      prediction=pred, impact_score=impact, sources=sources or [])


class FakeResponse:
    def __init__(self, text, model="deepseek/deepseek-v4.1-flash"):
        self.content = [SimpleNamespace(type="text", text=text)]
        self.usage = SimpleNamespace(input_tokens=100, output_tokens=50)
        self.model = model
        self.stop_reason = "end_turn"


class FakeClient:
    def __init__(self, texts):
        self.texts = list(texts)
        self.messages = self

    def create(self, **kwargs):
        return FakeResponse(self.texts.pop(0))


# ----------------------------------------------------------------------
# editorial helpers
# ----------------------------------------------------------------------

def test_title_case_headline_becomes_sentence_case_0926():
    body = ("Trump rejected Iran's offer to reopen a key oil route and stop fighting. "
            "He told aides he plans to resume bombing after the truce offer failed.")
    assert (editorial.to_sentence_case("Trump Rejects Iran's Truce Offer and Plans to Resume Bombing", body)
            == "Trump rejects Iran's truce offer and plans to resume bombing")


def test_sentence_case_and_acronyms_untouched():
    t = "NATO jets shoot down a drone over Lithuania"
    assert editorial.to_sentence_case(t, "the drone was shot down") == t
    t2 = "US Plans $2.8 Billion Bomb Sale to Israel"
    out = editorial.to_sentence_case(t2, "The plans for a $2.8 billion bomb sale to Israel went to Congress.")
    assert out == "US plans $2.8 billion bomb sale to Israel"
    # No evidence for a word -> leave the headline alone rather than half-convert it
    assert editorial.to_sentence_case("Houthi Rebels Seize Yemen's Mokha Port", "") == "Houthi Rebels Seize Yemen's Mokha Port"


def test_quick_hit_rerun_is_detected_0927_0928():
    prior = ["Swiss voters rejected a far-right plan to enshrine stricter neutrality, keeping government flexibility on sanctions."]
    rerun = "Swiss voters overwhelmingly rejected a far-right plan for 'total' neutrality, keeping sanctions on Russia."
    assert editorial.is_repeat(rerun, prior)


def test_shared_distinctive_figure_is_a_rerun_0923_0924():
    prior = ["450,000 — Scientists say a powerful El Niño could cause more than 450,000 deaths, mostly in poorer countries."]
    rerun = "A new study says the record El Nino could kill 450,000 people through extreme heat alone."
    assert editorial.is_repeat(rerun, prior)
    assert editorial.is_repeat("Russia adds 15,500 troops to its army.", ["Kenya hosts 15,500 runners in Nairobi marathon."]) is None


def test_update_with_new_figure_is_not_a_rerun():
    prior = ["The Philippines ferry fire death toll hit 35, with more than 50 people still missing."]
    update = "The death toll from the Philippine ferry fire rose to 76, with 13 people still missing."
    assert editorial.is_repeat(update, prior) is None


def test_telegraphic_copy_reads_choppy_0925():
    choppy = ["Zelensky says Trump made a final decision. Trump will let Ukraine produce Patriot "
              "missiles under license. Kyiv is short of these interceptors. They are the only "
              "reliable defense against Russian ballistic strikes. Building them locally could "
              "ease the shortage. But factories and tooling will take months."]
    normal = ["Trump will let Ukraine build Patriot interceptors under license, Zelensky says, "
              "easing a shortage of the only missiles that reliably stop Russian ballistic strikes. "
              "New factory lines would still take months to set up, so relief is not immediate."]
    assert editorial.reads_choppy(choppy)
    assert not editorial.reads_choppy(normal)


def test_history_excludes_today_and_carries_all_sections(tmp_path):
    def write(day, **extra):
        data = {"stories": [{"story_title": f"Story {day}"}],
                "quick_hits": [{"text": f"Hit {day}"}],
                "big_number": {"value": "74,000", "context": "Gaza toll"},
                "perspective_grid": {"blindspot": f"Blindspot {day}"}}
        (tmp_path / f"newsletter-2026-09-{day}.json").write_text(json.dumps(data))
    for d in ("26", "27", "28", "29"):
        write(d)
    hist = editorial.load_issue_history(tmp_path, days=2, today=datetime(2026, 9, 29).date())
    assert [h["date"] for h in hist] == ["2026-09-28", "2026-09-27"]
    block = editorial.format_history_block(hist)
    assert "QUICK HIT: Hit 28" in block and "BIG NUMBER: 74,000" in block and "BLINDSPOT: Blindspot 27" in block


# ----------------------------------------------------------------------
# analyzer post-generation rules
# ----------------------------------------------------------------------

@pytest.fixture
def analyzer(monkeypatch):
    a = SimplifiedMultiStageAnalyzer.__new__(SimplifiedMultiStageAnalyzer)
    a.mock_mode = False
    a.history = []
    a.meta = {}
    return a


def test_big_number_repeating_a_story_figure_is_dropped_0925(analyzer):
    issue = IssueContent(
        stories=[story("Hurricane Polo shuts Acapulco", why="Its pressure hit 892 millibars on September 22.")],
        big_number=BigNumber(value="892 millibars", context="Hurricane Polo's pressure reading.", url="u9"),
    )
    analyzer._apply_editorial_rules(issue, [])
    assert issue.big_number is None


def test_big_number_repeating_a_quick_hit_is_dropped_0927(analyzer):
    issue = IssueContent(
        stories=[story("Suicide bombing at Pakistan police checkpoint kills 12")],
        quick_hits=[QuickHit(text="The Palestinian death toll in the Gaza war crossed 74,000, the health ministry said.")],
        big_number=BigNumber(value="74,000", context="Palestinian death toll in the Gaza war crosses 74,000."),
    )
    analyzer._apply_editorial_rules(issue, [])
    assert issue.big_number is None


def test_fresh_big_number_is_kept(analyzer):
    issue = IssueContent(
        stories=[story("US and Iran hold indirect talks", why="Talks run through mediators.")],
        big_number=BigNumber(value="$518 billion", context="Anthropic's planned computing spending."),
    )
    analyzer._apply_editorial_rules(issue, [])
    assert issue.big_number is not None


def test_quick_hit_is_relinked_from_state_outlet_0929(analyzer):
    tass = art("Thailand flood toll reaches 23", "https://tass.com/1", "TASS", "russian_state", True, "event_7")
    bp = art("Thai floods kill 23", "https://bangkokpost.com/1", "Bangkok Post", "east_asia", False, "event_7")
    issue = IssueContent(stories=[story("Other story")],
                         quick_hits=[QuickHit(text="Thailand's flood death toll reaches 23.", url=tass.url)])
    analyzer._apply_editorial_rules(issue, [tass, bp])
    assert issue.quick_hits[0].url == bp.url


def test_quick_hit_rerun_from_history_is_dropped(analyzer):
    analyzer.history = [{"date": "2026-09-27", "stories": [], "big_number": "", "blindspot": "",
                         "quick_hits": ["Swiss voters rejected a far-right plan to enshrine stricter neutrality."]}]
    issue = IssueContent(stories=[story("Britain arrests five men near RAF Fairford")],
                         quick_hits=[QuickHit(text="Swiss voters overwhelmingly rejected a far-right plan for stricter neutrality.")])
    analyzer._apply_editorial_rules(issue, [])
    assert issue.quick_hits == []


def test_title_case_normalized_in_issue(analyzer):
    issue = IssueContent(stories=[story("Trump And Xi Wrap Up Their Second Summit Of The Year",
                                        why="Trump and Xi met in Washington; the summit will wrap up talks this year.")])
    analyzer._apply_editorial_rules(issue, [])
    assert issue.stories[0].story_title == "Trump and Xi wrap up their second summit of the year"


def test_choppy_readability_rewrite_is_rejected(analyzer, monkeypatch):
    from src.config import Config
    monkeypatch.setattr(Config, "READABILITY_MAX_GRADE", 5.0)
    original = [story("Trump grants Ukraine license to build Patriot missiles at home",
                      why=("Trump will let Ukraine manufacture Patriot interceptors under an American license, "
                           "President Zelensky announced, addressing a chronic shortage of air-defence missiles."),
                      overlooked=("No timeline, financing arrangement or participating American manufacturer "
                                  "has been announced for the production lines."),
                      pred="A formal agreement naming manufacturers and a start date for production.")]
    choppy = json.dumps([{"index": 0,
                          "why_important": "Trump made a choice. Ukraine can build Patriots. Kyiv is short. It needs them.",
                          "what_overlooked": "No dates yet. No money yet. No firms named.",
                          "prediction": "A deal. Names. A date."}])
    analyzer.client = FakeClient([choppy])
    out, *_ = analyzer._apply_readability_gate(original)
    assert out[0].why_important.startswith("Trump will let Ukraine manufacture")
    assert analyzer.meta["readability"]["rewrite"].startswith("rejected")


# ----------------------------------------------------------------------
# perspective grid + blindspot
# ----------------------------------------------------------------------

@pytest.fixture
def persp():
    p = PerspectiveAnalyzer.__new__(PerspectiveAnalyzer)
    p.mock_mode = True
    p.client = None
    p.recent_topics = []
    p.meta = {}
    return p


def test_state_only_blindspot_candidate_is_excluded_0925(persp):
    arts = [art("Russian and US envoys meet in the US", "https://tass.com/2", "TASS", "russian_state", True, "event_3"),
            art("Russian, US envoys hold talks", "https://rt.com/2", "RT", "russian_state", True, "event_3")]
    assert persp._blindspot_candidates([story("Other")], arts) == []


def test_blindspot_skips_storyline_already_covered_0913(persp):
    arts = [art("Repeated Hormuz strikes fuel fears of disrupted oil supplies", "https://a.com/1", "Al-Monitor", "middle_east", False, "event_4"),
            art("Hormuz strikes fuel oil supply fears", "https://b.com/1", "CNA", "east_asia", False, "event_4")]
    stories = [story("Deadly strike hits Iranian ship in the Strait of Hormuz, oil supplies at risk")]
    persp.recent_topics = ["Repeated strikes in Hormuz fuel oil supply fears"]
    assert persp._blindspot_candidates(stories, arts) == []


def test_blindspot_links_non_state_outlet_and_lists_outlets(persp):
    members = [art("Russia raises military spending 27%", "https://tass.com/9", "TASS", "russian_state", True, "event_5"),
               art("Budget shows 27% rise in military spending", "https://meduza.io/9", "Meduza", "russian_exile", False, "event_5")]
    assert persp._blindspot_link(members, "TASS reports a rise.").url == "https://meduza.io/9"


def test_blindspot_coverage_boilerplate_is_stripped_0929():
    text = ("Russia's budget documents show a 27% rise in 2027 military spending. No Western outlet in "
            "today's pool covered it; the rise signals sustained war funding.")
    cleaned = PerspectiveAnalyzer._clean_blindspot_text(text)
    assert "Western" not in cleaned and cleaned.startswith("Russia's budget")


def test_grid_parses_wire_copy_flag_and_blindspot(persp):
    persp.mock_mode = False
    west = art("US, Iran talk via mediators", "https://reuters.com/1", "Reuters", "western_mainstream", False, "event_1",
               summary="The US and Iran are talking through mediators, officials said on Monday.")
    asia = art("Mediators work on US-Iran deal", "https://koreatimes.co.kr/1", "The Korea Times", "east_asia", False, "event_1",
               summary="Mediators are working with Iran and the United States on a deal to end the fighting.")
    bs1 = art("Russia raises 2027 military spending 27%", "https://meduza.io/2", "Meduza", "russian_exile", False, "event_9")
    bs2 = art("Budget: Russian defence spending up 27%", "https://themoscowtimes.com/2", "The Moscow Times", "russian_exile", False, "event_9")
    reply = json.dumps({
        "views": [{"group": "western", "framing": "Stresses the gap between the two sides' terms.", "wire_copy": False,
                   "quote": "", "quote_article_index": 0},
                  {"group": "east_asia", "framing": "", "wire_copy": True, "quote": "", "quote_article_index": 1}],
        "blindspot": {"text": "Russia plans a 27% rise in 2027 military spending. No Western outlet in today's pool covered it.",
                      "article_index": 2}})
    persp.client = FakeClient([reply])
    grid = persp.build_grid(story("US and Iran hold indirect talks", sources=[west.url, asia.url]),
                            [west, asia, bs1, bs2])
    rows = {v.perspective: v for v in grid.views}
    assert rows["east_asia"].wire_copy and rows["east_asia"].framing == ""
    assert not rows["western"].wire_copy
    assert grid.blindspot == "Russia plans a 27% rise in 2027 military spending."
    assert grid.blindspot_outlets == ["Meduza", "The Moscow Times"]


# ----------------------------------------------------------------------
# render helpers
# ----------------------------------------------------------------------

def test_coverage_summary_distinguishes_reports_and_outlets():
    assert coverage_summary(6, {"african": 7, "western": 2, "middle_east": 1, "russian_state": 1}) == "11 reports from 6 outlets"
    assert coverage_summary(4, {"western": 2, "east_asia": 2}) == "4 outlets"


def test_wire_rows_collapse_into_one_line_in_rendered_issue():
    from src.newsletter.generator import NewsletterGenerator
    grid = PerspectiveGrid(total_outlets=6, counts={"east_asia": 3, "chinese_state": 2, "middle_east": 2},
                           views=[PerspectiveView("east_asia", ["The Korea Times"], 3,
                                                  framing="Runs wire copy: reports the facts without an editorial angle."),
                                  PerspectiveView("chinese_state", ["CGTN"], 2, wire_copy=True, state_affiliated=True),
                                  PerspectiveView("middle_east", ["Al Jazeera"], 2, framing="Skeptical of a quick deal.")],
                           blindspot="Russia plans a 27% rise in military spending.",
                           blindspot_outlets=["Meduza", "The Moscow Times"])
    nl = Newsletter(date=datetime(2026, 9, 29), title="Geopolitical Daily",
                    stories=[story("US and Iran hold indirect talks", why="w", overlooked="o", pred="p")],
                    perspective_grid=grid)
    gen = NewsletterGenerator()
    for html in (gen.generate_html(nl), gen.generate_email_html(nl)):
        assert "Runs wire copy" not in html
        assert "Straight news, no distinct angle: East Asian media (3), Chinese state media (2, state)" in html
        assert "Skeptical of a quick deal." in html
        assert "Reported by Meduza and The Moscow Times" in html
        assert "7 reports from 6 outlets" in html
    assert wire_copy_line(grid.views).startswith("Straight news")
    assert blindspot_sources_line([]) == ""
