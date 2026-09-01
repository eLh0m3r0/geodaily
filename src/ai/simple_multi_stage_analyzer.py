"""
Simplified Multi-Stage AI Analyzer with SINGLE API call.

This module provides transparent multi-stage analysis but with only ONE API call
to minimize costs while maintaining decision transparency.
"""

import asyncio
import json
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..models import Article, AIAnalysis, ContentType, QuickHit, BigNumber, IssueContent
from ..config import Config
from ..archiver.ai_data_archiver import ai_archiver
from .cost_controller import ai_cost_controller
from .api_utils import extract_response_text, response_tokens_and_cost, load_recent_newsletter_titles

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
except ImportError:
    logger.warning("Anthropic library not installed, using mock mode")
    Anthropic = None


class SimplifiedMultiStageAnalyzer:
    """
    Simplified multi-stage analyzer that does all analysis in a SINGLE API call.
    This maintains transparency while minimizing costs.
    """
    
    def __init__(self):
        self.mock_mode = Config.DRY_RUN or not Config.ANTHROPIC_API_KEY
        
        if not self.mock_mode and Anthropic:
            try:
                self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
                logger.info("Initialized simplified multi-stage analyzer with Claude API")
            except Exception as e:
                logger.error(f"Failed to initialize Claude client: {e}")
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

        start_time = time.time()

        if self.mock_mode:
            return self._create_mock_issue(articles, target_stories)

        # Event-aware pre-filter: keep corroborated, perspective-diverse events
        sorted_articles = self._prefilter_articles(articles, cap=60)

        # Build the comprehensive prompt for single API call
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
                max_tokens=Config.AI_MAX_TOKENS or 16000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = extract_response_text(response)
            input_tokens, output_tokens, cost = response_tokens_and_cost(response, prompt, response_text)

            # Parse the comprehensive response
            issue = self._parse_issue_response(response_text, sorted_articles)

            # One corrective retry if the model returned malformed JSON —
            # far better than silently publishing mock content.
            if not issue.stories:
                logger.warning("First response was not parseable JSON, retrying with corrective message")
                retry_response = self.client.messages.create(
                    model=Config.AI_MODEL,
                    max_tokens=Config.AI_MAX_TOKENS or 16000,
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
                        f"{len(issue.quick_hits)} quick hits, cost: ${cost:.4f}")

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

        # Recent coverage context so the briefing doesn't repeat itself day to day
        history_block = ""
        if Config.ENABLE_NEWSLETTER_HISTORY:
            history = load_recent_newsletter_titles()
            if history:
                history_block = ("\nRECENT NEWSLETTER COVERAGE (do NOT re-select these topics unless "
                                 "there is a genuinely new development):\n" + history + "\n")

        # Use string formatting to avoid f-string issues with article content containing braces
        template = """You write a daily world-news brief for smart readers who are NOT foreign-policy professionals. Each issue has: THE BIG STORY (the one thing worth full attention today), MORE TOP STORIES (the next most consequential distinct events, covered more briefly), ALSO TODAY (a quick world roundup so the reader feels caught up), and THE BIG NUMBER (one striking figure from today's news).
{}
ARTICLES TO ANALYZE:
{}

Build today's issue from the above articles. Deep stories to select: {}.

WRITING STYLE (strict — this is the product):
- Plain English, active voice, US grade 8-9 reading level.
- Short sentences: at most ~18 words each. One idea per sentence. Two or three short sentences beat one long one — never pack multiple clauses into a single sentence.
- Banned jargon: "inflection point", "strategic calculus", "paradigm", "escalatory dynamics", "operational tempo", "recalibrate", "posture", "leverage" (as a verb), "signal" (as a verb), "underscore". Say what happened in real words.
- Concrete beats abstract: "Iran said it will stop all Gulf oil exports" beats "Tehran signaled export disruption".
- Direct and conversational is good. Vague is not.

SOURCE RULES:
- Articles marked with the same "Event:" id cover the SAME event — treat them as one story and list ALL supporting indices in article_indices.
- article_indices must come from DIFFERENT outlets whenever possible. Never build a story on two articles from the same outlet if any alternative exists.
- Every outlet is a lens, not an oracle. State-affiliated sources are marked — useful for what a government wants amplified, but never the sole basis of a factual claim. Reflect single-perspective sourcing in a lower credibility_score and name the gap in what_overlooked.
- The "editorial weight" (0.7-1.3) reflects past reliability — a mild tiebreaker, not a ranking rule. A well-corroborated wire story beats a single-source think-tank essay.

Return this EXACT JSON structure — a single JSON object, no other text:

{{
  "email_subject": "Inbox subject line for the issue, max 45 CHARACTERS. Concrete and curiosity-driven, but NOT a copy of the big story title — say the sharpest fact or stake in fewer words. No emoji, no date, no ALL CAPS.",
  "preheader": "The snippet shown next to the subject in inboxes, max 85 characters. One sentence that CONTINUES the subject with new information — never repeats it.",
  "big_stories": [
    {{
      "article_indices": [0, 3, 5],
      "story_title": "Clear, specific title a non-expert understands — no clichés like 'tensions rise', no jargon",
      "content_type": "breaking_news or analysis or trend",
      "region": "europe or middle_east or indo_pacific or americas or africa or central_asia or global",
      "actor_type": "state or non_state or international_org or mixed",
      "event_type": "diplomatic or military or economic or informational_cyber or humanitarian or political",
      "why_important": "2-3 SHORT sentences: what happened and why a smart reader should care. Max 60 words.",
      "what_overlooked": "1-2 short sentences: what most coverage (or this story's own sources) misses. Max 35 words.",
      "prediction": "One concrete thing to watch in the next 72 hours. Max 25 words.",
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
1. big_stories: exactly the number of deep stories requested, ranked by geopolitical consequence — most consequential FIRST. Each must cover a DIFFERENT event. The first is THE story of the day — the one a busy reader must know; give it your fullest why_important. For stories after the first, keep why_important to max 50 words.
2. quick_hits: 6 to 8 items, each about a DIFFERENT event than ALL of the big_stories and than each other — never restate any selected story as a quick hit, not even from a different angle. Together they must span at least 4 distinct regions — this is the reader's "I'm caught up on the world" section, so favor geographic spread (Africa, Latin America and Asia are chronically under-covered; include them when the material exists).
3. big_number: one genuinely striking, verifiable figure taken from one of the articles. If no article contains a striking number, use null.
4. NO sports, entertainment, celebrity or human-interest items ANYWHERE in the issue — not as a story, not as a quick hit, not as the big number — unless the event has direct geopolitical consequences (state action, sanctions, boycotts, diplomatic fallout). An athlete retiring or a film winning awards is never news for this brief.
5. All scores integers 1-10. article_index values must reference the list above.
6. Return ONLY the raw JSON object — no markdown, no explanations, no code blocks.

FIELD DEFINITIONS:
- content_type: breaking_news=event requiring attention today; analysis=strategic examination; trend=multi-week pattern
- region: europe=EU/NATO/Russia; middle_east=MENA/GCC/Iran/Turkey; indo_pacific=China/Japan/Koreas/SE Asia/India; americas=US/LatAm; africa=SSA/Horn/Sahel; central_asia=ex-Soviet stans/Afghanistan; global=multi-region simultaneous
- actor_type: state=governments+militaries; non_state=armed groups/corps/NGOs; international_org=UN/NATO/EU/WTO; mixed=combination
- event_type: diplomatic=summits/treaties/negotiations; military=conflict/deployments/weapons; economic=trade/energy/sanctions; informational_cyber=disinformation/hacking; humanitarian=refugees/famine/disaster; political=elections/coups/protests"""

        return template.format(history_block, articles_section, target_stories)
    
    def _apply_readability_gate(self, analyses: List[AIAnalysis]) -> Tuple[List[AIAnalysis], int, int, float]:
        """Rewrite the generated copy in plainer language when it tests too dense.

        Returns (analyses, extra_input_tokens, extra_output_tokens, extra_cost).
        One rewrite attempt only; on any failure the original copy is kept.
        """
        from .readability import combined_grade

        texts = []
        for a in analyses:
            texts.extend([a.why_important, a.what_overlooked, a.prediction])
        grade = combined_grade(texts)
        if grade is None:
            return analyses, 0, 0, 0.0
        if grade <= Config.READABILITY_MAX_GRADE:
            logger.info(f"Readability gate passed: grade {grade:.1f} <= {Config.READABILITY_MAX_GRADE}")
            return analyses, 0, 0, 0.0

        logger.warning(f"Readability gate triggered: grade {grade:.1f} > {Config.READABILITY_MAX_GRADE}, requesting rewrite")
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
            "These newsletter passages test at US reading grade {:.1f}. Rewrite each field "
            "in plain English at grade 8-9 for smart non-expert readers.\n"
            "Rules: keep every fact, name and number. Short sentences (max ~18 words). "
            "Active voice. No jargon. Word limits: why_important max 60, what_overlooked "
            "max 35, prediction max 25.\n\n{}\n\n"
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
                return analyses, in_tok, out_tok, cost
            for item in json.loads(match.group()):
                idx = item.get("index")
                if isinstance(idx, int) and 0 <= idx < len(analyses):
                    analyses[idx].why_important = item.get("why_important") or analyses[idx].why_important
                    analyses[idx].what_overlooked = item.get("what_overlooked") or analyses[idx].what_overlooked
                    analyses[idx].prediction = item.get("prediction") or analyses[idx].prediction

            new_grade = combined_grade(
                [t for a in analyses for t in (a.why_important, a.what_overlooked, a.prediction)]
            )
            logger.info(f"Readability rewrite applied: grade {grade:.1f} -> {new_grade if new_grade is None else round(new_grade, 1)}")
            return analyses, in_tok, out_tok, cost
        except Exception as e:
            logger.warning(f"Readability rewrite failed, keeping original copy: {e}")
            return analyses, 0, 0, 0.0

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