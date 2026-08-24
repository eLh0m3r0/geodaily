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
from typing import Dict, List, Optional, Tuple

from ..models import Article, AIAnalysis, PerspectiveGrid, PerspectiveView
from ..config import Config
from ..perspectives import group_of, label_of, STATE_GROUPS, NON_WESTERN_GROUPS, GROUP_ORDER
from ..archiver.ai_data_archiver import ai_archiver
from .cost_controller import ai_cost_controller
from .api_utils import extract_response_text, response_tokens_and_cost

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

MAX_ARTICLES_PER_GROUP = 3
EXCERPT_CHARS = 450


class PerspectiveAnalyzer:
    """Builds the perspective grid for the big story in one API call."""

    def __init__(self):
        self.mock_mode = Config.DRY_RUN or not Config.ANTHROPIC_API_KEY or Anthropic is None
        self.client = None
        if not self.mock_mode:
            try:
                self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
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
        # Stable order: cited articles first, then by source weight
        members.sort(key=lambda a: (a.url not in source_urls, -(a.source_weight or 1.0)))
        return members

    def _group_articles(self, members: List[Article]) -> Dict[str, List[Article]]:
        groups = defaultdict(list)
        for a in members:
            g = group_of(getattr(a, 'source_perspective', 'western_mainstream'))
            if len(groups[g]) < MAX_ARTICLES_PER_GROUP:
                groups[g].append(a)
        return dict(groups)

    def _blindspot_candidates(self, story: AIAnalysis, articles: List[Article],
                              limit: int = 2) -> List[List[Article]]:
        """Events well covered outside Western media but absent from it
        (and not the big story itself)."""
        story_urls = set(story.sources or [])
        events = defaultdict(list)
        for a in articles:
            if getattr(a, 'cluster_id', None) and a.url not in story_urls:
                events[a.cluster_id].append(a)
        candidates = []
        for members in events.values():
            if len(members) < 2:
                continue
            groups = {group_of(getattr(m, 'source_perspective', '')) for m in members}
            if groups and groups.issubset(NON_WESTERN_GROUPS):
                candidates.append(members)
        candidates.sort(key=lambda ms: -sum(m.source_weight or 1.0 for m in ms))
        return candidates[:limit]

    # ------------------------------------------------------------------
    # Grid construction
    # ------------------------------------------------------------------

    def build_grid(self, story: AIAnalysis, articles: List[Article]) -> Optional[PerspectiveGrid]:
        members = self._story_articles(story, articles)
        if not members:
            return None

        groups = self._group_articles(members)
        counts = {g: len([a for a in members
                          if group_of(getattr(a, 'source_perspective', '')) == g])
                  for g in groups}
        grid = PerspectiveGrid(total_outlets=len({a.source for a in members}), counts=counts)

        blindspot_events = self._blindspot_candidates(story, articles)

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
                outlets=sorted({m.source for m in members}),
                article_count=len(members),
                framing=f"(mock) How {label_of(g)} frames this story.",
                state_affiliated=g in STATE_GROUPS,
            ))
        if blindspot_events:
            first = blindspot_events[0][0]
            grid.blindspot = f"(mock) Barely covered outside its region: {first.title[:80]}"
            grid.blindspot_url = first.url
        return grid

    def _build_grid_api(self, grid: PerspectiveGrid, groups: Dict[str, List[Article]],
                        blindspot_events: List[List[Article]]) -> PerspectiveGrid:
        indexed: List[Article] = []
        sections = []
        for g in sorted(groups, key=lambda g: GROUP_ORDER.index(g) if g in GROUP_ORDER else 99):
            lines = [f"PERSPECTIVE GROUP: {g} ({label_of(g)})"]
            for a in groups[g]:
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
                outlets = ", ".join(sorted({x.source for x in members}))
                lines.append(f"[{idx}] {m.title} (covered by: {outlets})")
            blindspot_section = "\n" + "\n".join(lines) + "\n"

        prompt = (
            "You analyze how different parts of the world's media cover the same story. "
            "Below are articles about ONE event, grouped by media perspective.\n\n"
            + "\n\n".join(sections)
            + "\n" + blindspot_section +
            "\nFor EACH perspective group above, give:\n"
            "1. framing: ONE short sentence (max 20 words) describing what this group's "
            "coverage emphasizes — the angle, not a summary of the event.\n"
            "2. quote: a VERBATIM quote of 8-30 words copied EXACTLY from one article's "
            "Text above, that shows the framing. Copy the characters exactly — do not fix, "
            "trim inside, or paraphrase. If no clean quote exists, use \"\".\n"
            "3. quote_article_index: the [index] of the article the quote is from.\n\n"
            + ("Also pick the single most significant blindspot candidate and write 1-2 plain "
               "sentences (max 35 words) on what it is and why the gap matters. Use the "
               "candidate's index.\n\n" if blindspot_section else "")
            + "Plain English, active voice, no jargon.\n"
            "Return ONLY this JSON object, no markdown fences:\n"
            '{"views": [{"group": "western", "framing": "...", "quote": "...", '
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

        start = time.time()
        response = self.client.messages.create(
            model=Config.AI_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = extract_response_text(response)
        in_tok, out_tok, cost = response_tokens_and_cost(response, prompt, text)
        ai_cost_controller.record_cost(cost, in_tok + out_tok, "perspective_extraction")
        logger.info(f"Perspective extraction: {in_tok}+{out_tok} tokens, ${cost:.4f}, "
                    f"{time.time() - start:.1f}s")

        data = self._parse_json_object(text)
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
                    quote_outlet, quote_url = src_article.source, src_article.url
                else:
                    logger.warning(f"Quote failed verbatim check, dropping: {quote[:60]}")
                    quote = ""
            else:
                quote = ""
            grid.views.append(PerspectiveView(
                perspective=g,
                outlets=sorted({m.source for m in members}),
                article_count=grid.counts.get(g, len(members)),
                framing=(view_data.get("framing") or "").strip(),
                quote=quote,
                quote_outlet=quote_outlet,
                quote_url=quote_url,
                state_affiliated=g in STATE_GROUPS,
            ))

        bs = data.get("blindspot")
        if isinstance(bs, dict) and bs.get("text"):
            grid.blindspot = str(bs["text"]).strip()
            b_idx = bs.get("article_index")
            if isinstance(b_idx, int) and 0 <= b_idx < len(indexed):
                grid.blindspot_url = indexed[b_idx].url

        ai_archiver.archive_ai_response(response_text=text, analysis=None,
                                        cluster_index=1, cost=cost, tokens=in_tok + out_tok)
        return grid

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[‘’]", "'", text)
        text = re.sub(r"[“”]", '"', text)
        return re.sub(r"\s+", " ", text).strip()

    def _verify_quote(self, quote: str, article: Article) -> bool:
        """A quote must appear verbatim (modulo whitespace/smart quotes) in the
        text we actually showed the model."""
        haystack = self._normalize(
            f"{article.title} {(getattr(article, 'full_content', None) or article.summary or '')[:EXCERPT_CHARS + 100]}"
        )
        return self._normalize(quote) in haystack

    @staticmethod
    def _parse_json_object(text: str) -> Optional[dict]:
        cleaned = re.sub(r'```(?:json)?\s*', '', text.strip()).strip('`').strip()
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if not match:
            logger.error("Perspective response contained no JSON object")
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.error(f"Perspective response JSON error: {e}")
            return None
