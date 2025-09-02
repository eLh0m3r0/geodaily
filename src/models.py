"""
Data models for the Geopolitical Daily newsletter.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class ContentType(Enum):
    """Content types for stories."""
    BREAKING_NEWS = "breaking_news"
    ANALYSIS = "analysis"
    TREND = "trend"

class SourceCategory(Enum):
    """Source categories for news sources."""
    MAINSTREAM = "mainstream"
    ANALYSIS = "analysis"
    REGIONAL = "regional"
    THINK_TANK = "think_tank"

class SourceTier(Enum):
    """Source tiers for different collection methods."""
    TIER1_RSS = "tier1_rss"
    TIER2_SCRAPING = "tier2_scraping"

@dataclass
class NewsSource:
    """Configuration for a news source."""
    name: str
    url: str
    category: SourceCategory
    tier: SourceTier
    weight: float = 1.0
    method: str = "rss"  # rss, basic, api
    selectors: Optional[Dict[str, str]] = None
    enabled: bool = True
    
    def __post_init__(self):
        if isinstance(self.category, str):
            self.category = SourceCategory(self.category)
        if isinstance(self.tier, str):
            self.tier = SourceTier(self.tier)

@dataclass
class Article:
    """Represents a single news article."""
    source: str
    source_category: SourceCategory
    title: str
    url: str
    summary: str
    published_date: datetime
    cluster_id: Optional[str] = None
    relevance_score: float = 0.0
    content: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if isinstance(self.source_category, str):
            self.source_category = SourceCategory(self.source_category)
        
        # Ensure summary is not too long
        if len(self.summary) > 500:
            self.summary = self.summary[:497] + "..."

@dataclass
class ArticleCluster:
    """Represents a cluster of similar articles."""
    cluster_id: str
    articles: List[Article]
    main_article: Article
    cluster_score: float = 0.0
    topic: Optional[str] = None
    
    def __post_init__(self):
        if not self.main_article and self.articles:
            # Select article with highest relevance score as main
            self.main_article = max(self.articles, key=lambda a: a.relevance_score)

@dataclass
class AIAnalysis:
    """AI analysis result for a story."""
    story_title: str
    why_important: str  # 80 words max
    what_overlooked: str  # 40 words max
    prediction: str  # 30 words max
    impact_score: int  # 1-10 (legacy score for backward compatibility)
    sources: List[str]
    content_type: ContentType = ContentType.ANALYSIS
    urgency_score: int = 1  # 1-10
    scope_score: int = 1  # 1-10
    novelty_score: int = 1  # 1-10
    credibility_score: int = 1  # 1-10
    impact_dimension_score: int = 1  # 1-10
    confidence: float = 0.0
    
    def __post_init__(self):
        # Validate word counts
        if len(self.why_important.split()) > 80:
            words = self.why_important.split()[:80]
            self.why_important = " ".join(words) + "..."

        if len(self.what_overlooked.split()) > 40:
            words = self.what_overlooked.split()[:40]
            self.what_overlooked = " ".join(words) + "..."

        if len(self.prediction.split()) > 30:
            words = self.prediction.split()[:30]
            self.prediction = " ".join(words) + "..."

        # Handle content_type
        if isinstance(self.content_type, str):
            self.content_type = ContentType(self.content_type)

        # Validate impact score
        self.impact_score = max(1, min(10, self.impact_score))

        # Validate new multi-dimensional scores
        self.urgency_score = max(1, min(10, self.urgency_score))
        self.scope_score = max(1, min(10, self.scope_score))
        self.novelty_score = max(1, min(10, self.novelty_score))
        self.credibility_score = max(1, min(10, self.credibility_score))
        self.impact_dimension_score = max(1, min(10, self.impact_dimension_score))

@dataclass
class Newsletter:
    """Complete newsletter data."""
    date: datetime
    title: str
    stories: List[AIAnalysis]
    intro_text: str = ""
    footer_text: str = ""
    
    def __post_init__(self):
        # Sort stories by impact score (highest first)
        self.stories.sort(key=lambda s: s.impact_score, reverse=True)

@dataclass
class ProcessingStats:
    """Statistics from the processing pipeline."""
    total_articles_collected: int = 0
    articles_after_deduplication: int = 0
    clusters_created: int = 0
    articles_sent_to_ai: int = 0
    stories_selected: int = 0
    processing_time_seconds: float = 0.0
    sources_attempted: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def deduplication_rate(self) -> float:
        """Calculate deduplication rate."""
        if self.total_articles_collected == 0:
            return 0.0
        return (self.total_articles_collected - self.articles_after_deduplication) / self.total_articles_collected
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_articles_collected == 0:
            return 0.0
        return (self.total_articles_collected - len(self.errors)) / self.total_articles_collected
