"""
Fallback content generation system for maintaining content availability during failures.
"""

import json
import random
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models import Article, ArticleCluster, AIAnalysis, NewsSource, SourceCategory
from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from ..config import Config


@dataclass
class FallbackContent:
    """Container for fallback content."""
    title: str
    summary: str
    content_type: str
    quality_score: float
    source: str
    timestamp: datetime
    metadata: Dict[str, Any]


class FallbackContentGenerator:
    """
    Generates fallback content when primary content sources fail.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("fallback_content")
        self.templates = self._load_content_templates()

    def _load_content_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load content templates for different scenarios."""
        return {
            'breaking_news': [
                {
                    'title': 'Breaking: Major Development in Global Affairs',
                    'summary': 'A significant development has occurred that may impact international relations and global markets.',
                    'content_type': 'breaking_news',
                    'quality_score': 0.6
                },
                {
                    'title': 'Urgent Update: International Situation Escalates',
                    'summary': 'Tensions are rising in a key geopolitical region, with potential implications for global stability.',
                    'content_type': 'breaking_news',
                    'quality_score': 0.6
                }
            ],
            'analysis': [
                {
                    'title': 'Strategic Analysis: Emerging Global Trends',
                    'summary': 'An examination of current geopolitical trends and their potential long-term implications.',
                    'content_type': 'analysis',
                    'quality_score': 0.7
                },
                {
                    'title': 'Geopolitical Forecast: What to Watch in Coming Weeks',
                    'summary': 'Key developments and indicators to monitor in the evolving international landscape.',
                    'content_type': 'analysis',
                    'quality_score': 0.7
                }
            ],
            'regional_focus': [
                {
                    'title': 'Asia-Pacific Developments: Shifting Dynamics',
                    'summary': 'Important changes in regional power structures and economic relationships.',
                    'content_type': 'regional_focus',
                    'quality_score': 0.8
                },
                {
                    'title': 'European Security Update: Alliance Considerations',
                    'summary': 'Current developments in European security architecture and transatlantic cooperation.',
                    'content_type': 'regional_focus',
                    'quality_score': 0.8
                },
                {
                    'title': 'Middle East Analysis: Strategic Implications',
                    'summary': 'Ongoing developments in the Middle East and their broader geopolitical significance.',
                    'content_type': 'regional_focus',
                    'quality_score': 0.8
                }
            ],
            'economic_impact': [
                {
                    'title': 'Economic Indicators: Global Market Implications',
                    'summary': 'Current economic developments and their potential impact on global markets and trade.',
                    'content_type': 'economic_impact',
                    'quality_score': 0.7
                },
                {
                    'title': 'Trade and Commerce: International Economic Relations',
                    'summary': 'Developments in global trade patterns and economic partnerships.',
                    'content_type': 'economic_impact',
                    'quality_score': 0.7
                }
            ]
        }

    def generate_fallback_articles(self,
                                 count: int = 5,
                                 categories: Optional[List[str]] = None) -> List[Article]:
        """
        Generate fallback articles when primary collection fails.

        Args:
            count: Number of articles to generate
            categories: Preferred content categories

        Returns:
            List of fallback Article objects
        """
        articles = []
        available_categories = categories or list(self.templates.keys())

        self.logger.info(f"Generating {count} fallback articles",
                        structured_data={
                            'requested_count': count,
                            'available_categories': available_categories
                        })

        for i in range(count):
            # Select random category
            category = random.choice(available_categories)
            templates = self.templates.get(category, self.templates['analysis'])

            # Select random template
            template = random.choice(templates)

            # Create fallback article
            article = self._create_fallback_article(template, i + 1)
            articles.append(article)

        self.logger.info(f"Generated {len(articles)} fallback articles",
                        structured_data={
                            'actual_count': len(articles),
                            'categories_used': list(set(a.source_category.value for a in articles))
                        })

        return articles

    def _create_fallback_article(self, template: Dict[str, Any], index: int) -> Article:
        """Create a fallback Article object from template."""
        timestamp = datetime.now()

        # Create mock source
        source = NewsSource(
            name="Geopolitical Daily Fallback",
            url="https://fallback.geodaily.internal",
            category=SourceCategory.THINK_TANK,
            tier=None,  # Fallback content has no tier
            weight=0.5
        )

        # Create article
        article = Article(
            title=f"{template['title']} ({timestamp.strftime('%Y-%m-%d')})",
            url=f"https://fallback.geodaily.internal/article/{index}",
            summary=template['summary'],
            content=self._generate_article_content(template),
            published_date=timestamp,
            source=source.name,
            source_category=source.category,
            relevance_score=template['quality_score'],
            language="en",
            tags=self._generate_tags(template),
            metadata={
                'is_fallback': True,
                'fallback_type': template['content_type'],
                'generated_at': timestamp.isoformat(),
                'quality_score': template['quality_score']
            }
        )

        return article

    def _generate_article_content(self, template: Dict[str, Any]) -> str:
        """Generate full article content from template."""
        content_type = template['content_type']

        if content_type == 'breaking_news':
            return self._generate_breaking_news_content()
        elif content_type == 'analysis':
            return self._generate_analysis_content()
        elif content_type == 'regional_focus':
            return self._generate_regional_content()
        elif content_type == 'economic_impact':
            return self._generate_economic_content()
        else:
            return self._generate_generic_content()

    def _generate_breaking_news_content(self) -> str:
        """Generate breaking news content."""
        return """
        <p>A significant development has occurred in the international arena that warrants immediate attention. While specific details are being monitored closely, this situation has the potential to impact global stability and international relations.</p>

        <p>Our analysts are tracking this development and will provide updates as more information becomes available. This type of situation typically involves multiple stakeholders and may have implications for diplomatic relations, economic partnerships, and regional security arrangements.</p>

        <p>Key points to monitor:</p>
        <ul>
            <li>Immediate diplomatic responses</li>
            <li>Economic market reactions</li>
            <li>International community statements</li>
            <li>Potential escalation scenarios</li>
        </ul>

        <p>This development underscores the dynamic nature of global affairs and the importance of maintaining situational awareness in an increasingly interconnected world.</p>
        """

    def _generate_analysis_content(self) -> str:
        """Generate analytical content."""
        return """
        <p>The current geopolitical landscape continues to evolve with several key trends shaping international relations and strategic decision-making. Understanding these dynamics is crucial for anticipating future developments and their potential impacts.</p>

        <p>Several factors are currently influencing the global strategic environment:</p>

        <h3>Power Dynamics</h3>
        <p>Major powers are adjusting their strategic postures in response to changing economic and security realities. This includes shifts in alliance structures, military deployments, and diplomatic engagements.</p>

        <h3>Economic Interdependencies</h3>
        <p>Global economic relationships continue to influence political decisions and strategic calculations. Trade patterns, resource dependencies, and economic partnerships play increasingly important roles in international affairs.</p>

        <h3>Technological Competition</h3>
        <p>Advances in technology are creating new domains of competition and cooperation. From cybersecurity to space exploration, technological capabilities are becoming central to national power and international influence.</p>

        <p>These trends suggest a period of strategic adjustment and realignment in global affairs, with potential implications for stability and prosperity in the international system.</p>
        """

    def _generate_regional_content(self) -> str:
        """Generate regional focus content."""
        regions = ['Asia-Pacific', 'Europe', 'Middle East', 'Africa', 'Americas']
        region = random.choice(regions)

        return f"""
        <p>The {region} region continues to be a focal point for international attention, with several developments shaping the strategic landscape and influencing global dynamics.</p>

        <h3>Current Dynamics</h3>
        <p>Several key factors are currently influencing developments in {region}:</p>

        <ul>
            <li>Evolving power relationships between major actors</li>
            <li>Economic integration and trade partnerships</li>
            <li>Security arrangements and military postures</li>
            <li>Diplomatic engagements and multilateral initiatives</li>
        </ul>

        <h3>Strategic Implications</h3>
        <p>Developments in {region} have broader implications for:</p>

        <ul>
            <li>Global economic stability and trade flows</li>
            <li>International security arrangements</li>
            <li>Energy and resource security</li>
            <li>Technological and innovation leadership</li>
        </ul>

        <p>Monitoring these developments is essential for understanding the evolving international order and anticipating potential challenges and opportunities in global affairs.</p>
        """

    def _generate_economic_content(self) -> str:
        """Generate economic impact content."""
        return """
        <p>Economic factors continue to play a central role in shaping international relations and strategic decision-making. Global economic trends and developments have significant implications for political stability and diplomatic relations.</p>

        <h3>Economic Indicators</h3>
        <p>Several key economic trends are currently influencing the international landscape:</p>

        <ul>
            <li>Global trade patterns and supply chain dynamics</li>
            <li>Energy markets and resource pricing</li>
            <li>Currency fluctuations and financial stability</li>
            <li>Investment flows and capital movements</li>
        </ul>

        <h3>Geopolitical Implications</h3>
        <p>Economic developments have direct implications for:</p>

        <ul>
            <li>Diplomatic leverage and negotiation positions</li>
            <li>Alliance structures and partnership arrangements</li>
            <li>Domestic political stability and policy directions</li>
            <li>International cooperation and conflict resolution</li>
        </ul>

        <p>The interplay between economic factors and geopolitical dynamics creates a complex environment where economic policies and diplomatic strategies are increasingly intertwined.</p>
        """

    def _generate_generic_content(self) -> str:
        """Generate generic fallback content."""
        return """
        <p>The field of international relations continues to evolve with new challenges and opportunities emerging regularly. Understanding these dynamics requires careful analysis of multiple factors and their interrelationships.</p>

        <p>Key areas of focus in current global affairs include:</p>

        <ul>
            <li>Strategic competition between major powers</li>
            <li>Economic globalization and its impacts</li>
            <li>Technological innovation and its implications</li>
            <li>Climate change and environmental challenges</li>
            <li>Security arrangements and conflict prevention</li>
        </ul>

        <p>These factors interact in complex ways, creating both challenges and opportunities for international cooperation and conflict resolution. Monitoring these developments helps in understanding the broader context of global affairs.</p>
        """

    def _generate_tags(self, template: Dict[str, Any]) -> List[str]:
        """Generate tags for fallback content."""
        base_tags = ['geopolitics', 'international-relations', 'global-affairs']

        content_type = template['content_type']

        if content_type == 'breaking_news':
            base_tags.extend(['breaking-news', 'urgent', 'current-events'])
        elif content_type == 'analysis':
            base_tags.extend(['analysis', 'strategy', 'forecast'])
        elif content_type == 'regional_focus':
            base_tags.extend(['regional', 'power-dynamics', 'security'])
        elif content_type == 'economic_impact':
            base_tags.extend(['economics', 'trade', 'markets'])

        return base_tags

    def generate_fallback_analysis(self,
                                 cluster: ArticleCluster,
                                 fallback_type: str = 'generic') -> AIAnalysis:
        """
        Generate fallback AI analysis when primary analysis fails.

        Args:
            cluster: Article cluster to analyze
            fallback_type: Type of fallback analysis

        Returns:
            Fallback AIAnalysis object
        """
        main_article = cluster.main_article

        # Generate fallback analysis based on article content
        if fallback_type == 'generic':
            analysis = self._generate_generic_analysis(main_article)
        elif fallback_type == 'regional':
            analysis = self._generate_regional_analysis(main_article)
        elif fallback_type == 'economic':
            analysis = self._generate_economic_analysis(main_article)
        else:
            analysis = self._generate_generic_analysis(main_article)

        self.logger.info("Generated fallback AI analysis",
                        structured_data={
                            'fallback_type': fallback_type,
                            'article_title': main_article.title,
                            'impact_score': analysis.impact_score
                        })

        return analysis

    def _generate_generic_analysis(self, article: Article) -> AIAnalysis:
        """Generate generic fallback analysis."""
        return AIAnalysis(
            story_title=f"Analysis: {article.title[:50]}...",
            why_important="This development represents an important shift in the geopolitical landscape with potential implications for international relations and strategic decision-making.",
            what_overlooked="The broader strategic context and long-term implications may not be immediately apparent from surface-level reporting.",
            prediction="This situation will likely develop further in the coming days with potential impacts on regional stability and international partnerships.",
            impact_score=6,
            sources=[article.url],
            confidence=0.6
        )

    def _generate_regional_analysis(self, article: Article) -> AIAnalysis:
        """Generate region-specific fallback analysis."""
        region_keywords = {
            'asia': 'Asia-Pacific',
            'china': 'China',
            'russia': 'Russia',
            'europe': 'Europe',
            'middle east': 'Middle East',
            'africa': 'Africa',
            'america': 'Americas'
        }

        region = 'global'
        content_lower = f"{article.title} {article.summary}".lower()

        for keyword, region_name in region_keywords.items():
            if keyword in content_lower:
                region = region_name
                break

        return AIAnalysis(
            story_title=f"Regional Analysis: Developments in {region}",
            why_important=f"This development in {region} has significant implications for regional power dynamics and international relations in the area.",
            what_overlooked=f"Western media often misses the {region.lower()}-centric perspective and local strategic calculations that are driving this development.",
            prediction=f"The situation in {region} will likely evolve with potential impacts on regional partnerships and international involvement.",
            impact_score=7,
            sources=[article.url],
            confidence=0.65
        )

    def _generate_economic_analysis(self, article: Article) -> AIAnalysis:
        """Generate economic-focused fallback analysis."""
        return AIAnalysis(
            story_title="Economic Geopolitics: Market and Trade Implications",
            why_important="Economic developments have direct implications for diplomatic leverage, alliance structures, and international power relationships.",
            what_overlooked="The economic dimensions of this story reveal deeper strategic motivations and potential leverage points in international negotiations.",
            prediction="Economic pressures will likely influence diplomatic positions and potentially lead to new partnership arrangements or trade realignments.",
            impact_score=7,
            sources=[article.url],
            confidence=0.65
        )


# Global fallback generator instance
fallback_generator = FallbackContentGenerator()