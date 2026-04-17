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

from ..models import Article, AIAnalysis, ContentType
from ..config import Config
from ..archiver.ai_data_archiver import ai_archiver

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
    
    async def analyze_articles_single_call(self, articles: List[Article], target_stories: int = 4) -> List[AIAnalysis]:
        """
        Analyze articles with transparent multi-stage process in a SINGLE API call.
        
        Args:
            articles: List of articles to analyze
            target_stories: Number of final stories to select
            
        Returns:
            List of AIAnalysis objects
        """
        print(f"🔍 Starting simplified multi-stage analysis of {len(articles)} articles")
        logger.info(f"Simplified analysis started: {len(articles)} articles → {target_stories} stories")
        
        start_time = time.time()
        
        if self.mock_mode:
            return self._create_mock_analyses(articles[:target_stories])
        
        # Pre-filter articles to reduce token usage (take top 50 by relevance if available)
        if len(articles) > 50:
            # Sort by relevance score if available, otherwise by date
            sorted_articles = sorted(
                articles, 
                key=lambda a: getattr(a, 'relevance_score', 0) or 0,
                reverse=True
            )[:50]
            print(f"📊 Pre-filtered to top 50 articles for analysis")
        else:
            sorted_articles = articles
        
        # Build the comprehensive prompt for single API call
        prompt = self._build_single_call_prompt(sorted_articles, target_stories)
        
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
                max_tokens=Config.AI_MAX_TOKENS or 4000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Parse the comprehensive response
            analyses = self._parse_single_response(response_text, sorted_articles)
            
            # Calculate approximate cost (rough estimate)
            prompt_tokens = len(prompt.split()) * 1.3  # Rough token estimate
            response_tokens = len(response_text.split()) * 1.3
            total_tokens = int(prompt_tokens + response_tokens)
            estimated_cost = total_tokens * 0.00001  # Rough cost estimate
            
            # Archive the response (one entry per analysis)
            if analyses:
                for i, analysis in enumerate(analyses):
                    ai_archiver.archive_ai_response(
                        response_text=response_text,
                        analysis=analysis,  # Single analysis instead of list
                        cluster_index=i,
                        cost=estimated_cost / len(analyses) if len(analyses) > 0 else estimated_cost,
                        tokens=total_tokens // len(analyses) if len(analyses) > 0 else total_tokens
                    )
            else:
                # Archive empty response
                ai_archiver.archive_ai_response(
                    response_text=response_text,
                    analysis=None,
                    cluster_index=0,
                    cost=estimated_cost,
                    tokens=total_tokens
                )
            
            elapsed = time.time() - start_time
            
            print(f"✅ Analysis complete in {elapsed:.1f}s with 1 API call")
            print(f"   • Input: {len(sorted_articles)} articles")
            print(f"   • Output: {len(analyses)} stories")
            print(f"   • Tokens: ~{total_tokens:,}")
            print(f"   • Cost: ~${estimated_cost:.4f}")
            
            logger.info(f"Single-call analysis completed: {len(analyses)} stories, cost: ${estimated_cost:.4f}")
            
            return analyses
            
        except Exception as e:
            logger.error(f"Single-call analysis failed: {e}")
            print(f"❌ Analysis failed: {e}")
            return self._create_mock_analyses(sorted_articles[:target_stories])
    
    def _build_single_call_prompt(self, articles: List[Article], target_stories: int) -> str:
        """Build comprehensive prompt for single API call."""
        
        # Prepare article summaries
        article_texts = []
        for i, article in enumerate(articles):
            # Use full_content if available, otherwise summary
            content = getattr(article, 'full_content', None) or article.summary
            # Limit content length to save tokens
            if len(content) > 300:
                content = content[:297] + "..."
            
            # Safely format article info avoiding f-string issues with braces in content
            article_info = """
[{}] {}
Source: {} ({})
Content: {}
URL: {}
""".format(i, article.title, article.source, article.source_category.value, content, article.url)
            article_texts.append(article_info)
        
        articles_section = "\n".join(article_texts)
        
        # Use string formatting to avoid f-string issues with article content containing braces
        template = """You are a senior geopolitical analyst producing a structured daily intelligence briefing.

ARTICLES TO ANALYZE:
{}

Select the {} MOST STRATEGICALLY SIGNIFICANT stories from the above articles.

SOURCE PRIORITY (highest to lowest): War on the Rocks, Foreign Affairs, ICG, CSIS, Chatham House, Lawfare, The Diplomat, Foreign Policy, Atlantic Council, Al Jazeera, SCMP, mainstream outlets.

For each selected story, provide analysis in this EXACT JSON format — return a JSON array, no other text:

[
  {{
    "article_indices": [0, 3, 5],
    "story_title": "Analytically sharp title — no clichés like 'tensions rise' or 'amid uncertainty'",
    "content_type": "breaking_news or analysis or trend",
    "region": "europe or middle_east or indo_pacific or americas or africa or central_asia or global",
    "actor_type": "state or non_state or international_org or mixed",
    "event_type": "diplomatic or military or economic or informational_cyber or humanitarian or political",
    "why_important": "Strategic significance, second-order effects, power implications — max 80 words",
    "what_overlooked": "What the headline misses: structural driver, underreported actor, longer arc — max 40 words",
    "prediction": "Concrete observable threshold or next move in the next 72 hours — max 30 words",
    "impact_score": 8,
    "urgency_score": 7,
    "scope_score": 8,
    "novelty_score": 6,
    "credibility_score": 9,
    "confidence": 0.85,
    "selection_reasoning": "Why this story over others in the same category"
  }}
]

FIELD DEFINITIONS:
- content_type: breaking_news=event requiring attention today; analysis=strategic examination; trend=multi-week pattern
- region: europe=EU/NATO/Russia; middle_east=MENA/GCC/Iran/Turkey; indo_pacific=China/Japan/Koreas/SE Asia/India; americas=US/LatAm; africa=SSA/Horn/Sahel; central_asia=ex-Soviet stans/Afghanistan; global=multi-region simultaneous
- actor_type: state=governments+militaries; non_state=armed groups/corps/NGOs; international_org=UN/NATO/EU/WTO; mixed=combination
- event_type: diplomatic=summits/treaties/negotiations; military=conflict/deployments/weapons; economic=trade/energy/sanctions; informational_cyber=disinformation/hacking; humanitarian=refugees/famine/disaster; political=elections/coups/protests

SELECTION RULES:
1. Cover at least 2-3 distinct regions — no geographic clustering
2. 25% breaking news, 75% analysis/trends
3. Weight think tanks and specialist outlets heavily over wire services
4. All scores must be integers 1-10
5. Return ONLY the raw JSON array — no markdown, no explanations, no code blocks"""

        return template.format(articles_section, target_stories)
    
    def _parse_single_response(self, response_text: str, articles: List[Article]) -> List[AIAnalysis]:
        """Parse the single API response into AIAnalysis objects."""
        try:
            # Log the response for debugging
            logger.info(f"API Response (first 1000 chars): {response_text[:1000]}...")
            
            # Extract JSON from response — use greedy match so multi-object arrays parse correctly
            import re
            response_text = response_text.strip()
            # Strip markdown code fences if present
            response_text = re.sub(r'```(?:json)?\s*', '', response_text).strip('`').strip()
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not json_match:
                logger.error(f"No JSON array found in response. Full response: {response_text}")
                return self._create_mock_analyses(articles[:4])
            
            json_text = json_match.group()
            logger.info(f"Found JSON: {json_text[:500]}...")
            
            try:
                analyses_data = json.loads(json_text)
            except json.JSONDecodeError as je:
                logger.error(f"JSON decode error: {je}. JSON text: {json_text}")
                return self._create_mock_analyses(articles[:4])
            
            if not isinstance(analyses_data, list):
                logger.error(f"Expected list, got {type(analyses_data)}: {analyses_data}")
                return self._create_mock_analyses(articles[:4])
            
            analyses = []
            
            for data in analyses_data:
                # Get source URLs from article indices
                source_urls = []
                for idx in data.get('article_indices', []):
                    if 0 <= idx < len(articles):
                        source_urls.append(articles[idx].url)
                
                # Determine content type
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
                
                analyses.append(analysis)
                
                # Archive the selection reasoning for transparency
                reasoning = data.get('selection_reasoning', 'Selected based on impact')
                logger.info(f"Selected story: {analysis.story_title} - {reasoning}")
            
            return analyses
            
        except Exception as e:
            logger.error(f"Failed to parse response: {e}", exc_info=True)
            logger.error(f"Response text was: {response_text[:1000] if response_text else 'None'}")
            return self._create_mock_analyses(articles[:4])
    
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