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
    # Perspective axis for multi-perspective coverage analysis, e.g.
    # western_mainstream, western_analysis, east_asia, chinese_state,
    # south_asia, middle_east, iranian_state, turkish_state, russian_state,
    # russian_exile, african, latam, global_south, intl_org
    perspective: str = "western_mainstream"
    # True for outlets under state editorial control or state funding —
    # cited as framing data with a visible label, never as sole source of fact
    state_affiliated: bool = False
    # 1 = high reliability, 2 = standard, 3 = use with care / framing-only
    reliability_tier: int = 2

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
    source_weight: float = 1.0  # per-source quality weight from sources.json
    source_perspective: str = "western_mainstream"  # perspective axis of the source
    state_affiliated: bool = False  # source under state editorial control/funding
    content: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    # Content enrichment fields
    full_content: Optional[str] = None
    content_quality_score: float = 0.0
    extraction_method: Optional[str] = None
    word_count: int = 0
    
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
    # Geopolitical structure fields
    region: str = "global"       # europe|middle_east|indo_pacific|americas|africa|central_asia|global
    actor_type: str = "state"    # state|non_state|international_org|mixed
    event_type: str = "political" # diplomatic|military|economic|informational_cyber|humanitarian|political
    # Coverage DNA, computed from the story's event cluster without any AI
    # call: perspective group -> article count, and distinct outlet total.
    # Rendered as the mini coverage bar on stories without the full grid.
    coverage_counts: Dict[str, int] = field(default_factory=dict)
    coverage_outlets: int = 0
    
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
class QuickHit:
    """One-sentence world-roundup item ("Also today" section)."""
    text: str
    region: str = "global"
    url: str = ""

    def __post_init__(self):
        if len(self.text.split()) > 40:
            self.text = " ".join(self.text.split()[:40]) + "..."


@dataclass
class BigNumber:
    """Delight element: one striking number from today's news with context."""
    value: str          # e.g. "35 %"
    context: str        # one sentence explaining the number
    url: str = ""


@dataclass
class PerspectiveView:
    """How one perspective group covers the big story."""
    perspective: str                 # axis key, e.g. "chinese_state"
    outlets: List[str] = field(default_factory=list)
    article_count: int = 0
    framing: str = ""                # one sentence: how this group frames it
    quote: str = ""                  # verbatim quote from one of the articles
    quote_outlet: str = ""
    quote_url: str = ""
    state_affiliated: bool = False


@dataclass
class PerspectiveGrid:
    """Coverage-transparency block for the big story."""
    views: List[PerspectiveView] = field(default_factory=list)
    total_outlets: int = 0
    counts: Dict[str, int] = field(default_factory=dict)  # perspective -> outlet count
    blindspot: str = ""              # 1-2 sentences on what almost nobody covers
    blindspot_url: str = ""


@dataclass
class Signal:
    """External data point (prediction market odds, news-volume trend)."""
    text: str
    url: str = ""
    source: str = ""                 # "Polymarket", "GDELT"


@dataclass
class IssueContent:
    """Full analyzer output for one issue: deep stories + roundup + delight."""
    stories: List[AIAnalysis] = field(default_factory=list)
    quick_hits: List[QuickHit] = field(default_factory=list)
    big_number: Optional[BigNumber] = None
    # Inbox craft: a dedicated short subject (not the headline) and a
    # preheader teaser — subject/headline/snippet must not repeat each other
    email_subject: str = ""
    preheader: str = ""


@dataclass
class Newsletter:
    """Complete newsletter data."""
    date: datetime
    title: str
    stories: List[AIAnalysis]
    intro_text: str = ""
    footer_text: str = ""
    quick_hits: List[QuickHit] = field(default_factory=list)
    big_number: Optional[BigNumber] = None
    perspective_grid: Optional[PerspectiveGrid] = None
    signals: List[Signal] = field(default_factory=list)
    email_subject: str = ""
    preheader: str = ""

    def __post_init__(self):
        # Story order is editorial: the analyzer ranks them and the first
        # carries the perspective grid — never re-sort by score here.
        pass

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
