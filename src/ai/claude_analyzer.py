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
from ..archiver.ai_data_archiver import ai_archiver

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
    
    def analyze_articles(self, articles: List[Article], target_stories: int = 4) -> List[AIAnalysis]:
        """
        Analyze individual articles directly and select the best stories.
        This bypasses clustering and lets Claude handle article selection directly.

        Args:
            articles: List of individual articles to analyze
            target_stories: Number of stories to select

        Returns:
            List of AI analysis results for selected stories
        """
        logger.info(f"Analyzing {len(articles)} articles directly to select {target_stories} stories")

        if not articles:
            return []

        # Pre-filter articles to manageable number for AI processing
        # Sort by relevance score and take top articles
        sorted_articles = sorted(articles, key=lambda a: getattr(a, 'relevance_score', 0), reverse=True)
        
        # Take more articles than needed to give Claude good selection
        candidates_count = min(target_stories * 3, len(sorted_articles), 15)  # Max 15 articles for API limits
        candidate_articles = sorted_articles[:candidates_count]
        
        logger.info(f"Pre-filtered to {len(candidate_articles)} candidate articles for AI analysis")

        # Estimate cost for this operation
        total_text_length = sum(len(article.title + article.summary) for article in candidate_articles)
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
            analyses = self._create_simulated_analyses_from_articles(candidate_articles[:target_stories])
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
                analyses = self._create_simulated_analyses_from_articles(candidate_articles[:target_stories])
                self._log_simulation_stats(analyses)
                return analyses
            else:
                return self._analyze_articles_with_claude_api(candidate_articles, target_stories)

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            # Fallback to mock analysis
            logger.info("Falling back to mock analysis")
            analyses = self._create_simulated_analyses_from_articles(candidate_articles[:target_stories])
            self._log_simulation_stats(analyses)
            return analyses
    
    def _analyze_articles_with_claude_api(self, articles: List[Article], target_stories: int) -> List[AIAnalysis]:
        """Analyze individual articles using real Claude API."""
        if not self.client:
            logger.error("Claude client not initialized")
            return self._create_simulated_analyses_from_articles(articles[:target_stories])
        
        analyses = []
        
        # Archive all candidate articles
        for i, article in enumerate(articles):
            ai_archiver.archive_article(article, i)
        
        try:
            # Send all articles to Claude in a single request for selection
            analysis_results = self._analyze_multiple_articles_with_api(articles, target_stories)
            if analysis_results:
                analyses.extend(analysis_results)
        except Exception as e:
            logger.error(f"Error analyzing articles with API: {e}")
            # Fallback to mock for remaining articles
            mock_analyses = self._create_simulated_analyses_from_articles(articles[:target_stories])
            if mock_analyses:
                analyses.extend(mock_analyses)
        
        return analyses
    
    def _analyze_multiple_articles_with_api(self, articles: List[Article], target_stories: int) -> List[AIAnalysis]:
        """Analyze multiple articles with Claude API in a single request for intelligent selection."""
        
        # Prepare articles content for analysis
        articles_summary = self._prepare_articles_for_analysis_direct(articles)
        
        prompt = self._build_multi_article_analysis_prompt(articles_summary, target_stories)
        
        # Archive the AI request
        ai_archiver.archive_ai_request(
            prompt=prompt,
            articles_summary=articles_summary,
            cluster_index=0,
            main_article_title=f"Multi-article analysis ({len(articles)} articles)"
        )

        try:
            start_time = time.time()

            logger.info("Making Claude API call for multi-article selection",
                        structured_data={
                            'model': Config.AI_MODEL,
                            'max_tokens': Config.AI_MAX_TOKENS,
                            'temperature': Config.AI_TEMPERATURE,
                            'prompt_length': len(prompt),
                            'articles_count': len(articles),
                            'target_stories': target_stories
                        })

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

            # Estimate tokens used
            prompt_tokens = len(prompt.split()) * 1.3
            response_tokens = len(response.content[0].text.split()) * 1.3
            total_tokens = int(prompt_tokens + response_tokens)

            # Estimate cost
            input_cost = (prompt_tokens / 1000) * 0.0008
            output_cost = (response_tokens / 1000) * 0.0024
            total_cost = input_cost + output_cost

            # Record actual cost
            ai_cost_controller.record_cost(total_cost, total_tokens, "multi_article_analysis")

            logger.debug("Claude API multi-article call completed",
                        structured_data={
                            'tokens_used': total_tokens,
                            'cost': total_cost,
                            'response_time': response_time,
                            'model': Config.AI_MODEL
                        })

            # Parse Claude's response
            analysis_text = response.content[0].text

            logger.info("Claude API multi-article response received",
                        structured_data={
                            'response_length': len(analysis_text),
                            'articles_analyzed': len(articles)
                        })
            
            # Parse the multi-article response  
            logger.debug(f"Claude response received (first 500 chars): {analysis_text[:500]}...")
            parsed_analyses = self._parse_claude_multi_article_response(analysis_text, articles)
            
            # Archive the AI response (only if we have valid parsed analyses)
            if parsed_analyses:
                for i, analysis in enumerate(parsed_analyses):
                    ai_archiver.archive_ai_response(
                        response_text=analysis_text,
                        analysis=analysis,  # Single analysis instead of list
                        cluster_index=i,
                        cost=total_cost / len(parsed_analyses) if len(parsed_analyses) > 0 else total_cost,
                        tokens=total_tokens // len(parsed_analyses) if len(parsed_analyses) > 0 else total_tokens
                    )
            else:
                # Archive the response even if parsing failed
                ai_archiver.archive_ai_response(
                    response_text=analysis_text,
                    analysis=None,
                    cluster_index=0,
                    cost=total_cost,
                    tokens=total_tokens
                )

            return parsed_analyses

        except Exception as e:
            logger.error(f"Claude API multi-article call failed: {e}")
            return []
    
    def _prepare_articles_for_analysis_direct(self, articles: List[Article]) -> str:
        """Prepare individual articles content for Claude analysis."""
        summaries = []
        for i, article in enumerate(articles):
            summary = f"Article {i+1}:\n"
            summary += f"Source: {article.source} ({article.source_category.value})\n"
            summary += f"Title: {article.title}\n"
            summary += f"URL: {article.url}\n"
            summary += f"Summary: {article.summary[:400]}...\n"  # Longer summaries for better context
            summary += f"Relevance Score: {getattr(article, 'relevance_score', 'N/A')}\n"
            summaries.append(summary)
        
        return "\n" + "="*80 + "\n".join(summaries)
    
    def _build_multi_article_analysis_prompt(self, articles_summary: str, target_stories: int) -> str:
        """Build the analysis prompt for multiple articles selection."""
        return f"""You are a geopolitical analyst creating a daily briefing that balances breaking news, in-depth analysis, and emerging trends.

Analyze the following {len(articles_summary.split('Article '))-1} articles and select the {target_stories} most important stories for today's geopolitical newsletter. Focus on:

1. **Strategic significance** - Stories that impact international relations, power dynamics, or regional stability
2. **Content diversity** - Balance of breaking news, analysis, and emerging trends  
3. **Source quality** - Prioritize think tanks and analysis sources over regional/biased sources
4. **Novelty and importance** - Fresh developments with meaningful geopolitical implications

**IMPORTANT SOURCE CONSIDERATIONS:**
- RT Today and similar sources should have lower priority due to bias
- Think tanks (CSIS, Atlantic Council) and analysis sources (Foreign Affairs, Foreign Policy) should be prioritized
- Look for stories that complement each other rather than overlap

{articles_summary}

For each selected story, provide analysis in this exact JSON format, enclosed in a JSON array:

[
  {{
    "article_index": [1-based index of selected article],
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
]

Content Type Guidelines:
- breaking_news: Recent events, announcements, crises requiring immediate attention
- analysis: Deeper examination of causes, implications, strategic context
- trend: Patterns, shifts indicating changing geopolitical landscapes

Scoring Guidelines:
- urgency_score: Time sensitivity (1=long-term, 10=immediate)
- scope_score: Geographic/political impact (1=local, 10=global)  
- novelty_score: Unexpectedness (1=expected, 10=unprecedented)
- credibility_score: Source reliability (1=unverified, 10=confirmed)
- impact_dimension_score: Geopolitical significance (1=minor, 10=world-changing)

Return ONLY the JSON array, no additional text. Select exactly {target_stories} stories."""
    
    def _parse_claude_multi_article_response(self, response_text: str, articles: List[Article]) -> List[AIAnalysis]:
        """Parse Claude's multi-article JSON response into AIAnalysis objects."""
        try:
            import re
            import json
            
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not json_match:
                logger.error("No JSON array found in Claude multi-article response")
                return []
            
            data_array = json.loads(json_match.group())
            
            if not isinstance(data_array, list):
                logger.error("Response is not a JSON array")
                return []
            
            analyses = []
            for data in data_array:
                # Validate required fields
                required_fields = ['article_index', 'story_title', 'why_important', 'what_overlooked', 
                                 'prediction', 'impact_score', 'content_type']
                
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    logger.error(f"Missing required fields in analysis: {missing_fields}")
                    continue
                
                # Get the source article
                article_index = int(data['article_index']) - 1  # Convert to 0-based
                if article_index < 0 or article_index >= len(articles):
                    logger.error(f"Invalid article index: {article_index}")
                    continue
                
                source_article = articles[article_index]
                
                # Create AIAnalysis object
                analysis = AIAnalysis(
                    story_title=data['story_title'][:60],
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
                    sources=[source_article.url],  # Single source per analysis
                    confidence=float(data.get('confidence', 0.8))
                )
                
                analyses.append(analysis)
                logger.info(f"Parsed analysis for: {source_article.title[:50]}...")
            
            logger.info(f"Successfully parsed {len(analyses)} analyses from Claude response")
            return analyses
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude multi-article response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Claude multi-article response: {e}")
            return []
    
    def _create_simulated_analyses_from_articles(self, articles: List[Article]) -> List[AIAnalysis]:
        """Create simulated AI analyses from individual articles."""
        analyses = []
        
        for i, article in enumerate(articles):
            # Generate contextual analysis based on article content
            why_important = self._generate_why_important_from_article(article)
            what_overlooked = self._generate_what_overlooked_from_article(article)
            prediction = self._generate_prediction_from_article(article)
            
            # Calculate scores based on article attributes (not cluster)
            impact_score = self._calculate_impact_score_from_article(article)
            urgency_score = self._calculate_urgency_score_from_article(article)
            scope_score = self._calculate_scope_score_from_article(article)
            novelty_score = self._calculate_novelty_score_from_article(article)
            credibility_score = self._calculate_credibility_score_from_article(article)
            impact_dimension_score = self._calculate_impact_dimension_score_from_article(article)

            # Simulate API call metrics for this article
            simulated_input_tokens = len(f"{article.title} {article.summary}".split()) + 100
            simulated_output_tokens = len(f"{why_important} {what_overlooked} {prediction}".split()) + 50

            # Track simulated usage
            self.simulated_tokens_used += simulated_input_tokens + simulated_output_tokens
            simulated_cost_increment = (simulated_input_tokens / 1000 * 0.0008) + (simulated_output_tokens / 1000 * 0.0024)
            self.simulated_cost += simulated_cost_increment

            analysis = AIAnalysis(
                story_title=article.title[:60],
                why_important=why_important,
                what_overlooked=what_overlooked,
                prediction=prediction,
                impact_score=impact_score,
                content_type=self._classify_content_type_mock(article),
                urgency_score=urgency_score,
                scope_score=scope_score,
                novelty_score=novelty_score,
                credibility_score=credibility_score,
                impact_dimension_score=impact_dimension_score,
                sources=[article.url],
                confidence=0.85
            )
            
            analyses.append(analysis)
        
        return analyses

    # Helper methods for article-based scoring (without clusters)
    def _calculate_impact_score_from_article(self, article: Article) -> int:
        """Calculate impact score based on individual article characteristics."""
        score = 5  # Base score
        
        content = f"{article.title} {article.summary}".lower()
        
        # High-impact keywords
        if any(keyword in content for keyword in ['china', 'taiwan', 'russia', 'ukraine', 'nato']):
            score += 2
        
        # Medium-impact keywords
        if any(keyword in content for keyword in ['nuclear', 'sanctions', 'energy', 'cyber']):
            score += 1
        
        # Source quality bonus
        if article.source_category.value == 'think_tank':
            score += 1
        elif article.source_category.value == 'analysis':
            score += 1
        
        # Relevance score bonus
        if getattr(article, 'relevance_score', 0) > 3.0:
            score += 1
        
        # Source bias adjustments
        source_bias_penalty = self._get_source_bias_penalty(article.source)
        score -= source_bias_penalty
        
        return min(10, max(1, score))

    def _calculate_urgency_score_from_article(self, article: Article) -> int:
        """Calculate urgency score based on individual article characteristics."""
        score = 5  # Base score

        content = f"{article.title} {article.summary}".lower()

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

    def _calculate_scope_score_from_article(self, article: Article) -> int:
        """Calculate scope score based on individual article characteristics."""
        score = 5  # Base score

        content = f"{article.title} {article.summary}".lower()

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

    def _calculate_novelty_score_from_article(self, article: Article) -> int:
        """Calculate novelty score based on individual article characteristics."""
        score = 5  # Base score

        content = f"{article.title} {article.summary}".lower()

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

    def _calculate_credibility_score_from_article(self, article: Article) -> int:
        """Calculate credibility score based on individual article characteristics."""
        score = 5  # Base score

        # Source quality bonus
        if article.source_category.value == 'think_tank':
            score += 2
        elif article.source_category.value == 'analysis':
            score += 2
        elif article.source_category.value == 'mainstream':
            score += 1

        # High relevance score bonus
        if getattr(article, 'relevance_score', 0) > 4.0:
            score += 1
        
        # Source bias adjustments
        source_bias_penalty = self._get_source_bias_penalty(article.source)
        score -= source_bias_penalty
        
        return min(10, max(1, score))

    def _calculate_impact_dimension_score_from_article(self, article: Article) -> int:
        """Calculate impact dimension score based on individual article characteristics."""
        score = 5  # Base score

        content = f"{article.title} {article.summary}".lower()

        # High-impact keywords
        if any(keyword in content for keyword in ['china', 'taiwan', 'russia', 'ukraine', 'nato', 'nuclear']):
            score += 3

        # Medium-impact keywords
        if any(keyword in content for keyword in ['sanctions', 'energy', 'cyber', 'alliance', 'treaty']):
            score += 2

        # Strategic keywords
        if any(keyword in content for keyword in ['sovereignty', 'influence', 'power', 'dominance']):
            score += 1
        
        # Source bias adjustments
        source_bias_penalty = self._get_source_bias_penalty(article.source)
        score -= source_bias_penalty
        
        return min(10, max(1, score))
    
    def _generate_why_important_from_article(self, article: Article) -> str:
        """Generate why_important text from individual article."""
        content = f"{article.title} {article.summary}".lower()
        
        if any(keyword in content for keyword in ['china', 'taiwan']):
            return "This development impacts critical US-China strategic competition and regional stability in the Asia-Pacific, with implications for global supply chains and military positioning."
        elif any(keyword in content for keyword in ['russia', 'ukraine']):
            return "This story reflects ongoing shifts in European security architecture and NATO cohesion, affecting global energy markets and international law enforcement."
        elif any(keyword in content for keyword in ['nuclear', 'cyber']):
            return "This represents a significant escalation in strategic domains that could reshape deterrence calculations and international security frameworks."
        else:
            return f"This development in {article.source_category.value} geopolitics has potential implications for international relations and strategic decision-making."
    
    def _generate_what_overlooked_from_article(self, article: Article) -> str:
        """Generate what_overlooked text from individual article."""
        if article.source_category.value == 'think_tank':
            return "Strategic analysis perspective often missing from breaking news coverage."
        elif 'economic' in f"{article.title} {article.summary}".lower():
            return "Economic implications and second-order market effects."
        else:
            return "Long-term strategic implications and regional spillover effects."
    
    def _generate_prediction_from_article(self, article: Article) -> str:
        """Generate prediction text from individual article."""
        content = f"{article.title} {article.summary}".lower()
        
        if any(keyword in content for keyword in ['summit', 'meeting', 'talks']):
            return "Expect follow-up diplomatic engagement and possible joint statements within 48-72 hours."
        elif any(keyword in content for keyword in ['sanctions', 'trade']):
            return "Market reactions and possible retaliatory measures likely within next week."
        else:
            return "This situation will likely evolve over the coming weeks with potential impacts on regional stability."
    
    def _analyze_with_claude_api(self, clusters: List[ArticleCluster]) -> List[AIAnalysis]:
        """Analyze clusters using real Claude API."""
        if not self.client:
            logger.error("Claude client not initialized")
            return self._create_mock_analyses(clusters)
        
        analyses = []
        
        for i, cluster in enumerate(clusters):
            # Archive the cluster before analysis
            ai_archiver.archive_cluster(cluster, i)
            
            try:
                analysis = self._analyze_single_cluster_with_api(cluster, cluster_index=i)
                if analysis:
                    analyses.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing cluster with API: {e}")
                # Fallback to mock for this cluster
                mock_analysis = self._create_mock_analyses([cluster])
                if mock_analysis:
                    analyses.extend(mock_analysis)
        
        return analyses
    
    def _analyze_single_cluster_with_api(self, cluster: ArticleCluster, cluster_index: int = 0) -> Optional[AIAnalysis]:
        """Analyze a single cluster using Claude API with cost tracking."""
        main_article = cluster.main_article

        # Prepare article content for analysis
        articles_summary = self._prepare_articles_for_analysis(cluster.articles)

        prompt = self._build_analysis_prompt(articles_summary, main_article)
        
        # Archive the AI request
        ai_archiver.archive_ai_request(
            prompt=prompt,
            articles_summary=articles_summary,
            cluster_index=cluster_index,
            main_article_title=main_article.title if main_article else "Unknown"
        )

        try:
            start_time = time.time()

            logger.info("Making Claude API call",
                        structured_data={
                            'model': Config.AI_MODEL,
                            'max_tokens': Config.AI_MAX_TOKENS,
                            'temperature': Config.AI_TEMPERATURE,
                            'prompt_length': len(prompt)
                        })
    
            # Log full prompt and content for debugging
            logger.info("=== CLAUDE API REQUEST DEBUG ===",
                        structured_data={
                            'full_prompt': prompt,
                            'articles_summary': articles_summary,
                            'cluster_main_article': main_article.title if main_article else 'None',
                            'cluster_size': len(cluster.articles) if cluster else 0
                        })

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

            # Log Claude's response for debugging
            logger.info("=== CLAUDE API RESPONSE DEBUG ===",
                        structured_data={
                            'response_text': analysis_text,
                            'response_length': len(analysis_text),
                            'cluster_main_article': main_article.title if main_article else 'None'
                        })
            
            # Parse the response
            parsed_analysis = self._parse_claude_response(analysis_text, cluster)
            
            # Archive the AI response
            ai_archiver.archive_ai_response(
                response_text=analysis_text,
                analysis=parsed_analysis,
                cluster_index=cluster_index,
                cost=total_cost,
                tokens=total_tokens
            )

            return parsed_analysis

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
    
    def _load_recent_newsletter_history(self, days_back: int = 2) -> str:
        """Load recent newsletter titles for diversity context."""
        try:
            from datetime import datetime, timedelta
            import os
            
            # Import BeautifulSoup safely
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                logger.warning("BeautifulSoup not available, skipping newsletter history")
                return "Newsletter history unavailable - missing BeautifulSoup"
            
            history_entries = []
            today = datetime.now().date()
            
            # Look for newsletters from previous days (skip today)
            for i in range(1, days_back + 1):
                date = today - timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                newsletter_path = os.path.join("docs", "newsletters", f"newsletter-{date_str}.html")
                
                if os.path.exists(newsletter_path):
                    try:
                        with open(newsletter_path, 'r', encoding='utf-8') as f:
                            soup = BeautifulSoup(f.read(), 'html.parser')
                            titles = [elem.get_text().strip() 
                                     for elem in soup.find_all('h2', class_='story-title')]
                        
                        if titles:
                            history_entries.append(f"Day -{i} ({date_str}): {' | '.join(titles)}")
                    except Exception as e:
                        logger.warning(f"Error parsing newsletter {newsletter_path}: {e}")
                        continue
            
            return "\n".join(history_entries) if history_entries else "No recent newsletter history found."
            
        except Exception as e:
            logger.warning(f"Newsletter history loading failed: {e}")
            return "Newsletter history unavailable due to error."

    def _build_analysis_prompt(self, articles_summary: str, main_article: Article) -> str:
        """Build the analysis prompt for Claude with newsletter history context."""
        
        # Load newsletter history for diversity awareness
        newsletter_context = ""
        if Config.ENABLE_NEWSLETTER_HISTORY:
            newsletter_history = self._load_recent_newsletter_history(Config.NEWSLETTER_HISTORY_DAYS)
            newsletter_context = f"""
RECENT NEWSLETTER COVERAGE (Last {Config.NEWSLETTER_HISTORY_DAYS} days):
{newsletter_history}

DIVERSITY REQUIREMENTS:
- AVOID stories with identical or very similar titles to recent coverage above
- AVOID same actors doing similar actions (Putin/Russia, Trump/US, China/Xi repeatedly)
- PRIORITIZE different geographic regions and new geopolitical angles
- ENSURE variety: breaking news (~25%), analysis (~50%), trends (~25%)

"""
        
        return f"""You are a geopolitical analyst creating today's briefing with strategic diversity awareness.

{newsletter_context}Analyze the following cluster of articles and classify the story into one of three content types:
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
                story_title=data['story_title'],  # Keep full title
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
        
        # Source bias adjustments - lower impact for specific sources
        source_bias_penalty = self._get_source_bias_penalty(main_article.source)
        score -= source_bias_penalty
        
        return min(10, max(1, score))
    
    def _get_source_bias_penalty(self, source: str) -> int:
        """Get source-specific bias penalty to reduce impact of certain sources."""
        # Normalize source name for comparison
        source_lower = source.lower()
        
        # High bias penalty for sources that should have significantly reduced impact
        if any(biased_source in source_lower for biased_source in ['rt.com', 'russia today', 'rt news']):
            return 3  # Significant penalty for RT
        
        if any(biased_source in source_lower for biased_source in ['scmp.com', 'south china morning post']):
            return 2  # Moderate penalty for SCMP
        
        # No penalty for other sources
        return 0

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
        
        # Source bias adjustments - lower credibility for specific sources
        source_bias_penalty = self._get_source_bias_penalty(main_article.source)
        score -= source_bias_penalty
        
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
        
        # Source bias adjustments - lower impact dimension for specific sources
        source_bias_penalty = self._get_source_bias_penalty(main_article.source)
        score -= source_bias_penalty
        
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
                story_title=main_article.title,  # Keep full title
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
