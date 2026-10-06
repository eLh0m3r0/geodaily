"""
Perspective extraction for the big story — the product's core differentiator.

Given the day's big story and the full article pool, this module builds the
"How the world covers it" grid: per perspective group, a verbatim quote and a
one-sentence framing summary, plus the day's blindspot (a story one part of
the world covers heavily while the rest ignores it).

One Claude call per issue. The model must QUOTE outlets verbatim, never
paraphrase them — LLMs otherwise inject their own framing (arXiv 2505.05406;
Springer 2026) — and quotes are verified as substrings of the provided
article text; failed verification keeps the framing but drops the quote.
"""

import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from ..models import Article, AIAnalysis, PerspectiveGrid, PerspectiveView
from ..config import Config
from ..perspectives import group_of, label_of, STATE_GROUPS, NON_WESTERN_GROUPS, GROUP_ORDER
from ..newsletter.source_display import source_display_name
from ..archiver.ai_data_archiver import ai_archiver
from .cost_controller import ai_cost_controller
from .api_utils import extract_response_text, response_tokens_and_cost
from .llm_client import build_llm_client, ai_credentials_present
from .editorial import content_words, history_texts, load_issue_history, overlap
from .storylines import StorylineIndex, distinctive_tokens, text_has

logger = logging.getLogger(__name__)

MAX_ARTICLES_PER_GROUP = 3
EXCERPT_CHARS = 450
WIRE_COPY_PREFIX = "runs wire copy"


class PerspectiveAnalyzer:
    """Builds the perspective grid for the big story in one API call."""

    def __init__(self):
        self.mock_mode = Config.DRY_RUN or not ai_credentials_present()
        self.client = None
        # Provenance of the grid call, merged into the issue's meta
        self.meta: Dict[str, object] = {}
        # Recent issues' stories and blindspots: a blindspot must be news the
        # reader has NOT already had (09-17 resurfaced the 09-15 lead story).
        self.recent_topics: List[str] = []
        self.recent_blindspots: List[str] = []
        # Everything the last 5 issues covered, by distinctive names: a
        # blindspot is never one of OUR running stories (10-05 offered
        # flydubai — the week's most-covered story — as "the story the West
        # missed").
        self.storylines = StorylineIndex([])
        if Config.ENABLE_NEWSLETTER_HISTORY:
            try:
                history = load_issue_history(Config.NEWSLETTERS_DIR, days=max(3, Config.NEWSLETTER_HISTORY_DAYS))
                self.recent_topics = history_texts(history, "stories", "blindspot")
                self.recent_blindspots = history_texts(history, "blindspot")
                self.storylines = StorylineIndex(load_issue_history(Config.NEWSLETTERS_DIR, days=5))
            except Exception as e:
                logger.warning(f"Issue history unavailable for blindspot screening: {e}")
        if not self.mock_mode:
            try:
                self.client = build_llm_client()
            except Exception as e:
                logger.error(f"Perspective analyzer client init failed: {e}")
                self.mock_mode = True

    # ------------------------------------------------------------------
    # Article selection
    # ------------------------------------------------------------------

    def _story_articles(self, story: AIAnalysis, articles: List[Article]) -> List[Article]:
        """All articles belonging to the big story's event cluster(s)."""
        source_urls = set(story.sources or [])
        cited = [a for a in articles if a.url in source_urls]
        cluster_ids = {a.cluster_id for a in cited if getattr(a, 'cluster_id', None)}
        if cluster_ids:
            members = [a for a in articles if getattr(a, 'cluster_id', None) in cluster_ids]
        else:
            members = cited
        members = self._focus_members(story, members, source_urls)
        # Stable order: cited articles first, then by source weight
        members.sort(key=lambda a: (a.url not in source_urls, -(a.source_weight or 1.0)))
        return members

    @staticmethod
    def _focus_members(story: AIAnalysis, members: List[Article], source_urls: set) -> List[Article]:
        """Keep the cluster members that name the event, not merely its actors.

        Embedding clusters are topical: 10-04's "Kyiv bridges" cluster carried
        a TASS piece on casualties in Donetsk, 10-01's Kaliningrad cluster an
        FT op-ed on hybrid war — and each became a grid row speaking for its
        whole perspective group. A member stays when it mentions one of the
        story's distinctive names (signal terms minus generic actors) or is
        cited by the story. No-op when the story has no distinctive name or
        filtering would leave fewer than 2 members."""
        patterns = set()
        for term in story.signal_terms or []:
            patterns |= distinctive_tokens(term, any_case=" " not in term.strip())
        if not patterns:
            return members
        focused = []
        for a in members:
            text = f"{a.title} {(getattr(a, 'full_content', None) or a.summary or '')[:600]}".lower()
            if a.url in source_urls or any(text_has(text, p) for p in patterns):
                focused.append(a)
        if len(focused) < 2:
            return members
        if len(focused) < len(members):
            logger.info(f"Grid members focused on {sorted(patterns)[:4]}: {len(members)} -> {len(focused)}")
        return focused

    def _group_articles(self, members: List[Article]) -> Dict[str, List[Article]]:
        groups = defaultdict(list)
        for a in members:
            g = group_of(getattr(a, 'source_perspective', 'western_mainstream'))
            if len(groups[g]) < MAX_ARTICLES_PER_GROUP:
                groups[g].append(a)
        return dict(groups)

    # A blindspot is today's news, not a backlog item: members older than
    # this (or undated) are never candidates, whatever the collector let in.
    BLINDSPOT_MAX_AGE_HOURS = 36
    # Never a blindspot: sports, entertainment, celebrity and lifestyle
    # events (the issue rule "no sports/celebrity" applies here too — the
    # 2026-09-16 blindspot was a World Athletics hosting bid).
    _OFF_TOPIC = re.compile(
        r"\b(athletics|olympic|olympics|world cup|championship|championships|"
        r"tournament|football|soccer|cricket|rugby|tennis|basketball|golf|"
        r"formula ?1|grand prix|marathon|medal|medals|fifa|uefa|ioc|premier league|"
        r"la liga|nba|nfl|mlb|nhl|ipl|stadium|coach|striker|goalkeeper|"
        r"celebrity|celebrities|actor|actress|singer|rapper|pop star|box office|"
        r"film festival|album|concert|grammy|oscar|oscars|emmy|netflix|k-pop|"
        r"royal wedding|miss universe|beauty pageant)\b", re.I)

    @classmethod
    def _off_topic(cls, article: Article) -> bool:
        return bool(cls._OFF_TOPIC.search(getattr(article, 'title', '') or ''))

    @classmethod
    def _is_fresh(cls, article: Article, now: datetime) -> bool:
        published = getattr(article, 'published_date', None)
        if not published:
            return False
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return now - published <= timedelta(hours=cls.BLINDSPOT_MAX_AGE_HOURS)

    # A candidate this similar to a story title (today's or a recent
    # issue's) is the same storyline, not a blindspot.
    BLINDSPOT_TOPIC_OVERLAP = 0.5
    BLINDSPOT_TODAY_OVERLAP = 0.4
    # Same storyline as a recent blindspot even when worded differently:
    # 09-29 "27% rise in 2027 military spending" and 09-30 "record 17.1
    # trillion rubles for its military in 2027" share russia/budget/2027/
    # military but only ~25% of their words.
    BLINDSPOT_SHARED_WORDS = 4
    # Words every blindspot text shares by construction — the "why it
    # matters outside the region" sentence — or that name no particular
    # event. They never count as evidence of the same storyline: 10-02's
    # "US sanctions Iran's rail and auto sectors" was dropped as a repeat
    # of 10-01's "China mobilization law" because both raised security
    # risks and could disrupt global trade, and the issue ran with no
    # blindspot.
    BLINDSPOT_FRAMING_WORDS = frozenset("""
        matters matter outside region regional regions because raises raise
        raising risks risk security global globally trade disrupt disrupts
        disruption could would might likely signals signal signalling
        signaling affect affects affecting forecasts forecast economic
        economy political politics international world western outlet
        outlets media covered coverage today pool reported reports report
        reporting according officials official government governments
        united states country countries nation nations national foreign
        policy week year years month wider broader beyond implications
        consequences stability pressure escalation tensions tension
        """.split())

    def _repeats_recent_blindspot(self, text: str) -> Optional[str]:
        words = content_words(text) - self.BLINDSPOT_FRAMING_WORDS
        for prior in self.recent_blindspots:
            shared = words & content_words(prior)
            if len(shared) >= self.BLINDSPOT_SHARED_WORDS:
                return prior
        return None

    def _blindspot_candidates(self, stories: List[AIAnalysis], articles: List[Article],
                              limit: int = 4,
                              exclude_urls: Optional[List[str]] = None) -> List[List[Article]]:
        """Events well covered outside Western media but absent from it —
        and not any of the issue's selected stories (excluded by cited URL
        AND by whole event cluster, so an uncited cluster member can't
        resurface the story as its own blindspot). Only fresh articles
        (BLINDSPOT_MAX_AGE_HOURS) take part.

        Also excluded: events only state media report (a blindspot must not
        become a megaphone for a government narrative — 09-20 and 09-25 were
        TASS-driven), and storylines the reader already has from today's
        stories or recent issues (09-13, 09-17, 09-21)."""
        now = datetime.now(timezone.utc)
        story_urls = set(exclude_urls or [])
        for s in stories:
            story_urls.update(s.sources or [])
        story_clusters = {getattr(a, 'cluster_id', None) for a in articles
                          if a.url in story_urls and getattr(a, 'cluster_id', None)}
        known_topics = [s.story_title for s in stories] + list(self.recent_topics)
        # Today's stories also by their whole event clusters' headlines and
        # first sentence: an event split across clusters must not come back
        # as today's blindspot (10-06 shadow: the Moscow drone strike was
        # story #2 AND the blindspot).
        today_texts = [s.story_title + " " + (s.why_important or "").split(". ")[0] for s in stories]
        today_texts += [a.title for a in articles if getattr(a, 'cluster_id', None) in story_clusters]
        events = defaultdict(list)
        for a in articles:
            cid = getattr(a, 'cluster_id', None)
            if (cid and cid not in story_clusters and a.url not in story_urls
                    and self._is_fresh(a, now) and not self._off_topic(a)):
                events[cid].append(a)
        # Western reports anywhere in the pool: a cluster can be non-Western
        # only because the embedding split one event (10-06 shadow: the Moscow
        # drone strike was offered as a blindspot while France 24 ran it).
        western_titles = [a.title for a in articles
                          if group_of(getattr(a, 'source_perspective', '')) not in NON_WESTERN_GROUPS
                          and group_of(getattr(a, 'source_perspective', '')) != 'intl_org']
        candidates = []
        for members in events.values():
            if len({m.source for m in members}) < 2:
                continue
            groups = {group_of(getattr(m, 'source_perspective', '')) for m in members}
            if not groups or not groups.issubset(NON_WESTERN_GROUPS):
                continue
            if all(self._is_state(m) for m in members):
                continue
            if any(overlap(m.title, topic) >= self.BLINDSPOT_TOPIC_OVERLAP
                   for m in members for topic in known_topics) \
                    or self._repeats_recent_blindspot(" ".join(m.title for m in members)):
                logger.info(f"Blindspot candidate skipped (storyline already covered): {members[0].title[:70]}")
                continue
            today = next((t for m in members for t in today_texts
                          if overlap(m.title, t, stem=True) >= self.BLINDSPOT_TODAY_OVERLAP), None)
            if today:
                logger.info(f"Blindspot candidate skipped (today's story: {today[:60]}): {members[0].title[:70]}")
                continue
            western = next((w for m in members for w in western_titles
                            if overlap(m.title, w, stem=True) >= self.BLINDSPOT_TOPIC_OVERLAP), None)
            if western:
                logger.info(f"Blindspot candidate skipped (a Western outlet ran it: {western[:60]}): "
                            f"{members[0].title[:70]}")
                continue
            covered = self._covered_storyline(members, stories)
            if covered:
                logger.info(f"Blindspot candidate skipped (our own storyline '{covered}'): {members[0].title[:70]}")
                continue
            candidates.append(members)
        # Independent corroboration first: distinct non-state outlets, then
        # weight (state outlets count half).
        candidates.sort(key=lambda ms: (
            -len({m.source for m in ms if not self._is_state(m)}),
            -sum((m.source_weight or 1.0) * (0.5 if self._is_state(m) else 1.0) for m in ms)))
        return candidates[:limit]

    def _covered_storyline(self, members: List[Article], stories: List[AIAnalysis]) -> Optional[str]:
        """The distinctive name tying a candidate to today's stories or to
        anything the last 5 issues covered, else None."""
        text = " ".join(f"{m.title} {(m.summary or '')[:300]}" for m in members)
        today = StorylineIndex([{"date": "today", "stories": [s.story_title for s in stories],
                                 "story_terms": [s.signal_terms for s in stories]}])
        for index, days in ((today, 1), (getattr(self, "storylines", None) or StorylineIndex([]), 5)):
            hit = index.match(text, days=days)
            if hit:
                return hit[1]
        return None

    @staticmethod
    def _is_state(article: Article) -> bool:
        return bool(getattr(article, 'state_affiliated', False)) or \
            group_of(getattr(article, 'source_perspective', '')) in STATE_GROUPS

    def _blindspot_link(self, members: List[Article], text: str) -> Article:
        """The article to link: a non-state outlet the text names, else any
        non-state member, else the first member."""
        non_state = [m for m in members if not self._is_state(m)]
        lowered = (text or "").lower()
        for m in non_state:
            names = {m.source.lower(), source_display_name(m.url).lower()}
            if any(n and n in lowered for n in names):
                return m
        return non_state[0] if non_state else members[0]

    def coverage_counts(self, story: AIAnalysis, articles: List[Article]) -> Tuple[Dict[str, int], int]:
        """(perspective group -> article count, distinct outlet count) for one
        story's event cluster. Pure computation — no API call — so every
        story can carry the coverage mini-bar for free."""
        members = self._story_articles(story, articles)
        counts: Dict[str, int] = defaultdict(int)
        for a in members:
            counts[group_of(getattr(a, 'source_perspective', 'western_mainstream'))] += 1
        return dict(counts), len({a.source for a in members})

    # ------------------------------------------------------------------
    # Grid construction
    # ------------------------------------------------------------------

    def build_grid(self, story: AIAnalysis, articles: List[Article],
                   all_stories: Optional[List[AIAnalysis]] = None,
                   exclude_urls: Optional[List[str]] = None) -> Optional[PerspectiveGrid]:
        """`exclude_urls`: articles already used elsewhere in the issue (quick
        hits) — their events are never offered as the blindspot."""
        members = self._story_articles(story, articles)
        if not members:
            return None

        groups = self._group_articles(members)
        counts = {g: len([a for a in members
                          if group_of(getattr(a, 'source_perspective', '')) == g])
                  for g in groups}
        grid = PerspectiveGrid(total_outlets=len({a.source for a in members}), counts=counts)

        blindspot_events = self._blindspot_candidates(all_stories or [story], articles,
                                                      exclude_urls=exclude_urls)

        if self.mock_mode:
            return self._mock_grid(grid, groups, blindspot_events)

        # A grid needs contrast: with one group there is nothing to compare,
        # but a computed blindspot may still be worth writing up.
        if len(groups) < 2 and not blindspot_events:
            logger.info("Perspective grid skipped: single perspective, no blindspot")
            return grid

        try:
            return self._build_grid_api(grid, groups, blindspot_events)
        except Exception as e:
            logger.error(f"Perspective extraction failed, shipping counts-only grid: {e}")
            return grid

    def _mock_grid(self, grid: PerspectiveGrid, groups: Dict[str, List[Article]],
                   blindspot_events: List[List[Article]]) -> PerspectiveGrid:
        for g, members in groups.items():
            grid.views.append(PerspectiveView(
                perspective=g,
                outlets=sorted({source_display_name(m.url) for m in members}),
                article_count=len(members),
                framing=f"(mock) How {label_of(g)} frames this story.",
                state_affiliated=g in STATE_GROUPS,
            ))
        if blindspot_events:
            members = blindspot_events[0]
            grid.blindspot = f"(mock) Barely covered outside its region: {members[0].title[:80]}"
            grid.blindspot_url = self._blindspot_link(members, "").url
            grid.blindspot_outlets = sorted({source_display_name(m.url) for m in members})
        return grid

    # With 80+ sources a big story can carry 20+ articles; the model only needs
    # a representative sample per group to name the angle, and quotes are
    # verified against exactly the excerpts shown, so the prompt is bounded
    # here. Only the Western row usually exceeds this (9-12 outlets on busy
    # days); the rendered counts and outlet lists still use the whole group.
    MAX_ARTICLES_PER_GROUP = 8

    @classmethod
    def _top_members(cls, members: List[Article]) -> List[Article]:
        """A representative sample: news outlets (mainstream/regional) before
        analysis and think tanks — a group's framing is how it REPORTS the
        event, not how its commentators discuss it — then by source weight,
        one article per outlet where possible."""
        def rank(a: Article):
            category = getattr(getattr(a, 'source_category', None), 'value',
                               str(getattr(a, 'source_category', '') or ''))
            news_first = 0 if category in ('mainstream', 'regional') else 1
            return (news_first, -(getattr(a, 'source_weight', 1.0) or 1.0), getattr(a, 'source', ''))
        ranked = sorted(members, key=rank)
        picked, seen_sources = [], set()
        for a in ranked:
            if a.source in seen_sources:
                continue
            seen_sources.add(a.source)
            picked.append(a)
            if len(picked) >= cls.MAX_ARTICLES_PER_GROUP:
                return picked
        for a in ranked:
            if len(picked) >= cls.MAX_ARTICLES_PER_GROUP:
                break
            if a not in picked:
                picked.append(a)
        return picked

    def _build_grid_api(self, grid: PerspectiveGrid, groups: Dict[str, List[Article]],
                        blindspot_events: List[List[Article]]) -> PerspectiveGrid:
        indexed: List[Article] = []
        sections = []
        for g in sorted(groups, key=lambda g: GROUP_ORDER.index(g) if g in GROUP_ORDER else 99):
            lines = [f"PERSPECTIVE GROUP: {g} ({label_of(g)})"]
            for a in self._top_members(groups[g]):
                idx = len(indexed)
                indexed.append(a)
                text = (getattr(a, 'full_content', None) or a.summary or "")[:EXCERPT_CHARS]
                lines.append(f"[{idx}] {a.source}: {a.title}\nText: {text}")
            sections.append("\n".join(lines))

        blindspot_section = ""
        if blindspot_events:
            lines = ["BLINDSPOT CANDIDATES (events covered ONLY outside Western media today):"]
            for members in blindspot_events:
                m = members[0]
                idx = len(indexed)
                indexed.append(m)
                outlets = ", ".join(sorted({x.source + (" [state]" if self._is_state(x) else "")
                                            for x in members}))
                summary = (getattr(m, 'full_content', None) or m.summary or "")[:240]
                lines.append(f"[{idx}] {m.title} (covered by: {outlets})\nText: {summary}")
            if self.recent_blindspots:
                lines.append("RECENT BLINDSPOTS (already shown to readers — never the same storyline):")
                lines.extend(f"- {b}" for b in self.recent_blindspots)
            blindspot_section = "\n" + "\n".join(lines) + "\n"

        prompt = (
            "You analyze how different parts of the world's media cover the same story. "
            "Below are articles about ONE event, grouped by media perspective.\n\n"
            + "\n\n".join(sections)
            + "\n" + blindspot_section +
            "\nFor EACH perspective group above, give:\n"
            "1. framing: ONE short sentence (max 20 words) naming this group's editorial "
            "angle in political terms: what it treats as the cause, whom it holds "
            "responsible, what it stresses compared with the other groups. "
            "Never describe writing style, tone, vividness, level of detail or imagery "
            "(\"vivid detail on smoke\", \"precise factual account\" are NOT framings). "
            "You only see short excerpts, so never claim a group \"omits\", \"ignores\" or "
            "\"downplays\" something unless another group's excerpt above reports it AND none of "
            "this group's excerpts mention it — otherwise describe what the group stresses.\n"
            "2. wire_copy: true if the group only runs agency/wire copy with no discernible "
            "angle of its own (then framing may be \"\"); otherwise false. Do not invent an "
            "angle to avoid saying true.\n"
            "3. quote: a VERBATIM quote of 8-30 words copied EXACTLY from one article's "
            "Text above, that shows the framing. It must be a complete sentence or "
            "self-contained clause starting with a capital letter, and it must carry a "
            "claim, an attribution or a number — never scene-setting (smoke, fires, "
            "sirens, weather). Copy the characters exactly — do not fix, trim inside, "
            "or paraphrase. If no such quote exists, use \"\".\n"
            "4. quote_article_index: the [index] of the article the quote is from.\n\n"
            + ("Also pick the single most significant blindspot candidate and write 1-2 plain "
               "sentences (max 40 words): what happened, then why it matters to a reader "
               "outside the region. Write it as neutral news in your own voice. Claims made "
               "only by state media ([state]) must be attributed (\"TASS reports\") and never "
               "adopted as your framing or as the reason it matters. Do NOT say who did or did "
               "not cover it and do not credit news agencies (\"Reuters reported\") — the page "
               "shows the outlets. Never pick a candidate from the same storyline as a recent "
               "blindspot listed above. Use the candidate's index. It must be an EVENT — a "
               "decision, an attack, casualties, a vote, an arrest, a deal or new data — never "
               "a statement, speech, warning or opinion on its own. Only "
               "political, economic, security or humanitarian events qualify: never sports, "
               "entertainment, celebrities or lifestyle — if no candidate qualifies, "
               "return \"blindspot\": null.\n\n"
               if blindspot_section else "")
            + "Plain English, active voice, no jargon.\n"
            "Return ONLY this JSON object, no markdown fences:\n"
            '{"views": [{"group": "western", "framing": "...", "wire_copy": false, "quote": "...", '
            '"quote_article_index": 0}], '
            + ('"blindspot": {"text": "...", "article_index": 5}}'
               if blindspot_section else '"blindspot": null}')
        )

        cost_estimate = ai_cost_controller.estimate_cost(len(prompt), "analysis")
        budget = ai_cost_controller.check_budget_allowance(cost_estimate.estimated_cost)
        if not budget['allowed']:
            logger.warning(f"Perspective extraction blocked by budget: {budget['reason']}")
            return grid

        ai_archiver.archive_ai_request(
            prompt=prompt,
            articles_summary=f"Perspective extraction over {len(indexed)} articles",
            cluster_index=1,
            main_article_title="Perspective grid"
        )

        data = None
        stop = None
        # Two attempts, plus a third only when the second was cut off by the
        # token budget: DeepSeek's reasoning occasionally eats the whole
        # budget (2026-10-03: stop_reason=length after 345 chars of text) and
        # an identical retry normally succeeds — the budget itself stays as
        # configured, OpenRouter's output cap for the model is unknown.
        for attempt in (1, 2, 3):
            if attempt == 3 and stop != "length":
                break
            start = time.time()
            # Same budget as the issue call: adaptive thinking spends from
            # max_tokens, and a 4000 cap left no room for the JSON on busy days.
            response = self.client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=Config.AI_MAX_TOKENS or 16000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_response_text(response)
            in_tok, out_tok, cost = response_tokens_and_cost(response, prompt, text)
            ai_cost_controller.record_cost(cost, in_tok + out_tok, "perspective_extraction")
            self.meta["grid_cost_usd"] = round(float(self.meta.get("grid_cost_usd", 0.0)) + cost, 5)
            self.meta["grid_attempts"] = attempt
            served = getattr(response, 'served_model', None) or getattr(response, 'model', None)
            if isinstance(served, str) and served:
                self.meta["grid_served_model"] = served
            stop = getattr(response, 'stop_reason', None)
            logger.info(f"Perspective extraction (attempt {attempt}): {in_tok}+{out_tok} tokens, "
                        f"${cost:.4f}, {time.time() - start:.1f}s, stop_reason={stop}")
            data = self._parse_json_object(text)
            if data:
                break
            again = attempt == 1 or (attempt == 2 and stop == "length")
            logger.warning(f"Perspective response unusable (stop_reason={stop}, "
                           f"{len(text)} chars of text) — "
                           + ("retrying" if again else "shipping counts-only grid"))
        if not data:
            return grid

        for view_data in data.get("views", []):
            if not isinstance(view_data, dict):
                continue
            g = view_data.get("group", "")
            if g not in groups:
                continue
            members = groups[g]
            quote = (view_data.get("quote") or "").strip().strip('"')
            q_idx = view_data.get("quote_article_index")
            quote_outlet, quote_url = "", ""
            if quote and isinstance(q_idx, int) and 0 <= q_idx < len(indexed):
                src_article = indexed[q_idx]
                if self._verify_quote(quote, src_article):
                    quote_outlet, quote_url = source_display_name(src_article.url), src_article.url
                else:
                    logger.warning(f"Quote failed verbatim check, dropping: {quote[:60]}")
                    quote = ""
            else:
                quote = ""
            framing = (view_data.get("framing") or "").strip()
            wire = view_data.get("wire_copy") is True or framing.lower().startswith(WIRE_COPY_PREFIX)
            grid.views.append(PerspectiveView(
                perspective=g,
                outlets=sorted({source_display_name(m.url) for m in members}),
                article_count=grid.counts.get(g, len(members)),
                framing="" if wire else framing,
                quote=quote,
                quote_outlet=quote_outlet,
                quote_url=quote_url,
                state_affiliated=g in STATE_GROUPS,
                wire_copy=wire,
            ))

        bs = data.get("blindspot")
        if isinstance(bs, dict) and bs.get("text"):
            b_idx = bs.get("article_index")
            chosen = None
            if isinstance(b_idx, int) and 0 <= b_idx < len(indexed):
                chosen = next((ms for ms in blindspot_events if indexed[b_idx] in ms), None)
            repeat = self._repeats_recent_blindspot(str(bs["text"])) if chosen else None
            if repeat:
                logger.warning(f"Blindspot dropped (repeats a recent blindspot): {str(bs['text'])[:80]} ~ {repeat[:60]}")
            elif chosen:
                text = self._clean_blindspot_text(str(bs["text"]))
                grid.blindspot = text
                grid.blindspot_url = self._blindspot_link(chosen, text).url
                grid.blindspot_outlets = sorted({source_display_name(m.url) for m in chosen})
            else:
                logger.warning("Blindspot dropped: article_index does not point at a candidate")

        ai_archiver.archive_ai_response(response_text=text, analysis=None,
                                        cluster_index=1, cost=cost, tokens=in_tok + out_tok)
        return grid

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _COVERAGE_CLAUSE = re.compile(
        r"[^.;]*\b(no|not a single|none of the)\s+western\s+(outlet|media|news)[^.;]*[.;]?\s*", re.I)

    @classmethod
    def _clean_blindspot_text(cls, text: str) -> str:
        """Strip "no Western outlet covered it" clauses — the rendered
        outlet line says that from data; in the model's voice it became the
        same boilerplate sentence every single day."""
        cleaned = cls._COVERAGE_CLAUSE.sub("", text).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return cleaned or text.strip()

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[‘’]", "'", text)
        text = re.sub(r"[“”]", '"', text)
        return re.sub(r"\s+", " ", text).strip()

    def _verify_quote(self, quote: str, article: Article) -> bool:
        """A quote must appear verbatim (modulo whitespace/smart quotes) in the
        text we actually showed the model — and must not date a past event in
        the future (10-04 quoted a source typo: "struck the Pivnichnyi Bridge
        in Kyiv on 14 October")."""
        haystack = self._normalize(
            f"{article.title} {(getattr(article, 'full_content', None) or article.summary or '')[:EXCERPT_CHARS + 100]}"
        )
        if self._normalize(quote) not in haystack:
            return False
        if self._future_dated_past_event(quote):
            logger.warning(f"Quote dropped (past event dated in the future — source typo?): {quote[:80]}")
            return False
        return True

    _MONTHS = {m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"], start=1)}
    _PAST_VERB = re.compile(r"\b(struck|hit|killed|attacked|launched|said|was|were|seized|"
                            r"captured|fired|arrested|died|destroyed|damaged|signed|voted|won)\b", re.I)

    @classmethod
    def _future_dated_past_event(cls, quote: str, today: Optional[datetime] = None) -> bool:
        today = (today or datetime.now(timezone.utc)).date()
        if not cls._PAST_VERB.search(quote):
            return False
        months = "|".join(cls._MONTHS)
        for m in re.finditer(rf"\b(\d{{1,2}})\s+({months})\b|\b({months})\s+(\d{{1,2}})\b", quote, re.I):
            day = int(m.group(1) or m.group(4))
            month = cls._MONTHS[(m.group(2) or m.group(3)).lower()]
            try:
                when = today.replace(month=month, day=day)
            except ValueError:
                continue
            if 1 < (when - today).days < 180:
                return True
        return False

    @staticmethod
    def _parse_json_object(text: str) -> Optional[dict]:
        """First complete JSON object in the response that carries "views".

        Models sometimes emit the object twice, or follow it with prose; the
        old greedy {.*} span then covered both and json.loads failed with
        "Extra data" (2026-10-03 shipped a counts-only grid that way). A
        raw_decode from each "{" parses exactly one object and ignores
        whatever trails it.
        """
        cleaned = re.sub(r'```(?:json)?\s*', '', text.strip()).strip('`').strip()
        decoder = json.JSONDecoder()
        first_error = None
        for m in re.finditer(r'\{', cleaned):
            try:
                obj, _ = decoder.raw_decode(cleaned, m.start())
            except json.JSONDecodeError as e:
                if first_error is None:
                    first_error = e
                continue
            # Only the grid object counts: a truncated response still parses
            # at an inner {"group": …} view, and returning that would skip
            # the retry and ship an empty grid.
            if isinstance(obj, dict) and ("views" in obj or "blindspot" in obj):
                return obj
        if first_error is None:
            logger.error("Perspective response contained no JSON object")
        else:
            logger.error(f"Perspective response JSON error: {first_error}")
        return None
