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
            
            # Archive the response
            ai_archiver.archive_ai_response(
                response_text=response_text,
                analysis=analyses,
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
            
            article_texts.append(f"""
[{i}] {article.title}
Source: {article.source} ({article.source_category.value})
Content: {content}
URL: {article.url}
""")
        
        articles_section = "\n".join(article_texts)
        
        return f"""You are a geopolitical analyst creating a daily newsletter. Analyze these {len(articles)} articles and select the {target_stories} MOST IMPORTANT stories.

ARTICLES TO ANALYZE:
{articles_section}

ANALYSIS INSTRUCTIONS:
Perform a transparent multi-stage analysis:

1. RELEVANCE SCREENING: Mentally evaluate each article for geopolitical relevance
2. CATEGORY ANALYSIS: Group by strategic importance (conflicts, economic, diplomatic, etc.)
3. STRATEGIC SELECTION: Choose the {target_stories} most impactful stories
4. CONTENT GENERATION: Create compelling newsletter content

For each of the {target_stories} selected stories, provide analysis in this EXACT JSON format:

```json
[
  {{
    "article_indices": [index numbers of source articles used],
    "story_title": "Compelling 60-character title",
    "why_important": "Why this matters geopolitically (80 words max)",
    "what_overlooked": "What mainstream media might be missing (40 words max)",
    "prediction": "What might happen next (30 words max)",
    "impact_score": 8,
    "urgency_score": 7,
    "scope_score": 8,
    "novelty_score": 6,
    "credibility_score": 9,
    "content_type": "breaking_news|analysis|trend",
    "confidence": 0.85,
    "selection_reasoning": "Why this story was selected over others"
  }}
]
```

IMPORTANT:
- Select stories with genuine geopolitical impact
- Ensure diversity (not all from same region/topic)
- Prioritize breaking news (25%) and deep analysis (75%)
- All scores should be 1-10
- Return ONLY the JSON array, no other text"""
    
    def _parse_single_response(self, response_text: str, articles: List[Article]) -> List[AIAnalysis]:
        """Parse the single API response into AIAnalysis objects."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not json_match:
                logger.error("No JSON found in response")
                return self._create_mock_analyses(articles[:4])
            
            analyses_data = json.loads(json_match.group())
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
                    story_title=data.get('story_title', 'Untitled Story')[:60],
                    why_important=data.get('why_important', 'Important geopolitical development'),
                    what_overlooked=data.get('what_overlooked', 'Broader strategic implications'),
                    prediction=data.get('prediction', 'Situation likely to evolve'),
                    impact_score=int(data.get('impact_score', 7)),
                    urgency_score=int(data.get('urgency_score', 5)),
                    scope_score=int(data.get('scope_score', 6)),
                    novelty_score=int(data.get('novelty_score', 5)),
                    credibility_score=int(data.get('credibility_score', 7)),
                    impact_dimension_score=int(data.get('impact_score', 7)),  # Use impact as dimension
                    content_type=content_type,
                    sources=source_urls or ['No source'],
                    confidence=float(data.get('confidence', 0.7))
                )
                
                analyses.append(analysis)
                
                # Archive the selection reasoning for transparency
                reasoning = data.get('selection_reasoning', 'Selected based on impact')
                logger.info(f"Selected story: {analysis.story_title} - {reasoning}")
            
            return analyses
            
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return self._create_mock_analyses(articles[:4])
    
    def _create_mock_analyses(self, articles: List[Article]) -> List[AIAnalysis]:
        """Create mock analyses for testing."""
        analyses = []
        
        for i, article in enumerate(articles[:4]):
            content_type = ContentType.BREAKING_NEWS if i == 0 else ContentType.ANALYSIS
            
            analysis = AIAnalysis(
                story_title=article.title[:60],
                why_important=f"This story about {article.source_category.value} represents a significant geopolitical development",
                what_overlooked="The broader strategic implications may be underappreciated",
                prediction="This situation will likely evolve with regional impacts",
                impact_score=7 + i % 3,
                urgency_score=6 + i % 2,
                scope_score=7,
                novelty_score=5 + i % 3,
                credibility_score=8,
                impact_dimension_score=7 + i % 3,
                content_type=content_type,
                sources=[article.url],
                confidence=0.75
            )
            analyses.append(analysis)
        
        return analyses