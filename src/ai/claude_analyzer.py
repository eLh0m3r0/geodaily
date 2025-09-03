"""
Claude AI analyzer for geopolitical content analysis.
"""

import json
import re
import time
from typing import List, Dict, Optional, Any

try:
    import anthropic
except ImportError:
    anthropic = None

from ..models import Article, ArticleCluster, AIAnalysis, ContentType
from ..config import Config
from ..logger import get_logger
from .cost_controller import ai_cost_controller

logger = get_logger("main_pipeline")

class ClaudeAnalyzer:
    """Analyzes articles using Claude AI to create balanced daily geopolitical briefings."""
    
    def __init__(self):
        """Initialize Claude analyzer."""
        self.client = None
        self.mock_mode = True
        self.simulated_tokens_used = 0
        self.simulated_cost = 0.0

        # Force mock mode in DRY_RUN
        if Config.DRY_RUN:
            logger.info("DRY_RUN mode: Using simulated AI analysis")
            self.mock_mode = True
            return

        # Try to initialize real Claude client
        if Config.ANTHROPIC_API_KEY and anthropic:
            try:
                self.client = anthropic.Anthropic(
                    api_key=Config.ANTHROPIC_API_KEY
                )
                self.mock_mode = False
                logger.info("Claude analyzer initialized with real API")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude API: {e}")
                logger.info("Falling back to mock mode")
        else:
            if not Config.ANTHROPIC_API_KEY:
                logger.info("No ANTHROPIC_API_KEY found, using mock mode")
            if not anthropic:
                logger.info("anthropic package not available, using mock mode")
    
    def analyze_clusters(self, clusters: List[ArticleCluster], target_stories: int = 4) -> List[AIAnalysis]:
        """
        Analyze clusters and select balanced mix of breaking news, analysis, and trends.
        Includes cost control and budget checking.

        Args:
            clusters: List of article clusters to analyze
            target_stories: Number of stories to select

        Returns:
            List of AI analysis results for selected stories with balanced content types
        """
        logger.info(f"Analyzing {len(clusters)} clusters to select {target_stories} stories")

        if not clusters:
            return []

        # Estimate cost for this operation
        total_text_length = sum(len(cluster.main_article.title + cluster.main_article.summary)
                              for cluster in clusters[:target_stories])
        cost_estimate = ai_cost_controller.estimate_cost(total_text_length, "analysis")

        # Check budget allowance
        budget_check = ai_cost_controller.check_budget_allowance(cost_estimate.estimated_cost)

        if not budget_check['allowed']:
            logger.warning("AI analysis blocked due to budget constraints",
                          structured_data={
                              'reason': budget_check['reason'],
                              'estimated_cost': cost_estimate.estimated_cost,
                              'current_daily_cost': budget_check['current_daily_cost'],
                              'daily_limit': budget_check['daily_limit']
                          })
            # Fallback to mock analysis
            logger.info("Falling back to mock analysis due to budget constraints")
            analyses = self._create_simulated_analyses(clusters[:target_stories])
            self._log_simulation_stats(analyses)
            return analyses

        logger.info("Budget check passed, proceeding with AI analysis",
                   structured_data={
                       'estimated_cost': cost_estimate.estimated_cost,
                       'estimated_tokens': cost_estimate.estimated_tokens,
                       'current_daily_cost': budget_check['current_daily_cost'],
                       'remaining_daily_budget': budget_check['daily_limit'] - budget_check['current_daily_cost']
                   })

        try:
            if self.mock_mode:
                analyses = self._create_simulated_analyses(clusters[:target_stories])
                self._log_simulation_stats(analyses)
                return analyses
            else:
                return self._analyze_with_claude_api(clusters[:target_stories])

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            # Fallback to mock analysis
            logger.info("Falling back to mock analysis")
            analyses = self._create_simulated_analyses(clusters[:target_stories])
            self._log_simulation_stats(analyses)
            return analyses
    
    def _analyze_with_claude_api(self, clusters: List[ArticleCluster]) -> List[AIAnalysis]:
        """Analyze clusters using real Claude API."""
        if not self.client:
            logger.error("Claude client not initialized")
            return self._create_mock_analyses(clusters)
        
        analyses = []
        
        for cluster in clusters:
            try:
                analysis = self._analyze_single_cluster_with_api(cluster)
                if analysis:
                    analyses.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing cluster with API: {e}")
                # Fallback to mock for this cluster
                mock_analysis = self._create_mock_analyses([cluster])
                if mock_analysis:
                    analyses.extend(mock_analysis)
        
        return analyses
    
    def _analyze_single_cluster_with_api(self, cluster: ArticleCluster) -> Optional[AIAnalysis]:
        """Analyze a single cluster using Claude API with cost tracking."""
        main_article = cluster.main_article

        # Prepare article content for analysis
        articles_summary = self._prepare_articles_for_analysis(cluster.articles)

        prompt = self._build_analysis_prompt(articles_summary, main_article)

        try:
            start_time = time.time()

            response = self.client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=Config.AI_MAX_TOKENS,
                temperature=Config.AI_TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_time = time.time() - start_time

            # Estimate tokens used (rough approximation)
            prompt_tokens = len(prompt.split()) * 1.3  # Rough token estimation
            response_tokens = len(response.content[0].text.split()) * 1.3
            total_tokens = int(prompt_tokens + response_tokens)

            # Estimate cost (Claude pricing)
            input_cost = (prompt_tokens / 1000) * 0.0008
            output_cost = (response_tokens / 1000) * 0.0024
            total_cost = input_cost + output_cost

            # Record actual cost
            ai_cost_controller.record_cost(total_cost, total_tokens, "cluster_analysis")

            logger.debug("Claude API call completed with cost tracking",
                        structured_data={
                            'tokens_used': total_tokens,
                            'cost': total_cost,
                            'response_time': response_time,
                            'model': Config.AI_MODEL
                        })

            # Parse Claude's response
            analysis_text = response.content[0].text
            return self._parse_claude_response(analysis_text, cluster)

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return None
    
    def _prepare_articles_for_analysis(self, articles: List[Article]) -> str:
        """Prepare articles content for Claude analysis."""
        summaries = []
        for i, article in enumerate(articles[:5]):  # Limit to 5 articles per cluster
            summary = f"Article {i+1}:\n"
            summary += f"Source: {article.source} ({article.source_category.value})\n"
            summary += f"Title: {article.title}\n"
            summary += f"Summary: {article.summary[:300]}...\n"
            summaries.append(summary)
        
        return "\n\n".join(summaries)
    
    def _build_analysis_prompt(self, articles_summary: str, main_article: Article) -> str:
        """Build the analysis prompt for Claude."""
        return f"""You are a geopolitical analyst creating a daily briefing that balances breaking news, in-depth analysis, and emerging trends.

Analyze the following cluster of articles and classify the story into one of three content types:
- breaking_news: Immediate developments, urgent events, or time-sensitive announcements
- analysis: In-depth examination of ongoing situations, strategic implications, or policy impacts
- trend: Emerging patterns, long-term developments, or evolving geopolitical dynamics

{articles_summary}

Provide analysis in this exact JSON format:
{{
  "story_title": "Concise, engaging title (max 60 characters)",
  "content_type": "breaking_news|analysis|trend",
  "why_important": "Strategic significance and implications (max 80 words)",
  "what_overlooked": "What mainstream media is missing or underemphasizing (max 40 words)",
  "prediction": "Expected developments in next 72 hours (max 30 words)",
  "impact_score": [1-10 integer],
  "urgency_score": [1-10 integer],
  "scope_score": [1-10 integer],
  "novelty_score": [1-10 integer],
  "credibility_score": [1-10 integer],
  "impact_dimension_score": [1-10 integer],
  "confidence": [0.0-1.0 float]
}}

Content Type Classification Guidelines:
- breaking_news: Recent events, announcements, crises, or developments requiring immediate attention
- analysis: Deeper examination of causes, implications, or strategic context of ongoing situations
- trend: Patterns, shifts, or developments that indicate changing geopolitical landscapes over time

Scoring guidelines:
- urgency_score: How time-sensitive is this story? (1=long-term trend, 10=immediate action required)
- scope_score: Geographic/political scope of impact (1=local, 10=global systemic)
- novelty_score: How novel/unexpected is this development? (1=expected, 10=completely unprecedented)
- credibility_score: Reliability of sources and information (1=unverified rumors, 10=multiple confirmed sources)
- impact_dimension_score: Overall geopolitical significance (1=minor, 10=potentially world-changing)

Focus on:
- Second-order effects and strategic implications
- Regional power dynamics
- Economic/technological sovereignty issues
- Alliance structures and partnerships
- Information warfare and influence operations

Return only valid JSON, no additional text."""
    
    def _parse_claude_response(self, response_text: str, cluster: ArticleCluster) -> Optional[AIAnalysis]:
        """Parse Claude's JSON response into AIAnalysis object."""
        try:
            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r'{.*}', response_text, re.DOTALL)
            if not json_match:
                logger.error("No JSON found in Claude response")
                return None
            
            data = json.loads(json_match.group())
            
            # Validate required fields
            required_fields = ['story_title', 'why_important', 'what_overlooked', 'prediction', 'impact_score', 'content_type']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return None

            # Create AIAnalysis object with new multi-dimensional scores
            analysis = AIAnalysis(
                story_title=data['story_title'][:60],  # Ensure length limit
                why_important=data['why_important'],
                what_overlooked=data['what_overlooked'],
                prediction=data['prediction'],
                impact_score=int(data['impact_score']),
                content_type=ContentType(data['content_type']),
                urgency_score=int(data.get('urgency_score', 5)),
                scope_score=int(data.get('scope_score', 5)),
                novelty_score=int(data.get('novelty_score', 5)),
                credibility_score=int(data.get('credibility_score', 5)),
                impact_dimension_score=int(data.get('impact_dimension_score', 5)),
                sources=[article.url for article in cluster.articles],
                confidence=float(data.get('confidence', 0.8))
            )
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Error parsing Claude response: {e}")
            return None

    def _create_mock_analyses(self, clusters: List[ArticleCluster]) -> List[AIAnalysis]:
        """Create mock AI analyses for testing."""
        analyses = []
        
        for i, cluster in enumerate(clusters):
            main_article = cluster.main_article
            
            # Generate contextual analysis based on article content
            why_important = self._generate_why_important(main_article)
            what_overlooked = self._generate_what_overlooked(main_article)
            prediction = self._generate_prediction(main_article)
            impact_score = self._calculate_impact_score(cluster)

            # Calculate new multi-dimensional scores
            urgency_score = self._calculate_urgency_score(cluster)
            scope_score = self._calculate_scope_score(cluster)
            novelty_score = self._calculate_novelty_score(cluster)
            credibility_score = self._calculate_credibility_score(cluster)
            impact_dimension_score = self._calculate_impact_dimension_score(cluster)

            analysis = AIAnalysis(
                story_title=main_article.title,
                why_important=why_important,
                what_overlooked=what_overlooked,
                prediction=prediction,
                impact_score=impact_score,
                content_type=self._classify_content_type_mock(main_article),
                urgency_score=urgency_score,
                scope_score=scope_score,
                novelty_score=novelty_score,
                credibility_score=credibility_score,
                impact_dimension_score=impact_dimension_score,
                sources=[article.url for article in cluster.articles],
                confidence=0.8
            )
            
            analyses.append(analysis)
        
        return analyses
    
    def _generate_why_important(self, article: Article) -> str:
        """Generate 'why important' text based on article content."""
        content = f"{article.title} {article.summary}".lower()
        
        if any(keyword in content for keyword in ['china', 'taiwan', 'beijing']):
            return "This development represents a significant shift in China-Taiwan dynamics with potential implications for regional stability and US-China relations. The strategic implications extend beyond immediate bilateral concerns to broader Indo-Pacific security architecture."
        
        elif any(keyword in content for keyword in ['russia', 'ukraine', 'nato']):
            return "This story highlights evolving dynamics in the Russia-Ukraine conflict with broader implications for NATO strategy and European security. The development could influence alliance cohesion and future defense planning across the transatlantic partnership."
        
        elif any(keyword in content for keyword in ['energy', 'oil', 'gas', 'pipeline']):
            return "Energy security implications of this development extend beyond immediate market effects to geopolitical leverage and strategic dependencies. This could reshape global energy flows and influence international power dynamics significantly."
        
        elif any(keyword in content for keyword in ['cyber', 'technology', 'semiconductor']):
            return "This technological development has strategic implications for global supply chains and technological sovereignty. The story represents broader competition for technological dominance with national security implications."
        
        elif any(keyword in content for keyword in ['africa', 'middle east', 'asia']):
            return "This regional development reflects broader shifts in global power dynamics and emerging market influence. The implications extend to international partnerships and strategic competition among major powers."
        
        else:
            return f"This development in {article.source_category.value} geopolitics represents a significant shift with potential implications for international relations and strategic decision-making. The story highlights emerging trends that could influence global stability."
    
    def _generate_what_overlooked(self, article: Article) -> str:
        """Generate 'what overlooked' text based on article content."""
        content = f"{article.title} {article.summary}".lower()
        
        if 'china' in content:
            return "Mainstream coverage focuses on immediate tensions but misses long-term strategic positioning and economic dimensions."
        
        elif 'russia' in content:
            return "Analysis emphasizes military aspects while overlooking economic warfare and information operations components."
        
        elif 'energy' in content:
            return "Media attention centers on price impacts but underestimates geopolitical leverage and strategic dependencies."
        
        elif 'technology' in content:
            return "Coverage highlights technical aspects but misses broader implications for technological sovereignty and supply chain security."
        
        elif any(region in content for region in ['africa', 'asia', 'middle east']):
            return "Western media focuses on immediate events but overlooks broader regional power dynamics and emerging partnerships."
        
        else:
            return "Mainstream analysis focuses on surface-level developments while missing deeper strategic implications and second-order effects."
    
    def _generate_prediction(self, article: Article) -> str:
        """Generate prediction text based on article content."""
        content = f"{article.title} {article.summary}".lower()
        
        if 'china' in content:
            return "Expect escalated diplomatic responses and potential new security partnerships within 3-6 months."
        
        elif 'russia' in content:
            return "Anticipate expanded sanctions regime and enhanced NATO coordination in coming weeks."
        
        elif 'energy' in content:
            return "Watch for new energy partnerships and infrastructure deals within the next quarter."
        
        elif 'technology' in content:
            return "Expect new export controls and technology transfer restrictions in the near term."
        
        elif 'election' in content:
            return "Monitor for policy shifts and new international agreements following electoral outcomes."
        
        else:
            return "Watch for cascading effects on regional partnerships and international cooperation frameworks."
    
    def _calculate_impact_score(self, cluster: ArticleCluster) -> int:
        """Calculate impact score based on cluster characteristics."""
        score = 5  # Base score
        
        main_article = cluster.main_article
        content = f"{main_article.title} {main_article.summary}".lower()
        
        # High-impact keywords
        if any(keyword in content for keyword in ['china', 'taiwan', 'russia', 'ukraine', 'nato']):
            score += 2
        
        # Medium-impact keywords
        if any(keyword in content for keyword in ['nuclear', 'sanctions', 'energy', 'cyber']):
            score += 1
        
        # Source quality bonus
        if main_article.source_category.value == 'think_tank':
            score += 1
        elif main_article.source_category.value == 'analysis':
            score += 1
        
        # Cluster size bonus
        if len(cluster.articles) > 2:
            score += 1
        
        # Relevance score bonus
        if main_article.relevance_score > 3.0:
            score += 1
        
        return min(10, max(1, score))

    def _calculate_urgency_score(self, cluster: ArticleCluster) -> int:
        """Calculate urgency score based on cluster characteristics."""
        score = 5  # Base score

        main_article = cluster.main_article
        content = f"{main_article.title} {main_article.summary}".lower()

        # High-urgency keywords
        if any(keyword in content for keyword in ['breaking', 'urgent', 'immediate', 'crisis', 'emergency']):
            score += 3

        # Medium-urgency keywords
        if any(keyword in content for keyword in ['escalation', 'deadline', 'warning', 'alert']):
            score += 2

        # Time-sensitive topics
        if any(keyword in content for keyword in ['election', 'summit', 'meeting', 'deadline']):
            score += 1

        return min(10, max(1, score))

    def _calculate_scope_score(self, cluster: ArticleCluster) -> int:
        """Calculate scope score based on cluster characteristics."""
        score = 5  # Base score

        main_article = cluster.main_article
        content = f"{main_article.title} {main_article.summary}".lower()

        # Global scope keywords
        if any(keyword in content for keyword in ['global', 'world', 'international', 'nato', 'united nations']):
            score += 3

        # Regional scope keywords
        if any(keyword in content for keyword in ['asia', 'europe', 'middle east', 'africa', 'americas']):
            score += 2

        # Multiple countries mentioned
        countries = ['china', 'russia', 'usa', 'uk', 'germany', 'france', 'japan', 'india']
        country_count = sum(1 for country in countries if country in content)
        score += min(2, country_count)

        return min(10, max(1, score))

    def _calculate_novelty_score(self, cluster: ArticleCluster) -> int:
        """Calculate novelty score based on cluster characteristics."""
        score = 5  # Base score

        main_article = cluster.main_article
        content = f"{main_article.title} {main_article.summary}".lower()

        # Novel developments
        if any(keyword in content for keyword in ['breakthrough', 'unprecedented', 'first time', 'historic', 'surprise']):
            score += 3

        # Unexpected events
        if any(keyword in content for keyword in ['sudden', 'unexpected', 'shock', 'surprising']):
            score += 2

        # New developments
        if any(keyword in content for keyword in ['new', 'emerging', 'developing']):
            score += 1

        return min(10, max(1, score))

    def _calculate_credibility_score(self, cluster: ArticleCluster) -> int:
        """Calculate credibility score based on cluster characteristics."""
        score = 5  # Base score

        main_article = cluster.main_article

        # Source quality bonus
        if main_article.source_category.value == 'think_tank':
            score += 2
        elif main_article.source_category.value == 'analysis':
            score += 2
        elif main_article.source_category.value == 'mainstream':
            score += 1

        # Multiple sources bonus
        if len(cluster.articles) > 3:
            score += 2
        elif len(cluster.articles) > 1:
            score += 1

        # High relevance score bonus
        if main_article.relevance_score > 4.0:
            score += 1

        return min(10, max(1, score))

    def _calculate_impact_dimension_score(self, cluster: ArticleCluster) -> int:
        """Calculate impact dimension score (similar to original impact_score but focused on geopolitical significance)."""
        score = 5  # Base score

        main_article = cluster.main_article
        content = f"{main_article.title} {main_article.summary}".lower()

        # High-impact keywords
        if any(keyword in content for keyword in ['china', 'taiwan', 'russia', 'ukraine', 'nato', 'nuclear']):
            score += 3

        # Medium-impact keywords
        if any(keyword in content for keyword in ['sanctions', 'energy', 'cyber', 'alliance', 'treaty']):
            score += 2

        # Strategic keywords
        if any(keyword in content for keyword in ['sovereignty', 'influence', 'power', 'dominance']):
            score += 1

        return min(10, max(1, score))

    def _classify_content_type_mock(self, article: Article) -> ContentType:
        """Classify content type for mock analysis."""
        content = f"{article.title} {article.summary}".lower()

        # Breaking news keywords
        if any(keyword in content for keyword in ['breaking', 'urgent', 'crisis', 'emergency', 'attack', 'announcement', 'statement', 'meeting']):
            return ContentType.BREAKING_NEWS

        # Trend keywords
        if any(keyword in content for keyword in ['trend', 'emerging', 'shift', 'changing', 'evolution', 'pattern', 'long-term', 'future']):
            return ContentType.TREND

        # Default to analysis
        return ContentType.ANALYSIS

    def _create_simulated_analyses(self, clusters: List[ArticleCluster]) -> List[AIAnalysis]:
        """Create simulated AI analyses with realistic content and tracking."""
        analyses = []

        for i, cluster in enumerate(clusters):
            main_article = cluster.main_article

            # Generate contextual analysis based on article content
            why_important = self._generate_why_important(main_article)
            what_overlooked = self._generate_what_overlooked(main_article)
            prediction = self._generate_prediction(main_article)
            impact_score = self._calculate_impact_score(cluster)

            # Calculate new multi-dimensional scores
            urgency_score = self._calculate_urgency_score(cluster)
            scope_score = self._calculate_scope_score(cluster)
            novelty_score = self._calculate_novelty_score(cluster)
            credibility_score = self._calculate_credibility_score(cluster)
            impact_dimension_score = self._calculate_impact_dimension_score(cluster)

            # Simulate API call metrics
            simulated_input_tokens = len(f"{main_article.title} {main_article.summary}".split()) + 100  # Base prompt tokens
            simulated_output_tokens = len(f"{why_important} {what_overlooked} {prediction}".split()) + 50  # Response tokens

            # Track simulated usage
            self.simulated_tokens_used += simulated_input_tokens + simulated_output_tokens
            # Claude pricing: ~$0.0008 per 1K input tokens, ~$0.0024 per 1K output tokens (approximate)
            simulated_cost_increment = (simulated_input_tokens / 1000 * 0.0008) + (simulated_output_tokens / 1000 * 0.0024)
            self.simulated_cost += simulated_cost_increment

            analysis = AIAnalysis(
                story_title=main_article.title[:60],  # Ensure length limit
                why_important=why_important,
                what_overlooked=what_overlooked,
                prediction=prediction,
                impact_score=impact_score,
                content_type=self._classify_content_type_mock(main_article),
                urgency_score=urgency_score,
                scope_score=scope_score,
                novelty_score=novelty_score,
                credibility_score=credibility_score,
                impact_dimension_score=impact_dimension_score,
                sources=[article.url for article in cluster.articles],
                confidence=0.85  # Slightly higher confidence for simulation
            )

            analyses.append(analysis)

        return analyses

    def _log_simulation_stats(self, analyses: List[AIAnalysis]):
        """Log simulation statistics and costs."""
        if not Config.DRY_RUN:
            return

        logger.info("=== DRY RUN SIMULATION STATS ===")
        logger.info(f"Simulated API calls: {len(analyses)}")
        logger.info(f"Simulated tokens used: {self.simulated_tokens_used}")
        logger.info(f"Simulated cost: ${self.simulated_cost:.4f}")
        logger.info("=================================")

        # Log individual analysis details
        for i, analysis in enumerate(analyses, 1):
            logger.info(f"Story {i}: '{analysis.story_title[:40]}...' (Impact: {analysis.impact_score}/10, Confidence: {analysis.confidence:.2f})")

    def get_simulation_stats(self) -> Dict[str, Any]:
        """Get current simulation statistics."""
        return {
            "simulated_tokens_used": self.simulated_tokens_used,
            "simulated_cost": self.simulated_cost,
            "simulated_api_calls": 0  # Would need to track this separately if needed
        }

    def test_api_connection(self) -> bool:
        """Test if Claude API is working."""
        if self.mock_mode:
            logger.info("Testing API connection (mock mode)")
            return True
        
        try:
            # Simple test prompt
            response = self.client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=50,
                temperature=0.0,
                messages=[{
                    "role": "user", 
                    "content": "Respond with exactly: 'API connection successful'"
                }]
            )
            
            result = response.content[0].text.strip()
            if "API connection successful" in result:
                logger.info("✅ Claude API connection test successful")
                return True
            else:
                logger.warning(f"Unexpected API response: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Claude API connection test failed: {e}")
            return False
