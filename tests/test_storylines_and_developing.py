"""
Storylines, DEVELOPING and the 2026-10 review fixes, pinned to the real
cases from the 2026-10-01..06 issues.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai import editorial
from src.ai.perspective_analyzer import PerspectiveAnalyzer
from src.ai.simple_multi_stage_analyzer import SimplifiedMultiStageAnalyzer
from src.ai.storylines import StorylineIndex, distinctive_tokens, proper_terms
from src.models import (AIAnalysis, Article, BigNumber, DevelopingItem, IssueContent, Newsletter,
                        QuickHit, SourceCategory)

ROOT = Path(__file__).parent.parent


def story(title, why="w", overlooked="o", pred="p", terms=(), sources=None, region="global"):
    return AIAnalysis(story_title=title, why_important=why, what_overlooked=overlooked,
                      prediction=pred, impact_score=8, sources=sources or ["https://x.com/" + title[:5]],
                      region=region, signal_terms=list(terms))


def art(title, url, source="Outlet", perspective="western_mainstream", state=False, cluster=None, summary=""):
    return Article(source=source, source_category=SourceCategory.MAINSTREAM, title=title, url=url,
                   summary=summary or title, published_date=datetime.now(timezone.utc) - timedelta(hours=2),
                   cluster_id=cluster, source_perspective=perspective, state_affiliated=state)


HISTORY = [  # newest first, as load_issue_history returns it
    {"date": "2026-10-05",
     "stories": ["Brazil's election goes to a runoff as Bolsonaro edges past Lula",
                 "US pulls B-1 bombers from UK base after terror plot"],
     "story_terms": [["Brazil", "Lula", "Bolsonaro"], ["RAF Fairford", "B-1 bombers"]],
     "quick_hits": ["A lab worker in Siberia died of suspected plague, and the White House is monitoring."],
     "developing": [], "big_number": "", "blindspot": ""},
    {"date": "2026-10-04",
     "stories": ["Ethiopian troops seize Mekelle as Tigray fighting flares again"],
     "story_terms": [["Tigray", "Mekelle", "TPLF", "Ethiopia"]],
     "quick_hits": [], "developing": [], "big_number": "", "blindspot": ""},
    {"date": "2026-10-03",
     "stories": ["UAE calls flydubai cockpit axe attack a terrorist act"],
     "story_terms": [["flydubai", "Hammam al-Hammami", "Oman", "UAE"]],
     "quick_hits": [], "developing": [], "big_number": "", "blindspot": ""},
]


# ----------------------------------------------------------------------
# storyline identity
# ----------------------------------------------------------------------

def test_distinctive_tokens_keep_names_and_drop_generic_actors():
    assert distinctive_tokens("Russia") == set()
    assert distinctive_tokens("housing protests") == set()
    assert "fairford" in distinctive_tokens("RAF Fairford")
    assert "flydubai" in distinctive_tokens("flydubai", any_case=True)
    assert distinctive_tokens("International Criminal Court") == set()


def test_flydubai_is_recognised_as_our_storyline_0105():
    idx = StorylineIndex(HISTORY)
    hit = idx.match("A flydubai co-pilot accused of stabbing his captain told UAE interrogators "
                    "he planned the attack before being hired", days=5)
    assert hit and hit[1] == "flydubai"


def test_demonym_suffix_matches_siberia_siberian_1006():
    idx = StorylineIndex(HISTORY)
    hit = idx.match("A Siberian laboratory technician died of suspected pneumonic plague", days=3)
    assert hit and hit[1] == "siberia"


def test_unrelated_item_does_not_match():
    idx = StorylineIndex(HISTORY)
    assert idx.match("The Parti Quebecois won Quebec's provincial election", days=5) is None
    assert proper_terms("Leaders visited Tuvalu to see rising seas") == {"tuvalu"}


# ----------------------------------------------------------------------
# DEVELOPING enforcement in the analyzer
# ----------------------------------------------------------------------

@pytest.fixture
def analyzer():
    a = SimplifiedMultiStageAnalyzer.__new__(SimplifiedMultiStageAnalyzer)
    a.mock_mode = False
    a.history = HISTORY[:2]
    a.meta = {}
    a.storylines = StorylineIndex(HISTORY)
    return a


def test_running_story_below_the_lead_is_demoted_to_developing_1006(analyzer):
    issue = IssueContent(stories=[
        story("Ukraine hits Moscow with one of its largest drone attacks", terms=["Moscow", "Sobyanin"]),
        story("Pakistan and Turkey discuss troops for Saudi Arabia", terms=["Makkah Defence Agreement"]),
        story("Airstrikes and forced recruitment as Ethiopia's Tigray war returns",
              terms=["Tigray", "Mekelle", "TPLF"], region="africa"),
    ])
    analyzer._apply_storyline_rules(issue)
    assert [s.story_title[:7] for s in issue.stories] == ["Ukraine", "Pakista"]
    assert issue.developing[0].storyline.lower() in {"tigray", "mekelle", "tplf", "ethiopia"}
    assert "Tigray" in issue.developing[0].text


def test_a_running_lead_is_allowed(analyzer):
    issue = IssueContent(stories=[story("Ethiopian army takes Tigray's last city", terms=["Tigray"]),
                                  story("Fresh event one"), story("Fresh event two")])
    analyzer._apply_storyline_rules(issue)
    assert len(issue.stories) == 3 and issue.developing == []


def test_quick_hit_in_running_storyline_moves_to_developing(analyzer):
    issue = IssueContent(stories=[story("Fresh lead")],
                         quick_hits=[QuickHit(text="Brazil's stock exchange hit a record after Bolsonaro's showing."),
                                     QuickHit(text="Japan protested to Washington after a US Marine was arrested in Okinawa.")])
    analyzer._apply_storyline_rules(issue)
    assert [d.storyline for d in issue.developing] == ["Bolsonaro"]
    assert len(issue.quick_hits) == 1 and "Okinawa" in issue.quick_hits[0].text


def test_quick_hit_restating_todays_story_is_dropped(analyzer):
    issue = IssueContent(stories=[story("Spain calls snap election", terms=["Pedro Sánchez", "Spain"])],
                         quick_hits=[QuickHit(text="Pedro Sánchez dissolved parliament on Monday.")])
    analyzer._apply_storyline_rules(issue)
    assert issue.quick_hits == [] and issue.developing == []


def test_developing_is_capped_and_one_per_storyline(analyzer):
    items = [DevelopingItem("Tigray", f"New fact {i} with figure {i}0.") for i in range(3)] + \
            [DevelopingItem("Fairford", "Police charged two men."), DevelopingItem("Flydubai", "Oman opened a probe."),
             DevelopingItem("Brazil", "Debates set for Thursday.")]
    issue = IssueContent(stories=[story("Fresh lead")], developing=items)
    analyzer._apply_storyline_rules(issue)
    labels = [d.storyline for d in issue.developing]
    assert len(labels) == 3 and labels.count("Tigray") == 1


def test_background_big_number_is_dropped_1005(analyzer):
    issue = IssueContent(stories=[story("Fresh lead")],
                         big_number=BigNumber("6%", "The Green Party's vote share in 2024, before it labelled Zionism racism."))
    analyzer._apply_editorial_rules(issue, [])
    assert issue.big_number is None


def test_nobel_science_prize_is_not_a_quick_hit_1006(analyzer):
    issue = IssueContent(stories=[story("Fresh lead")],
                         quick_hits=[QuickHit(text="The Nobel Prize in medicine went to three optogenetics pioneers."),
                                     QuickHit(text="The Nobel Peace Prize went to Memorial and two Ukrainian groups.")])
    analyzer._apply_editorial_rules(issue, [])
    assert [h.text[:16] for h in issue.quick_hits] == ["The Nobel Peace "]


def test_headline_overclaim_is_flagged_but_caveats_are_not_1006(analyzer):
    issue = IssueContent(stories=[
        story("Pakistan and Turkey agree to send troops to Saudi Arabia",
              overlooked="No independent source has confirmed any deployment."),
        story("Ukraine hits Moscow with drones", overlooked="Russia says it shot down 105, a figure Ukraine has not confirmed."),
    ])
    analyzer._apply_editorial_rules(issue, [])
    flags = analyzer.meta["quality_flags"]
    assert len(flags) == 1 and "Pakistan" in flags[0]


# ----------------------------------------------------------------------
# blindspot + grid
# ----------------------------------------------------------------------

@pytest.fixture
def persp():
    p = PerspectiveAnalyzer.__new__(PerspectiveAnalyzer)
    p.mock_mode = True
    p.client = None
    p.recent_topics = []
    p.recent_blindspots = []
    p.meta = {}
    p.storylines = StorylineIndex(HISTORY)
    return p


def test_our_own_storyline_is_never_a_blindspot_1005(persp):
    arts = [art("Flydubai co-pilot planned attack before being hired, Israel says", "https://a.com/1",
                "Al-Monitor", "middle_east", False, "e9"),
            art("Co-pilot of flydubai flight planned attack", "https://b.com/1", "Dawn", "south_asia", False, "e9")]
    assert persp._blindspot_candidates([story("Ukraine hits Moscow")], arts) == []


def test_fresh_non_western_event_remains_a_candidate(persp):
    arts = [art("Kenya parliament impeaches deputy president Gachagua", "https://a.com/2", "Nation", "african", False, "e7"),
            art("Kenyan MPs vote to impeach Gachagua", "https://b.com/2", "Daily Maverick", "african", False, "e7")]
    assert len(persp._blindspot_candidates([story("Ukraine hits Moscow")], arts)) == 1


def test_grid_members_focus_on_the_event_1004(persp):
    s = story("Russia hits Kyiv's Dnipro bridges for the first time",
              terms=["Kyiv", "Dnipro River", "Pivnichnyi Bridge"], sources=["https://bbc.com/1"])
    members = [art("Russia strikes Kyiv bridge over the Dnipro", "https://bbc.com/1", "BBC", cluster="e1"),
               art("Drone hits Pivnichnyi Bridge", "https://up.com/1", "Ukrainska Pravda", "ukrainian", cluster="e1"),
               art("Ukrainian attacks kill one in DPR", "https://tass.com/1", "TASS", "russian_state", True, "e1")]
    focused = persp._focus_members(s, members, {"https://bbc.com/1"})
    assert [a.source for a in focused] == ["BBC", "Ukrainska Pravda"]


def test_future_dated_past_event_quote_is_rejected_1004():
    today = datetime(2026, 10, 4, tzinfo=timezone.utc)
    assert PerspectiveAnalyzer._future_dated_past_event(
        "Russian forces struck the Pivnichnyi Bridge in Kyiv on 14 October, hitting the roadway", today)
    assert not PerspectiveAnalyzer._future_dated_past_event("They face a runoff on October 25", today)


# ----------------------------------------------------------------------
# rendering, footer, workflow guard, quality report
# ----------------------------------------------------------------------

def test_developing_section_renders_and_intro_counts_it():
    from src.newsletter.generator import NewsletterGenerator
    gen = NewsletterGenerator()
    nl = gen.generate_newsletter([story("Fresh lead", why="Why it matters here.")],
                                 date=datetime(2026, 10, 6),
                                 quick_hits=[QuickHit(text="Japan protested to Washington.", region="indo_pacific")],
                                 developing=[DevelopingItem("Tigray", "Airstrikes killed 17 near Mekelle.", "africa", "https://a.com")])
    assert "1 update on stories you're following" in nl.intro_text
    for html in (gen.generate_html(nl), gen.generate_email_html(nl)):
        assert "Developing" in html and "Tigray:" in html and "Airstrikes killed 17" in html
        assert "human review before sending" not in html


def test_manual_runs_are_guarded_unless_forced():
    wf = (ROOT / ".github/workflows/daily_newsletter.yml").read_text()
    data = yaml.safe_load(wf)
    triggers = data.get("on") or data.get(True)
    assert "force" in triggers["workflow_dispatch"]["inputs"]
    assert 'if [ "$EVENT_NAME" = "workflow_dispatch" ] && { [ "$FORCE" = "true" ]' in wf
    assert '[ "${{ github.event_name }}" = "workflow_dispatch" ]; then\n          echo "ALLOW_OVERWRITE=true"' not in wf


def test_quality_report_flags_degraded_issue(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import issue_quality_report as q
    rows = q.check({"stories": [{"story_title": "a"}, {"story_title": "b"}],
                    "perspective_grid": {"views": []}, "quick_hits": [], "meta": {}})
    warned = {label for status, label, _ in rows if status == "warn"}
    assert {"Grid rows with an angle", "Blindspot", "Also today"} <= warned


def test_length_truncated_empty_reply_retries_with_bigger_budget(monkeypatch):
    """2026-10-06 shadow run: reasoning ate 16000 tokens four times and the
    issue failed. An empty finish=length reply must grow the budget, never
    cap the reasoning."""
    from unittest.mock import patch
    from src.ai import llm_client
    budgets = []

    def fake_post(url, headers=None, json=None, timeout=None):
        budgets.append(json["max_tokens"])
        assert "reasoning" not in json
        if len(budgets) == 1:
            return SimpleNamespace(status_code=200, text="{}", json=lambda: {
                "model": "deepseek/deepseek-v4.1-flash", "provider": "Together",
                "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 16000,
                          "completion_tokens_details": {"reasoning_tokens": 16000}}})
        return SimpleNamespace(status_code=200, text="{}", json=lambda: {
            "model": "deepseek/deepseek-v4.1-flash", "provider": "DeepInfra",
            "choices": [{"message": {"content": "{\"ok\": 1}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20000}})

    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    client = llm_client.OpenRouterClient(api_key="k", timeout=5, max_retries=3)
    with patch.object(llm_client.requests, "post", side_effect=fake_post):
        resp = client.messages.create(model="deepseek/deepseek-v4.1-flash", max_tokens=16000,
                                      messages=[{"role": "user", "content": "hi"}])
    assert budgets == [16000, 32000]
    assert resp.content[0].text == '{"ok": 1}'


def test_generic_office_words_are_not_storylines():
    idx = StorylineIndex([{"date": "2026-10-05", "stories": ["Estonia blames Russian Military Intelligence for arson"],
                           "story_terms": [["Estonia", "Russian Military Intelligence"]],
                           "quick_hits": [], "developing": [], "big_number": "", "blindspot": ""}])
    assert idx.match("Germany arrested its former Federal Intelligence Service chief on espionage charges",
                     days=3) is None


def test_big_number_must_be_a_figure_and_not_a_running_story(analyzer):
    issue = IssueContent(stories=[story("Fresh lead")],
                         big_number=BigNumber("Hundreds", "People quarantined after a plague death in Siberia."))
    analyzer._apply_editorial_rules(issue, [])
    assert issue.big_number is None
    issue = IssueContent(stories=[story("Fresh lead")],
                         big_number=BigNumber("4,000", "Ebola deaths in eastern Congo since May."))
    analyzer._apply_editorial_rules(issue, [])
    assert issue.big_number is not None


def test_event_run_by_a_western_outlet_elsewhere_is_no_blindspot(persp):
    arts = [art("Ukrainian drones hit Moscow region fuel depot, kill two", "https://meduza.io/9", "Meduza", "russian_exile", False, "e5"),
            art("Moscow region fuel depot hit by Ukrainian drones", "https://st.com/9", "The Straits Times", "east_asia", False, "e5"),
            art("Massive Ukrainian drone attack hits Moscow region fuel depot", "https://france24.com/9", "France 24",
                "western_mainstream", False, "e6")]
    assert persp._blindspot_candidates([story("Kenya confirms Ebola case")], arts) == []


def test_reserve_story_becomes_a_quick_hit_unless_a_demotion_made_room(analyzer):
    analyzer.target_stories = 3
    issue = IssueContent(stories=[story("Fresh lead"), story("Fresh two"), story("Fresh three"),
                                  story("Reserve event", why="Chile's congress approved a new constitution draft on Monday.")])
    analyzer._apply_storyline_rules(issue)
    assert len(issue.stories) == 3 and issue.quick_hits[0].text.startswith("Chile's congress")
    issue = IssueContent(stories=[story("Fresh lead"), story("Ethiopian troops press on in Tigray", terms=["Tigray"]),
                                  story("Fresh three"), story("Reserve event")])
    analyzer._apply_storyline_rules(issue)
    assert [s.story_title for s in issue.stories] == ["Fresh lead", "Fresh three", "Reserve event"]
    assert any("Story demoted" in a for a in analyzer.meta["editorial_actions"])


def test_todays_story_split_across_clusters_is_no_blindspot(persp):
    arts = [art("Massive Ukrainian drone attack on Moscow region kills two, sets largest oil depot ablaze",
                "https://meduza.io/8", "Meduza", "russian_exile", False, "e4"),
            art("Ukrainian drones hit Moscow region fuel depot", "https://st.com/8", "The Straits Times", "east_asia", False, "e4")]
    s = story("Ukraine hits Moscow region with hundreds of drones, killing two people",
              why="Russia said its air defences shot down nearly 900 drones overnight.")
    assert persp._blindspot_candidates([s], arts) == []
