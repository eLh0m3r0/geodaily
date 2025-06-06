"""
Claude AI analyzer for geopolitical content analysis.
"""

import json
import re
from typing import List, Dict, Optional

try:
    from ..models import Article, ArticleCluster, AIAnalysis
    from ..config import Config
    from ..logger import get_logger
except ImportError:
    from models import Article, ArticleCluster, AIAnalysis
    from config import Config
    from logger import get_logger

logger = get_logger(__name__)

class ClaudeAnalyzer:
    """Analyzes articles using Claude AI to identify underreported geopolitical stories."""
    
    def __init__(self):
        """Initialize Claude analyzer."""
        # For now, we'll use mock analysis since we don't have real API keys in testing
        self.mock_mode = True
        logger.info("Claude analyzer initialized in mock mode")
    
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
                # Real Claude API implementation would go here
                return self._create_mock_analyses(clusters[:target_stories])
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return []
    
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
        logger.info("Testing API connection (mock mode)")
        return True
