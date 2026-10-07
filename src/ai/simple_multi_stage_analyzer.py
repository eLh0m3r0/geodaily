"""
Simplified Multi-Stage AI Analyzer with SINGLE API call.

This module provides transparent multi-stage analysis but with only ONE API call
to minimize costs while maintaining decision transparency.
"""

import asyncio
import json
import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..models import Article, AIAnalysis, ContentType, QuickHit, BigNumber, IssueContent, DevelopingItem
from ..config import Config
from ..archiver.ai_data_archiver import ai_archiver
from .cost_controller import ai_cost_controller
from .api_utils import extract_response_text, response_tokens_and_cost, load_recent_newsletter_titles
from .llm_client import build_llm_client, ai_credentials_present
from .editorial import (format_history_block, history_texts, is_off_brand, is_repeat,
                        load_issue_history, numbers_in, overlap, reads_choppy, sentence_stats,
                        to_sentence_case, headline_overclaims, earlier_year, content_words)
from .storylines import StorylineIndex, label_for

logger = logging.getLogger(__name__)


class SimplifiedMultiStageAnalyzer:
    """
    Simplified multi-stage analyzer that does all analysis in a SINGLE API call.
    This maintains transparency while minimizing costs.
    """
    
    def __init__(self):
        # Poznamka: drive tu byla primo kontrola ANTHROPIC_API_KEY. Po prechodu
        # na konfigurovatelneho poskytovatele by takova kontrola poslala celou
        # analyzu do mock rezimu a vydani by vyslo s vymyslenym obsahem.
        self.mock_mode = Config.DRY_RUN or not ai_credentials_present()
        # What the last issues already told the reader (stories, quick hits,
        # big number, blindspot) — steers the prompt and the post-filters.
        self.history = []
        if Config.ENABLE_NEWSLETTER_HISTORY:
            try:
                self.history = load_issue_history(Config.NEWSLETTERS_DIR, days=Config.NEWSLETTER_HISTORY_DAYS)
            except Exception as e:
                logger.warning(f"Issue history unavailable: {e}")
        # Running storylines (names that identify an event across days): a
        # story, quick hit or blindspot that continues one is recognised even
        # when every word of the copy changed.
        self.storylines = StorylineIndex([])
        if Config.ENABLE_NEWSLETTER_HISTORY:
            try:
                self.storylines = StorylineIndex(load_issue_history(Config.NEWSLETTERS_DIR, days=5))
            except Exception as e:
                logger.warning(f"Storyline history unavailable: {e}")
        self.meta: Dict[str, Any] = {}

        if not self.mock_mode:
            try:
                self.client = build_llm_client()
                logger.info(f"Initialized simplified multi-stage analyzer "
                            f"({Config.AI_PROVIDER}, model {Config.AI_MODEL})")
            except Exception as e:
                logger.error(f"Failed to initialize AI client: {e}")
                self.mock_mode = True
                self.client = None
        else:
            self.mock_mode = True
            self.client = None
            logger.info("Using mock mode for simplified multi-stage analyzer")
    
    async def analyze_articles_single_call(self, articles: List[Article], target_stories: int = 1) -> IssueContent:
        """
        Produce one issue's content in a SINGLE API call: the big story
        (plus optional secondary stories), 6-8 quick hits, and the big number.

        Args:
            articles: List of articles to analyze
            target_stories: Number of deep-analysis stories (1 = big story only)

        Returns:
            IssueContent (stories may be empty on failure — caller decides)
        """
        print(f"🔍 Starting simplified multi-stage analysis of {len(articles)} articles")
        logger.info(f"Simplified analysis started: {len(articles)} articles → {target_stories} deep stories + quick hits")
        self.target_stories = target_stories

        start_time = time.time()

        if self.mock_mode:
            issue = self._create_mock_issue(articles, target_stories)
            self._apply_editorial_rules(issue, articles)
            issue.meta = {"provider": "mock", "model": "mock", "served_model": "mock"}
            return issue

        # Event-aware pre-filter: keep corroborated, perspective-diverse events
        sorted_articles = self._prefilter_articles(articles, cap=60)

        # Build the comprehensive prompt for single API call
        # No reserve story in the prompt: a fourth story plus extra quick hits
        # pushed DeepSeek's reasoning past 32k tokens (18-minute analysis in
        # the 10-06 shadow runs). A demotion may leave 2 stories; DEVELOPING
        # carries the running story.
        prompt = self._build_single_call_prompt(sorted_articles, target_stories)

        # Budget check before spending API tokens
        cost_estimate = ai_cost_controller.estimate_cost(len(prompt), "analysis")
        budget_check = ai_cost_controller.check_budget_allowance(cost_estimate.estimated_cost)
        if not budget_check['allowed']:
            logger.error(f"AI analysis blocked by budget: {budget_check['reason']} "
                         f"(daily ${budget_check['current_daily_cost']:.2f}/${budget_check['daily_limit']:.2f})")
            return IssueContent()

        try:
            # Archive the request
            ai_archiver.archive_ai_request(
                prompt=prompt,
                articles_summary=f"Single-call analysis of {len(sorted_articles)} articles",
                cluster_index=0,
                main_article_title="Multi-stage comprehensive analysis"
            )

            # SINGLE API CALL - does all stages internally
            print(f"📡 Making single API call for comprehensive analysis...")
            response = self.client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=self._analysis_budget(),
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = extract_response_text(response)
            input_tokens, output_tokens, cost = response_tokens_and_cost(response, prompt, response_text)
            served_model = self._served_model(response)

            # Parse the comprehensive response
            issue = self._parse_issue_response(response_text, sorted_articles)

            # One corrective retry if the model returned malformed JSON —
            # far better than silently publishing mock content.
            if not issue.stories:
                logger.warning("First response was not parseable JSON, retrying with corrective message")
                retry_response = self.client.messages.create(
                    model=Config.AI_MODEL,
                    max_tokens=self._analysis_budget(),
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response_text or "(empty)"},
                        {"role": "user", "content": "Your previous reply was not valid JSON in the requested "
                                                    "format. Return ONLY the JSON object in the exact format "
                                                    "requested — no markdown fences, no commentary."}
                    ]
                )
                retry_text = extract_response_text(retry_response)
                r_in, r_out, r_cost = response_tokens_and_cost(retry_response, prompt, retry_text)
                input_tokens += r_in
                output_tokens += r_out
                cost += r_cost
                issue = self._parse_issue_response(retry_text, sorted_articles)
                if issue.stories:
                    response_text = retry_text

            # Readability gate: if the copy came back too dense, run one
            # "simplify" rewrite pass before publishing.
            if issue.stories:
                issue.stories, gate_in, gate_out, gate_cost = self._apply_readability_gate(issue.stories)
                input_tokens += gate_in
                output_tokens += gate_out
                cost += gate_cost
                self._apply_editorial_rules(issue, sorted_articles)

            total_tokens = input_tokens + output_tokens
            ai_cost_controller.record_cost(cost, total_tokens, "single_call_analysis")

            # Archive the response (one entry per analysis)
            if issue.stories:
                for i, analysis in enumerate(issue.stories):
                    ai_archiver.archive_ai_response(
                        response_text=response_text,
                        analysis=analysis,  # Single analysis instead of list
                        cluster_index=i,
                        cost=cost / len(issue.stories),
                        tokens=total_tokens // len(issue.stories)
                    )
            else:
                # Archive empty response
                ai_archiver.archive_ai_response(
                    response_text=response_text,
                    analysis=None,
                    cluster_index=0,
                    cost=cost,
                    tokens=total_tokens
                )

            elapsed = time.time() - start_time

            print(f"✅ Analysis complete in {elapsed:.1f}s")
            print(f"   • Input: {len(sorted_articles)} articles")
            print(f"   • Output: {len(issue.stories)} stories + {len(issue.quick_hits)} quick hits")
            print(f"   • Tokens: {input_tokens:,} in / {output_tokens:,} out")
            print(f"   • Cost: ${cost:.4f}")

            logger.info(f"Single-call analysis completed: {len(issue.stories)} stories, "
                        f"{len(issue.quick_hits)} quick hits, cost: ${cost:.4f}, "
                        f"provider {Config.AI_PROVIDER}, model {served_model or Config.AI_MODEL}")
            self.meta.update({
                "provider": Config.AI_PROVIDER,
                "model": Config.AI_MODEL,
                "served_model": served_model or Config.AI_MODEL,
                "analysis_input_tokens": input_tokens,
                "analysis_output_tokens": output_tokens,
                "analysis_cost_usd": round(cost, 5),
                "analysis_seconds": round(elapsed, 1),
            })
            issue.meta = dict(self.meta)

            if not issue.stories:
                # Fail loudly rather than publish generic mock text as analysis.
                logger.error("AI analysis produced no valid stories after retry — failing this run")
            return issue

        except Exception as e:
            logger.error(f"Single-call analysis failed: {e}")
            print(f"❌ Analysis failed: {e}")
            # Do NOT fall back to mock content in production — a missed issue is
            # better than a published newsletter full of fabricated analysis.
            return IssueContent()
    
    def _prefilter_articles(self, articles: List[Article], cap: int = 60) -> List[Article]:
        """Event-aware pre-filter to keep the prompt affordable.

        Ranks event clusters by corroboration x perspective diversity x source
        weight, takes up to 4 articles per event (preferring distinct
        perspectives), then fills remaining slots with the highest-relevance
        unclustered articles.
        """
        if len(articles) <= cap:
            return articles

        from collections import defaultdict
        events = defaultdict(list)
        singles = []
        for a in articles:
            if getattr(a, 'cluster_id', None):
                events[a.cluster_id].append(a)
            else:
                singles.append(a)

        def event_score(members):
            perspectives = {getattr(m, 'source_perspective', '') for m in members}
            weight_sum = sum(m.source_weight or 1.0 for m in members)
            return weight_sum * (1 + 0.5 * (len(perspectives) - 1))

        selected: List[Article] = []
        for members in sorted(events.values(), key=event_score, reverse=True):
            if len(selected) >= cap:
                break
            chosen, seen_p = [], set()
            for m in sorted(members, key=lambda m: -(m.source_weight or 1.0)):
                p = getattr(m, 'source_perspective', '')
                if p not in seen_p:
                    chosen.append(m)
                    seen_p.add(p)
                if len(chosen) == 4:
                    break
            selected.extend(chosen[:max(0, cap - len(selected))])

        singles.sort(key=lambda a: -(getattr(a, 'relevance_score', 0) or 0))
        selected.extend(singles[:max(0, cap - len(selected))])
        print(f"📊 Pre-filtered {len(articles)} articles to {len(selected)} "
              f"({len(events)} events considered)")
        return selected

    def _build_single_call_prompt(self, articles: List[Article], target_stories: int) -> str:
        """Build comprehensive prompt for single API call."""

        # Prepare article summaries
        article_texts = []
        for i, article in enumerate(articles):
            # Use full_content if available, otherwise summary
            content = getattr(article, 'full_content', None) or article.summary
            # Enough context for real analytical judgment without blowing the budget
            if len(content) > 600:
                content = content[:597] + "..."

            weight = getattr(article, 'source_weight', 1.0) or 1.0
            perspective = getattr(article, 'source_perspective', 'western_mainstream')
            state_label = ", state-affiliated" if getattr(article, 'state_affiliated', False) else ""
            event = getattr(article, 'cluster_id', None)
            event_line = f"Event: {event}\n" if event else ""
            # Safely format article info avoiding f-string issues with braces in content
            article_info = """
[{}] {}
Source: {} (perspective: {}{}, editorial weight {:.1f})
{}Content: {}
URL: {}
""".format(i, article.title, article.source, perspective, state_label, weight, event_line, content, article.url)
            article_texts.append(article_info)

        articles_section = "\n".join(article_texts)

        # Recent coverage context so the briefing doesn't repeat itself day to
        # day: stories AND quick hits, big number and blindspot (the 2026-09
        # review found quick hits and big numbers rerun on consecutive days
        # because only story titles were shown here).
        history_block = ""
        if Config.ENABLE_NEWSLETTER_HISTORY:
            history_block = format_history_block(self.history)
            if not history_block:
                titles = load_recent_newsletter_titles()
                if titles:
                    history_block = ("\nRECENT NEWSLETTER COVERAGE (do NOT re-select these topics unless "
                                     "there is a genuinely new development):\n" + titles + "\n")
            history_block += self._running_storylines_block()

        # Use string formatting to avoid f-string issues with article content containing braces
        template = """You write a daily world-news brief for smart readers who are NOT foreign-policy professionals. Each issue has: THE BIG STORY (the one thing worth full attention today), MORE TOP STORIES (the next most consequential distinct events, covered more briefly), ALSO TODAY (a quick world roundup so the reader feels caught up), and THE BIG NUMBER (one striking figure from today's news).
{}
ARTICLES TO ANALYZE:
{}

Build today's issue from the above articles. Deep stories to select: {}.

WRITING STYLE (strict — this is the product):
- Plain English, active voice, US grade 8-9 reading level — reached with plain WORDS, not by chopping sentences.
- Sentences of 12-20 words with a natural rhythm, one idea each. Never write fragments or strings of 4-7-word sentences ("Kyiv is short. It needs more. Factories take months.") — that reads as a telegram, not journalism. Never open consecutive sentences with "Also".
- Headlines in sentence case: capitalize only the first word and proper nouns ("Trump rejects Iran's truce offer", never "Trump Rejects Iran's Truce Offer"). A headline must be literally true to the body: no "record", "first" or superlative the body does not support.
- A headline claims only what is confirmed. If an action is planned, threatened, claimed by one side or not yet confirmed, the headline says so ("plans to", "says", "claims", "threatens", "agrees to discuss") — never "Pakistan and Turkey send troops" when the body says no deployment is confirmed.
- Your own voice states facts only. Judgments ("shows Israel is isolated", "unusually high turnout") must be attributed to whoever makes them, or cut.
- Banned jargon: "inflection point", "strategic calculus", "paradigm", "escalatory dynamics", "operational tempo", "recalibrate", "posture", "leverage" (as a verb), "signal" (as a verb), "underscore". Say what happened in real words.
- Concrete beats abstract: "Iran said it will stop all Gulf oil exports" beats "Tehran signaled export disruption".
- Direct and conversational is good. Vague is not.

SOURCE RULES:
- Articles marked with the same "Event:" id cover the SAME event — treat them as one story and list ALL supporting indices in article_indices.
- article_indices must come from DIFFERENT outlets whenever possible. Never build a story on two articles from the same outlet if any alternative exists.
- Every outlet is a lens, not an oracle. State-affiliated sources are marked — useful for what a government wants amplified, but NEVER the sole basis of a fact anywhere in the issue: not in a story, not in what_overlooked, not in a quick hit or the big number. If only state media report something, attribute it in the text ("TASS reports ...") or leave it out. For a quick hit or the big number, point article_index at a non-state article whenever one covers the event. Reflect single-perspective sourcing in a lower credibility_score.
- The "editorial weight" (0.7-1.3) reflects past reliability — a mild tiebreaker, not a ranking rule. A well-corroborated wire story beats a single-source think-tank essay.

Return this EXACT JSON structure — a single JSON object, no other text:

{{
  "email_subject": "Inbox subject line for the issue, max 45 CHARACTERS. Concrete and curiosity-driven, but NOT a copy of the big story title — say the sharpest fact or stake in fewer words. No emoji, no date, no ALL CAPS.",
  "preheader": "The snippet shown next to the subject in inboxes, max 85 characters. One sentence that CONTINUES the subject with new information — never repeats it.",
  "big_stories": [
    {{
      "article_indices": [0, 3, 5],
      "story_title": "Clear, specific, sentence-case title a non-expert understands — no clichés like 'tensions rise', no jargon",
      "content_type": "breaking_news or analysis or trend",
      "region": "europe or middle_east or indo_pacific or americas or africa or central_asia or global",
      "actor_type": "state or non_state or international_org or mixed",
      "event_type": "diplomatic or military or economic or informational_cyber or humanitarian or political",
      "why_important": "2-3 sentences: what happened and why a smart reader should care. Max 60 words.",
      "what_overlooked": "1-2 sentences that ADD something why_important does not say: a missing fact, a claim nobody has verified (and who makes it), a consequence most coverage skips, or context that changes the meaning. Never restate why_important. Max 35 words.",
      "prediction": "One concrete, checkable development in the next 72 hours and what it would tell us. It appears under the heading 'What to watch', so do NOT start with 'Watch'. Max 25 words.",
      "signal_terms": ["2-4 proper nouns that identify THIS event the way a prediction market or news search would name it: countries, leaders, places, organizations (e.g. Iran, Strait of Hormuz). Never generic words like US, war, strikes, talks."],
      "impact_score": 8,
      "urgency_score": 7,
      "scope_score": 8,
      "novelty_score": 6,
      "credibility_score": 9,
      "confidence": 0.85,
      "selection_reasoning": "Why this story over the other candidates"
    }}
  ],
  "quick_hits": [
    {{
      "text": "One sentence, max 25 words, concrete facts: who did what, with a number or name in it.",
      "region": "europe or middle_east or indo_pacific or americas or africa or central_asia or global",
      "article_index": 7
    }}
  ],
  "big_number": {{
    "value": "35%",
    "context": "One sentence: what this number is and why it is striking. Max 25 words.",
    "article_index": 12
  }}
}}

CONTENT RULES:
1. big_stories: exactly the number of deep stories requested, ranked by geopolitical consequence — most consequential FIRST. Each must cover a DIFFERENT event. The first is THE story of the day — the one a busy reader must know; give it your fullest why_important. For stories after the first, keep why_important to max 50 words. The ranking and the scores must agree: no story may have a higher impact_score than a story ranked above it.
2. quick_hits: 8 items, never about a story or storyline the reader already got (listed above), each about a DIFFERENT event than ALL of the big_stories and than each other — never restate any selected story as a quick hit, not even from a different angle — and never a rerun of a quick hit from recent issues (a follow-up is fine only when it states the new fact). Every quick hit must involve a government, an international organization, an armed group or a cross-border consequence, and must NAME the actor ("Japan's foreign ministry protested…", never "Leaders visited…" or "Officials said…"); science prizes, domestic health alerts and markets news without a state actor do not qualify. Together they must span at least 4 distinct regions — this is the reader's "I'm caught up on the world" section, so favor geographic spread (Africa, Latin America and Asia are chronically under-covered; include them when the material exists).
3. big_number: one genuinely striking, verifiable figure taken from one of the articles, about something NOT already covered by a story or quick hit in this issue (a number from the big story repeated as the big number wastes the slot) and not used in recent issues. The figure must describe TODAY's event itself — never background from an earlier year ("6% vote share in 2024") or a past disaster's toll. If no such number exists, use null.
4. NO sports, entertainment, celebrity or human-interest items, and NO single-country domestic crime, court cases, executions, campus scandals, accidents or space launches ANYWHERE in the issue — not as a story, not as a quick hit, not as the big number — unless the event has direct geopolitical consequences (state action, sanctions, boycotts, diplomatic fallout, cross-border impact). An athlete retiring, a film winning awards, a botched execution in one US state or a university fraternity case is never news for this brief; a world-roundup item must matter beyond its own country's borders.
5. All scores integers 1-10 — use the whole scale. impact_score 9-10: changes the course of a war, a great-power relationship or the world economy (a few times a month, not daily); 7-8: a major national or regional development; 5-6: notable but contained. article_index values must reference the list above.
6. Return ONLY the raw JSON object — no markdown, no explanations, no code blocks.

FIELD DEFINITIONS:
- content_type: breaking_news=a discrete event of the last 48 hours; analysis=the news IS a report, study, investigation, leaked document or official statistic; trend=a multi-week pattern made newsworthy today
- region: europe=EU/NATO/Russia; middle_east=MENA/GCC/Iran/Turkey; indo_pacific=China/Japan/Koreas/SE Asia/India; americas=US/LatAm; africa=SSA/Horn/Sahel; central_asia=ex-Soviet stans/Afghanistan; global=multi-region simultaneous
- actor_type: state=governments+militaries; non_state=armed groups/corps/NGOs; international_org=UN/NATO/EU/WTO; mixed=combination
- event_type: diplomatic=summits/treaties/negotiations; military=conflict/deployments/weapons; economic=trade/energy/sanctions; informational_cyber=disinformation/hacking; humanitarian=refugees/famine/disaster; political=elections/coups/protests"""

        return template.format(history_block, articles_section, target_stories)
    
    def _running_storylines_block(self) -> str:
        groups = (getattr(self, "storylines", None) or StorylineIndex([])).running_storylines(days=3)
        if not groups:
            return ""
        lines = []
        for g in groups:
            names = ", ".join(label_for(t) for t in sorted(g["terms"], key=len)[:4])
            dates = ", ".join(sorted(g["dates"]))
            lines.append(f"- {names} (big story on {dates}; latest: {g['latest']})")
        return ("\nSTORIES THE READER ALREADY FOLLOWED as big stories in the last issues "
                "(give big-story slots to fresh events first; one of these may lead only if today's "
                "development is the biggest news of the day):\n" + "\n".join(lines) + "\n")

    @staticmethod
    def _analysis_budget() -> int:
        return max(Config.AI_MAX_TOKENS or 16000, getattr(Config, "ANALYSIS_MAX_TOKENS", 32000))

    @staticmethod
    def _served_model(response) -> str:
        """The model the provider actually ran (OpenRouter reports it), if known."""
        for attr in ("served_model", "model"):
            value = getattr(response, attr, None)
            if isinstance(value, str) and value:
                return value
        return ""

    @staticmethod
    def _copy_texts(analyses: List[AIAnalysis]) -> List[str]:
        return [t for a in analyses for t in (a.why_important, a.what_overlooked, a.prediction)]

    def _apply_readability_gate(self, analyses: List[AIAnalysis]) -> Tuple[List[AIAnalysis], int, int, float]:
        """Rewrite the generated copy in plainer language when it tests too dense.

        Returns (analyses, extra_input_tokens, extra_output_tokens, extra_cost).
        One rewrite attempt only. The rewrite is ACCEPTED only when it lowers
        the grade without chopping the copy into fragments — in 2026-09 every
        accepted rewrite turned ~13-word sentences into ~9-word telegrams
        ("Kyiv is short of these interceptors. They are the only reliable
        defense."), which is worse than a slightly dense original.
        """
        from .readability import combined_grade

        texts = self._copy_texts(analyses)
        grade = combined_grade(texts)
        avg_len, frag = sentence_stats(texts)
        self.meta["readability"] = {"grade": grade, "avg_sentence_words": avg_len,
                                    "fragment_share": frag, "rewrite": "not_needed"}
        if grade is None:
            return analyses, 0, 0, 0.0
        if grade <= Config.READABILITY_MAX_GRADE:
            logger.info(f"Readability gate passed: grade {grade:.1f} <= {Config.READABILITY_MAX_GRADE} "
                        f"({avg_len} words/sentence)")
            return analyses, 0, 0, 0.0

        logger.warning(f"Readability gate triggered: grade {grade:.1f} > {Config.READABILITY_MAX_GRADE} "
                       f"({avg_len} words/sentence), requesting rewrite")
        payload = [
            {
                "index": i,
                "why_important": a.why_important,
                "what_overlooked": a.what_overlooked,
                "prediction": a.prediction,
            }
            for i, a in enumerate(analyses)
        ]
        rewrite_prompt = (
            "These newsletter passages test at US reading grade {:.1f}; the target is 8-9 "
            "for smart non-expert readers. Edit them like a senior copy editor.\n"
            "How: swap long or technical WORDS for plain ones, unpack jargon, and split only "
            "sentences over 25 words. Keep sentences 12-20 words with a natural rhythm. Do NOT "
            "chop the text into short fragments — merge any sentence under 8 words into its "
            "neighbour. Keep every fact, name, number and attribution exactly; add nothing. "
            "Active voice. The prediction must not start with 'Watch'. Word limits: "
            "why_important max 60, what_overlooked max 35, prediction max 25.\n\n{}\n\n"
            "Return ONLY a JSON array of objects with fields: index, why_important, "
            "what_overlooked, prediction. No markdown, no commentary."
        ).format(grade, json.dumps(payload, ensure_ascii=False, indent=1))

        try:
            response = self.client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=Config.AI_MAX_TOKENS or 16000,
                messages=[{"role": "user", "content": rewrite_prompt}],
            )
            text = extract_response_text(response)
            in_tok, out_tok, cost = response_tokens_and_cost(response, rewrite_prompt, text)

            import re
            cleaned = re.sub(r'```(?:json)?\s*', '', text.strip()).strip('`').strip()
            match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if not match:
                logger.warning("Readability rewrite returned no JSON — keeping original copy")
                self.meta["readability"]["rewrite"] = "failed"
                return analyses, in_tok, out_tok, cost

            import copy
            candidate = copy.deepcopy(analyses)
            for item in json.loads(match.group()):
                idx = item.get("index")
                if isinstance(idx, int) and 0 <= idx < len(candidate):
                    candidate[idx].why_important = item.get("why_important") or candidate[idx].why_important
                    candidate[idx].what_overlooked = item.get("what_overlooked") or candidate[idx].what_overlooked
                    candidate[idx].prediction = item.get("prediction") or candidate[idx].prediction

            new_texts = self._copy_texts(candidate)
            new_grade = combined_grade(new_texts)
            new_avg, new_frag = sentence_stats(new_texts)
            improved = new_grade is not None and new_grade < grade
            choppy = reads_choppy(new_texts) and not reads_choppy(texts)
            lost_numbers = numbers_in(" ".join(texts)) - numbers_in(" ".join(new_texts))
            self.meta["readability"].update({
                "rewrite_grade": new_grade, "rewrite_avg_sentence_words": new_avg,
                "rewrite_fragment_share": new_frag,
            })
            if improved and not choppy and not lost_numbers:
                logger.info(f"Readability rewrite applied: grade {grade:.1f} -> {new_grade:.1f}, "
                            f"{avg_len} -> {new_avg} words/sentence")
                self.meta["readability"]["rewrite"] = "applied"
                return candidate, in_tok, out_tok, cost

            reason = ("no grade improvement" if not improved else
                      "copy turned choppy" if choppy else
                      f"figures dropped: {sorted(lost_numbers)}")
            logger.warning(f"Readability rewrite rejected ({reason}): grade {grade:.1f} -> {new_grade}, "
                           f"{avg_len} -> {new_avg} words/sentence — keeping original copy")
            self.meta["readability"]["rewrite"] = f"rejected: {reason}"
            return analyses, in_tok, out_tok, cost
        except Exception as e:
            logger.warning(f"Readability rewrite failed, keeping original copy: {e}")
            self.meta["readability"]["rewrite"] = "failed"
            return analyses, 0, 0, 0.0

    # ------------------------------------------------------------------
    # Editorial guardrails (post-generation)
    # ------------------------------------------------------------------

    def _apply_editorial_rules(self, issue: IssueContent, articles: List[Article]) -> None:
        """Enforce what the prompt asks but models don't always deliver:
        sentence-case headlines, no quick hit or big number rerun from recent
        issues, a big number that isn't already in the issue, and non-state
        links for quick hits whenever the event has a non-state source."""
        # Headlines: one house style (sentence case). Case evidence comes from
        # running text only — feed titles are often Title Case themselves.
        corpus = " ".join(
            [f"{s.why_important} {s.what_overlooked} {s.prediction}" for s in issue.stories]
            + [h.text for h in issue.quick_hits]
            + [(getattr(a, 'full_content', None) or a.summary or "")[:600] for a in articles])
        for story in issue.stories:
            fixed = to_sentence_case(story.story_title, corpus)
            if fixed != story.story_title:
                logger.info(f"Headline normalized to sentence case: {story.story_title!r} -> {fixed!r}")
                story.story_title = fixed

        by_url = {a.url: a for a in articles}

        # Quick hits and the big number: the link must be about the text.
        # The model's article_index is sometimes off (10-06 shadow runs linked
        # a 'super El Nino' quick hit to a pre-COP fossil-fuel article twice).
        for item in list(issue.quick_hits) + ([issue.big_number] if issue.big_number else []):
            text = getattr(item, 'text', None) or f"{getattr(item, 'value', '')} {getattr(item, 'context', '')}"
            better = self._better_link(text, by_url.get(item.url), articles)
            if better is not None:
                self._note(f"Link fixed ({by_url[item.url].source if item.url in by_url else 'unknown'}"
                           f" -> {better.source}): {text[:70]}")
                item.url = better.url

        # Quick hits: link a non-state outlet when the same event has one
        for hit in issue.quick_hits:
            art = by_url.get(hit.url)
            if art is None or not getattr(art, 'state_affiliated', False):
                continue
            cid = getattr(art, 'cluster_id', None)
            alt = next((a for a in articles
                        if cid and getattr(a, 'cluster_id', None) == cid
                        and not getattr(a, 'state_affiliated', False)), None)
            if alt:
                logger.info(f"Quick hit relinked from state outlet {art.source} to {alt.source}")
                hit.url = alt.url

        # Quick hits: no reruns of what recent issues already said
        prior_hits = history_texts(self.history, "quick_hits", "big_number", "blindspot")
        kept = []
        for hit in issue.quick_hits:
            repeat = is_repeat(hit.text, prior_hits)
            if repeat:
                self._note(f"Quick hit dropped (rerun of a recent issue): {hit.text[:70]}")
                continue
            kept.append(hit)
        issue.quick_hits = kept

        # Quick hits: domestic crime / entertainment fare is not world news,
        # however new the "new fact" is (see editorial.is_off_brand)
        kept = []
        for hit in issue.quick_hits:
            marker = is_off_brand(hit.text)
            if marker:
                self._note(f"Quick hit dropped (off-brand: {marker}): {hit.text[:70]}")
                continue
            kept.append(hit)
        issue.quick_hits = kept

        self._apply_storyline_rules(issue)

        # Big number: must add something the issue doesn't already say
        bn = issue.big_number
        if bn:
            issue_texts = ([f"{s.story_title} {s.why_important} {s.what_overlooked}" for s in issue.stories]
                           + [h.text for h in issue.quick_hits])
            bn_text = f"{bn.value} {bn.context}"
            bn_figures = numbers_in(bn.value)
            reason = None
            story_urls = {u for s in issue.stories for u in (s.sources or [])}
            story_clusters = {getattr(by_url[u], 'cluster_id', None) for u in story_urls if u in by_url} - {None}
            bn_article = by_url.get(bn.url)
            if bn_figures and any(bn_figures & numbers_in(t) for t in issue_texts):
                reason = "figure already in the issue"
            elif bn.url and (bn.url in story_urls or
                             (bn_article and getattr(bn_article, 'cluster_id', None) in story_clusters)):
                reason = "same event as a story"
            elif any(overlap(bn_text, t) >= 0.6 for t in issue_texts):
                reason = "restates a story or quick hit"
            elif is_repeat(bn_text, history_texts(self.history, "big_number", "quick_hits")):
                reason = "rerun of a recent issue"
            elif is_off_brand(bn_text):
                reason = f"off-brand: {is_off_brand(bn_text)}"
            elif earlier_year(bn.context):
                reason = f"background figure from {earlier_year(bn.context)}, not today's event"
            elif not re.search(r"\d", bn.value or ""):
                reason = "not a figure"
            elif (getattr(self, "storylines", None) or StorylineIndex([])).match(bn_text, days=3):
                reason = "part of a running storyline"
            if reason:
                self._note(f"Big number dropped ({reason}): {bn.value} — {bn.context[:60]}")
                issue.big_number = None

        # Ranking sanity: order is editorial, but flag a contradiction
        for i in range(1, len(issue.stories)):
            if issue.stories[i].impact_score > issue.stories[0].impact_score:
                logger.warning(f"Story #{i + 1} scores higher impact ({issue.stories[i].impact_score}) "
                               f"than the lead ({issue.stories[0].impact_score}) — lead choice may be off")

        # Headlines that state as fact what the body calls unconfirmed —
        # surfaced in the issue's quality report (meta.quality_flags)
        flags = self.meta.setdefault("quality_flags", [])
        for story in issue.stories:
            if headline_overclaims(story.story_title, story.why_important, story.what_overlooked):
                logger.warning(f"Headline may overstate an unconfirmed claim: {story.story_title}")
                flags.append(f"headline_overclaims: {story.story_title}")

    # Max one big story may continue a storyline that was a big story in the
    # last two issues; max DEVELOPING lines per issue.
    MAX_CONTINUING_STORIES = 1
    MAX_DEVELOPING = 3
    MAX_QUICK_HITS = 8

    LINK_MISMATCH = 0.2   # share of the item's words its linked article has
    LINK_BETTER = 0.4     # a replacement must clearly be about the item

    @staticmethod
    def _link_score(words, article) -> float:
        if not words or article is None:
            return 0.0
        art_words = content_words(f"{article.title} {(article.summary or '')[:400]}", stem=True)
        return len(words & art_words) / len(words)

    def _better_link(self, text, current, articles):
        """An article that matches `text` clearly better than its current
        link does, or None when the link is fine or nothing fits better."""
        words = content_words(text, stem=True)
        if len(words) < 4:
            return None
        current_score = self._link_score(words, current)
        if current is not None and current_score >= self.LINK_MISMATCH:
            return None
        best, best_score = None, 0.0
        for a in articles:
            score = self._link_score(words, a)
            # prefer non-state outlets on ties
            if score > best_score or (score == best_score and best is not None
                                      and getattr(best, 'state_affiliated', False)
                                      and not getattr(a, 'state_affiliated', False)):
                best, best_score = a, score
        if best is not None and best is not current and best_score >= self.LINK_BETTER \
                and best_score >= current_score + 0.2:
            return best
        return None

    def _note(self, action: str) -> None:
        """Record an editorial decision in the issue's meta (the JSON logger
        does not carry module loggers, so shadow runs could not show them)."""
        logger.info(action)
        self.meta.setdefault("editorial_actions", []).append(action[:200])

    def _apply_storyline_rules(self, issue: IssueContent) -> None:
        """Running stories get one DEVELOPING line, not a story or quick-hit
        slot. 2026-09-30..10-06 ran flydubai and the French school protests
        four days in a row and Tigray as a big story in 4 of 6 issues — each
        time "with a new fact", so the repeat filters let it through."""
        idx = getattr(self, "storylines", None) or StorylineIndex([])
        developing: List[DevelopingItem] = []
        seen_labels = set()

        def add(item: DevelopingItem, front: bool = False) -> bool:
            key = item.storyline.lower()
            if key in seen_labels or len(developing) >= self.MAX_DEVELOPING:
                return False
            seen_labels.add(key)
            developing.insert(0, item) if front else developing.append(item)
            return True

        # 1) Big stories continuing a storyline that was a big story lately
        continuing = []
        for i, story in enumerate(issue.stories):
            m = idx.match(story.story_title, story.signal_terms, days=2, kinds={"story"})
            if m:
                continuing.append((i, m[1]))
        demotable = max(0, len(issue.stories) - 2)  # an issue keeps >= 2 stories
        # Only the LEAD may continue a running storyline (the prompt allows it
        # only when it is the day's most consequential news); a continuing
        # story further down the ranking is a running story, not news.
        extra = [c for c in continuing if c[0] != 0]
        if continuing and continuing[0][0] == 0:
            extra = continuing[self.MAX_CONTINUING_STORIES:]
        for i, term in sorted(extra, reverse=True)[:demotable]:
            story = issue.stories.pop(i)
            self._note(f"Story demoted to DEVELOPING (running storyline '{term}'): {story.story_title}")
            add(DevelopingItem(storyline=label_for(term), text=story.story_title.rstrip(".") + ".",
                               region=story.region, url=(story.sources or [""])[0]), front=True)

        # 2) The model's own DEVELOPING items: one per storyline, new facts only
        prior = history_texts(self._storyline_history(), "developing", "quick_hits")
        for item in issue.developing:
            if is_repeat(item.text, prior):
                self._note(f"Developing item dropped (no new fact): {item.text[:70]}")
                continue
            add(item)

        # 3) Quick hits that belong to today's stories or a running storyline
        today = StorylineIndex([{"date": "today", "stories": [s.story_title for s in issue.stories],
                                 "story_terms": [s.signal_terms for s in issue.stories]}])
        kept = []
        for hit in issue.quick_hits:
            m = idx.match(hit.text, days=3, kinds={"story", "quick_hit", "developing", "blindspot"})
            if m:
                moved = add(DevelopingItem(storyline=label_for(m[1]), text=hit.text,
                                           region=hit.region, url=hit.url))
                self._note(f"Quick hit {'moved to DEVELOPING' if moved else 'dropped'} "
                           f"(running storyline '{m[1]}'): {hit.text[:70]}")
                continue
            if today.match(hit.text, days=1, kinds={"story"}):
                self._note(f"Quick hit dropped (same storyline as a story today): {hit.text[:70]}")
                continue
            kept.append(hit)
        # 4) The reserve story: published only if a demotion made room;
        # otherwise it leads ALSO TODAY as a one-sentence item.
        target = getattr(self, "target_stories", len(issue.stories)) or len(issue.stories)
        while len(issue.stories) > max(1, target):
            reserve = issue.stories.pop()
            first = re.split(r"(?<=[.!?])\s+", (reserve.why_important or "").strip())[0]
            text = first if len(first.split()) >= 6 else reserve.story_title.rstrip(".") + "."
            kept.insert(0, QuickHit(text=text, region=reserve.region,
                                    url=(reserve.sources or [""])[0]))
            self._note(f"Reserve story moved to ALSO TODAY: {reserve.story_title}")
        issue.quick_hits = kept[:self.MAX_QUICK_HITS]
        issue.developing = developing

    def _storyline_history(self) -> List[dict]:
        """Raw history behind the storyline index (for text-level repeat checks)."""
        return getattr(getattr(self, "storylines", None), "history", []) or self.history

    def _story_from_data(self, data: Dict[str, Any], articles: List[Article]) -> AIAnalysis:
        """Build one AIAnalysis from a parsed story dict."""
        from ..newsletter.source_display import registrable_domain

        # Get source URLs from article indices, never citing the same
        # outlet twice under one story (repeated domains read as bias).
        source_urls = []
        seen_domains = set()
        for idx in data.get('article_indices', []):
            if isinstance(idx, int) and 0 <= idx < len(articles):
                url = articles[idx].url
                domain = registrable_domain(url)
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)
                source_urls.append(url)

        content_type_str = data.get('content_type', 'analysis')
        content_type = ContentType.BREAKING_NEWS if 'breaking' in content_type_str else \
                      ContentType.TREND if 'trend' in content_type_str else \
                      ContentType.ANALYSIS

        analysis = AIAnalysis(
            story_title=data.get('story_title', 'Untitled Story'),
            why_important=data.get('why_important', 'Important geopolitical development'),
            what_overlooked=data.get('what_overlooked', 'Broader strategic implications'),
            prediction=data.get('prediction', 'Situation likely to evolve'),
            impact_score=int(data.get('impact_score', 7)),
            urgency_score=int(data.get('urgency_score', 5)),
            scope_score=int(data.get('scope_score', 6)),
            novelty_score=int(data.get('novelty_score', 5)),
            credibility_score=int(data.get('credibility_score', 7)),
            impact_dimension_score=int(data.get('impact_dimension_score', data.get('impact_score', 7))),
            content_type=content_type,
            sources=source_urls or ['No source'],
            confidence=float(data.get('confidence', 0.7)),
            region=data.get('region', 'global'),
            actor_type=data.get('actor_type', 'state'),
            event_type=data.get('event_type', 'political'),
        )
        raw_terms = data.get('signal_terms') or []
        if isinstance(raw_terms, list):
            analysis.signal_terms = [str(t).strip() for t in raw_terms
                                     if isinstance(t, str) and len(t.strip()) >= 3][:4]
        reasoning = data.get('selection_reasoning', 'Selected based on impact')
        logger.info(f"Selected story: {analysis.story_title} - {reasoning}")
        return analysis

    def _article_url(self, idx, articles: List[Article]) -> str:
        if isinstance(idx, int) and 0 <= idx < len(articles):
            return articles[idx].url
        return ""

    @staticmethod
    def _content_words(text: str) -> set:
        import re
        return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 3}

    def _filter_hits_against_stories(self, quick_hits: List[QuickHit],
                                     stories: List[AIAnalysis],
                                     articles: List[Article]) -> List[QuickHit]:
        """Belt-and-suspenders dedup: the prompt forbids restating a selected
        story as a quick hit, but models drift — so also drop any hit that
        (a) links a URL cited by a story, (b) links into a story's event
        cluster, or (c) shares most of its content words with a story title."""
        if not stories or not quick_hits:
            return quick_hits
        story_urls = set()
        for s in stories:
            story_urls.update(s.sources or [])
        url_cluster = {a.url: getattr(a, 'cluster_id', None) for a in articles}
        story_clusters = {url_cluster.get(u) for u in story_urls} - {None}
        title_words = [self._content_words(s.story_title) for s in stories]

        kept = []
        for hit in quick_hits:
            if hit.url and (hit.url in story_urls or url_cluster.get(hit.url) in story_clusters):
                logger.info(f"Quick hit dropped (same event as a story): {hit.text[:70]}")
                continue
            hit_words = self._content_words(hit.text)
            overlap = False
            for tw in title_words:
                base = min(len(tw), len(hit_words))
                if base >= 3 and len(tw & hit_words) / base >= 0.6:
                    overlap = True
                    break
            if overlap:
                logger.info(f"Quick hit dropped (restates a story title): {hit.text[:70]}")
                continue
            kept.append(hit)
        return kept

    def _parse_issue_response(self, response_text: str, articles: List[Article]) -> IssueContent:
        """Parse the issue-format response (object with big_stories/quick_hits/
        big_number). Falls back to the legacy array-of-stories format."""
        try:
            logger.info(f"API Response (first 1000 chars): {response_text[:1000]}...")

            import re
            cleaned = response_text.strip()
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip('`').strip()

            # Legacy fallback: a bare JSON array of stories
            obj_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            arr_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if not obj_match or (arr_match and arr_match.start() < obj_match.start()):
                stories = self._parse_single_response(response_text, articles)
                return IssueContent(stories=stories)

            try:
                data = json.loads(obj_match.group())
            except json.JSONDecodeError as je:
                logger.error(f"JSON decode error: {je}")
                return IssueContent()

            stories = [self._story_from_data(s, articles)
                       for s in data.get('big_stories', []) if isinstance(s, dict)]

            quick_hits = []
            seen_texts = set()
            for hit in data.get('quick_hits', []):
                if not isinstance(hit, dict):
                    continue
                text = (hit.get('text') or '').strip()
                if not text or text.lower() in seen_texts:
                    continue
                seen_texts.add(text.lower())
                quick_hits.append(QuickHit(
                    text=text,
                    region=hit.get('region', 'global'),
                    url=self._article_url(hit.get('article_index'), articles),
                ))
            quick_hits = self._filter_hits_against_stories(quick_hits, stories, articles)

            developing = []
            for item in data.get('developing', []) or []:
                if not isinstance(item, dict):
                    continue
                text = (item.get('text') or '').strip()
                label = (item.get('storyline') or '').strip()
                if text and label:
                    developing.append(DevelopingItem(
                        storyline=label[:40], text=text, region=item.get('region', 'global'),
                        url=self._article_url(item.get('article_index'), articles)))

            big_number = None
            bn = data.get('big_number')
            if isinstance(bn, dict) and bn.get('value') and bn.get('context'):
                big_number = BigNumber(
                    value=str(bn['value']).strip(),
                    context=str(bn['context']).strip(),
                    url=self._article_url(bn.get('article_index'), articles),
                )

            email_subject = str(data.get('email_subject') or "").strip().strip('"')[:60]
            preheader = str(data.get('preheader') or "").strip().strip('"')[:110]

            return IssueContent(stories=stories, quick_hits=quick_hits, big_number=big_number,
                                developing=developing,
                                email_subject=email_subject, preheader=preheader)

        except Exception as e:
            logger.error(f"Failed to parse issue response: {e}", exc_info=True)
            logger.error(f"Response text was: {response_text[:1000] if response_text else 'None'}")
            return IssueContent()

    def _parse_single_response(self, response_text: str, articles: List[Article]) -> List[AIAnalysis]:
        """Parse the legacy array-format response into AIAnalysis objects."""
        try:
            import re
            cleaned = response_text.strip()
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip('`').strip()
            json_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if not json_match:
                logger.error(f"No JSON array found in response. Full response: {cleaned[:500]}")
                return []

            try:
                analyses_data = json.loads(json_match.group())
            except json.JSONDecodeError as je:
                logger.error(f"JSON decode error: {je}")
                return []

            if not isinstance(analyses_data, list):
                logger.error(f"Expected list, got {type(analyses_data)}")
                return []

            return [self._story_from_data(d, articles) for d in analyses_data if isinstance(d, dict)]

        except Exception as e:
            logger.error(f"Failed to parse response: {e}", exc_info=True)
            return []
    
    def _create_mock_issue(self, articles: List[Article], target_stories: int = 1) -> IssueContent:
        """Mock issue in the new format for DRY_RUN and tests.

        Mirrors real selection: one story per DISTINCT event cluster, and
        quick hits run through the same dedup filter as production."""
        n = max(1, min(3, target_stories))
        story_articles, seen_clusters, leftovers = [], set(), []
        for a in articles:
            cid = getattr(a, 'cluster_id', None)
            if len(story_articles) < n and (cid is None or cid not in seen_clusters):
                story_articles.append(a)
                if cid:
                    seen_clusters.add(cid)
            else:
                leftovers.append(a)
        stories = self._create_mock_analyses(story_articles)
        regions = ["europe", "middle_east", "indo_pacific", "americas", "africa", "central_asia", "global"]
        quick_hits = [
            QuickHit(
                text=(a.title if len(a.title.split()) <= 25 else " ".join(a.title.split()[:25]) + "..."),
                region=regions[i % len(regions)],
                url=a.url,
            )
            for i, a in enumerate(leftovers[:10])
        ]
        quick_hits = self._filter_hits_against_stories(quick_hits, stories, articles)[:8]
        big_number = None
        if len(leftovers) > 10:
            big_number = BigNumber(
                value="61",
                context="Sources now feeding this brief across 14 global perspectives (mock).",
                url=leftovers[10].url,
            )
        title_words = (stories[0].story_title.split() if stories else ["World", "brief"])
        return IssueContent(stories=stories, quick_hits=quick_hits, big_number=big_number,
                            email_subject=" ".join(title_words[:6])[:45],
                            preheader="Plus a world roundup and one number worth knowing (mock).")

    def _create_mock_analyses(self, articles: List[Article]) -> List[AIAnalysis]:
        """Create BETTER mock analyses as fallback."""
        logger.warning("Using improved mock analyses as fallback")
        analyses = []
        
        # Different templates for variety
        templates = [
            {
                'why': "This development signals a major shift in regional power dynamics that could reshape international relations",
                'what': "The second-order effects on neighboring states and global supply chains",
                'pred': "Expect escalating tensions and diplomatic realignment in coming weeks"
            },
            {
                'why': "This economic development has immediate implications for global markets and strategic resource allocation",
                'what': "The underlying structural changes that mainstream media tends to overlook",
                'pred': "Watch for policy responses from major powers within days"
            },
            {
                'why': "This diplomatic move represents a calculated strategic gambit with far-reaching consequences",
                'what': "The historical context and long-term strategic calculations behind this decision",
                'pred': "Anticipate countermoves from rival powers and regional realignment"
            },
            {
                'why': "This security development threatens to upset the established balance of power in the region",
                'what': "The military capabilities gap and deterrence implications",
                'pred': "Increased military posturing and alliance strengthening likely"
            }
        ]
        
        for i, article in enumerate(articles[:4]):
            template = templates[i % len(templates)]
            content_type = ContentType.BREAKING_NEWS if i == 0 else ContentType.ANALYSIS
            
            # Generate more varied scores based on source and position
            base_score = 8 - i  # Higher scores for earlier articles
            
            analysis = AIAnalysis(
                story_title=article.title[:60] if len(article.title) > 60 else article.title,
                why_important=template['why'],
                what_overlooked=template['what'],
                prediction=template['pred'],
                impact_score=max(5, base_score),
                urgency_score=max(4, base_score - 1),
                scope_score=max(5, base_score - 1),
                novelty_score=max(4, base_score - 2),
                credibility_score=7 if article.source_category.value in ['think_tank', 'analysis'] else 6,
                impact_dimension_score=max(5, base_score),
                content_type=content_type,
                sources=[article.url],
                confidence=0.75
            )
            analyses.append(analysis)
        
        return analyses