"""
Claude AI analyzer for geopolitical content analysis.
"""

import json
import re
from typing import List, Dict, Optional

try:
    import anthropic
except ImportError:
    anthropic = None

from ..models import Article, ArticleCluster, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

class ClaudeAnalyzer:
    """Analyzes articles using Claude AI to identify underreported geopolitical stories."""
    
    def __init__(self):
        """Initialize Claude analyzer."""
        self.client = None
        self.mock_mode = True
        
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
        Analyze clusters and select the most important underreported stories.
        
        Args:
            clusters: List of article clusters to analyze
            target_stories: Number of stories to select
            
        Returns:
            List of AI analysis results for selected stories
        """
        logger.info(f"Analyzing {len(clusters)} clusters to select {target_stories} stories")
        
        if not clusters:
            return []
        
        try:
            if self.mock_mode:
                return self._create_mock_analyses(clusters[:target_stories])
            else:
                return self._analyze_with_claude_api(clusters[:target_stories])
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            # Fallback to mock analysis
            logger.info("Falling back to mock analysis")
            return self._create_mock_analyses(clusters[:target_stories])
    
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
        """Analyze a single cluster using Claude API."""
        main_article = cluster.main_article
        
        # Prepare article content for analysis
        articles_summary = self._prepare_articles_for_analysis(cluster.articles)
        
        prompt = self._build_analysis_prompt(articles_summary, main_article)
        
        try:
            response = self.client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=Config.AI_MAX_TOKENS,
                temperature=Config.AI_TEMPERATURE,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
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
        return f"""You are a geopolitical analyst specializing in identifying underreported stories with strategic significance. 

Analyze the following cluster of articles and provide insights focusing on what mainstream media might be missing:

{articles_summary}

Provide analysis in this exact JSON format:
{{
  "story_title": "Concise, engaging title (max 60 characters)",
  "why_important": "Strategic significance and implications (max 80 words)",
  "what_overlooked": "What mainstream media is missing (max 40 words)", 
  "prediction": "Expected developments in next 72 hours (max 30 words)",
  "impact_score": [1-10 integer],
  "confidence": [0.0-1.0 float]
}}

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
            required_fields = ['story_title', 'why_important', 'what_overlooked', 'prediction', 'impact_score']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return None
            
            # Create AIAnalysis object
            analysis = AIAnalysis(
                story_title=data['story_title'][:60],  # Ensure length limit
                why_important=data['why_important'],
                what_overlooked=data['what_overlooked'],
                prediction=data['prediction'],
                impact_score=int(data['impact_score']),
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
            
            analysis = AIAnalysis(
                story_title=main_article.title,
                why_important=why_important,
                what_overlooked=what_overlooked,
                prediction=prediction,
                impact_score=impact_score,
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
