"""
Main collector that coordinates data collection from all sources.
"""

from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from ..models import Article, NewsSource, SourceTier, SourceCategory, ProcessingStats
from ..config import Config
from ..logger import get_logger
from .rss_collector import RSSCollector
from .web_scraper import WebScraper

logger = get_logger(__name__)

class MainCollector:
    """Main collector that coordinates all data collection."""
    
    def __init__(self):
        self.rss_collector = RSSCollector()
        self.web_scraper = WebScraper()
        self.stats = ProcessingStats()
    
    def collect_all_articles(self) -> List[Article]:
        """
        Collect articles from all configured sources.
        
        Returns:
            List of all collected articles
        """
        start_time = time.time()
        logger.info("Starting article collection from all sources")
        
        try:
            # Load sources configuration
            sources_config = Config.load_sources()
            sources = self._parse_sources_config(sources_config)
            
            logger.info(f"Loaded {len(sources)} sources for collection")
            
            # Collect articles from all sources in parallel
            all_articles = self._collect_parallel(sources)
            
            # Update stats
            self.stats.total_articles_collected = len(all_articles)
            self.stats.processing_time_seconds = time.time() - start_time
            
            logger.info(f"Collection completed: {len(all_articles)} articles in {self.stats.processing_time_seconds:.2f}s")
            
            return all_articles
            
        except Exception as e:
            error_msg = f"Error in article collection: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            return []
    
    def _parse_sources_config(self, config: Dict[str, Any]) -> List[NewsSource]:
        """Parse sources configuration into NewsSource objects."""
        sources = []
        
        # Parse Tier 1 sources (RSS)
        for source_config in config.get('tier1_sources', []):
            try:
                source = NewsSource(
                    name=source_config['name'],
                    url=source_config['url'],
                    category=SourceCategory(source_config['category']),
                    tier=SourceTier.TIER1_RSS,
                    weight=source_config.get('weight', 1.0),
                    method='rss'
                )
                sources.append(source)
            except Exception as e:
                logger.error(f"Error parsing Tier 1 source {source_config.get('name', 'unknown')}: {e}")
        
        # Parse Tier 2 sources (Web scraping)
        for source_config in config.get('tier2_sources', []):
            try:
                source = NewsSource(
                    name=source_config['name'],
                    url=source_config['url'],
                    category=SourceCategory(source_config['category']),
                    tier=SourceTier.TIER2_SCRAPING,
                    weight=source_config.get('weight', 1.0),
                    method=source_config.get('method', 'basic'),
                    selectors=source_config.get('selectors')
                )
                sources.append(source)
            except Exception as e:
                logger.error(f"Error parsing Tier 2 source {source_config.get('name', 'unknown')}: {e}")
        
        return sources
    
    def _collect_parallel(self, sources: List[NewsSource]) -> List[Article]:
        """Collect articles from sources in parallel."""
        all_articles = []
        
        # Use ThreadPoolExecutor for parallel collection
        max_workers = min(len(sources), 10)  # Limit concurrent requests
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit collection tasks
            future_to_source = {
                executor.submit(self._collect_from_single_source, source): source
                for source in sources
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    articles = future.result(timeout=Config.REQUEST_TIMEOUT * 2)
                    all_articles.extend(articles)
                    logger.info(f"Collected {len(articles)} articles from {source.name}")
                except Exception as e:
                    error_msg = f"Error collecting from {source.name}: {e}"
                    logger.error(error_msg)
                    self.stats.errors.append(error_msg)
        
        return all_articles
    
    def _collect_from_single_source(self, source: NewsSource) -> List[Article]:
        """Collect articles from a single source."""
        try:
            if source.tier == SourceTier.TIER1_RSS:
                return self.rss_collector.collect_from_source(source)
            elif source.tier == SourceTier.TIER2_SCRAPING:
                return self.web_scraper.collect_from_source(source)
            else:
                logger.warning(f"Unknown source tier for {source.name}: {source.tier}")
                return []
        except Exception as e:
            logger.error(f"Error collecting from {source.name}: {e}")
            return []
    
    def get_stats(self) -> ProcessingStats:
        """Get collection statistics."""
        return self.stats
    
    def reset_stats(self):
        """Reset collection statistics."""
        self.stats = ProcessingStats()
