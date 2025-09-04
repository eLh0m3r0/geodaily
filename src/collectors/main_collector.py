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
from .source_health_monitor import source_health_monitor, SourceHealthStatus
from ..performance.connection_pool import performance_optimizer

logger = get_logger(__name__)

class MainCollector:
    """Main collector that coordinates all data collection."""
    
    def __init__(self):
        self.rss_collector = RSSCollector(fetch_full_content=Config.FETCH_FULL_CONTENT)
        self.web_scraper = WebScraper()
        self.stats = ProcessingStats()
        self.health_monitor = source_health_monitor
    
    def collect_all_articles(self) -> List[Article]:
        """
        Collect articles from all configured sources with health monitoring and failover.

        Returns:
            List of all collected articles
        """
        start_time = time.time()
        logger.info("Starting article collection from all sources")

        try:
            # Load sources configuration
            sources_config = Config.load_sources()
            all_sources = self._parse_sources_config(sources_config)

            # Register sources with health monitor
            for source in all_sources:
                self.health_monitor.register_source(source)

            # Set up failover groups by category
            self._setup_failover_groups(all_sources)

            # Get healthy sources for collection
            healthy_sources = self.health_monitor.get_healthy_sources(all_sources)

            logger.info(f"Loaded {len(all_sources)} sources, {len(healthy_sources)} healthy for collection")

            if len(healthy_sources) < 3:
                logger.warning("Low number of healthy sources available",
                             structured_data={
                                 'total_sources': len(all_sources),
                                 'healthy_sources': len(healthy_sources),
                                 'threshold': 3
                             })

            # Collect articles from healthy sources in parallel
            all_articles = self._collect_parallel(healthy_sources)

            # Update stats
            self.stats.total_articles_collected = len(all_articles)
            self.stats.sources_attempted = len(healthy_sources)
            self.stats.processing_time_seconds = time.time() - start_time

            logger.info(f"Collection completed: {len(all_articles)} articles from {len(healthy_sources)} sources in {self.stats.processing_time_seconds:.2f}s")

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
        """Collect articles from sources in parallel with performance optimization."""
        all_articles = []

        # Optimize batch size and worker count
        max_workers = min(len(sources), 10)  # Limit concurrent requests
        batch_size = performance_optimizer.optimize_collection_batch_size(len(sources), max_workers)

        logger.info("Starting optimized parallel collection",
                   structured_data={
                       'total_sources': len(sources),
                       'max_workers': max_workers,
                       'batch_size': batch_size
                   })

        # Use enhanced thread pool executor
        with performance_optimizer.create_optimized_thread_pool(max_workers=max_workers) as executor:
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

        # Log performance statistics
        thread_pool_stats = executor.get_stats()
        logger.info("Parallel collection completed",
                   structured_data={
                       'articles_collected': len(all_articles),
                       'thread_pool_stats': thread_pool_stats
                   })

        return all_articles
    
    def _collect_from_single_source(self, source: NewsSource) -> List[Article]:
        """Collect articles from a single source with health monitoring."""
        start_time = time.time()
        articles = []
        success = False
        error_type = None

        try:
            if source.tier == SourceTier.TIER1_RSS:
                articles = self.rss_collector.collect_from_source(source)
            elif source.tier == SourceTier.TIER2_SCRAPING:
                articles = self.web_scraper.collect_from_source(source)
            else:
                logger.warning(f"Unknown source tier for {source.name}: {source.tier}")
                error_type = "unknown_tier"
                return []

            success = True
            response_time = time.time() - start_time

            logger.debug(f"Successfully collected {len(articles)} articles from {source.name}",
                        structured_data={
                            'source_name': source.name,
                            'articles_count': len(articles),
                            'response_time': response_time
                        })

        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__.lower()
            logger.error(f"Error collecting from {source.name}: {e}",
                        structured_data={
                            'source_name': source.name,
                            'error_type': error_type,
                            'response_time': response_time
                        })

        # Record health metrics
        self.health_monitor.record_request_result(
            source_name=source.name,
            success=success,
            response_time=response_time,
            error_type=error_type
        )

        return articles
    
    def get_stats(self) -> ProcessingStats:
        """Get collection statistics."""
        return self.stats

    def reset_stats(self):
        """Reset collection statistics."""
        self.stats = ProcessingStats()

    def _setup_failover_groups(self, sources: List[NewsSource]):
        """Set up failover groups for different source categories."""
        from ..models import SourceCategory

        # Group sources by category
        sources_by_category = {}
        for source in sources:
            if source.category not in sources_by_category:
                sources_by_category[source.category] = []
            sources_by_category[source.category].append(source)

        # Set up failover for each category
        for category, category_sources in sources_by_category.items():
            self.health_monitor.setup_failover_groups(category, category_sources)

        logger.info("Failover groups configured",
                   structured_data={
                       'categories': len(sources_by_category),
                       'total_sources': len(sources)
                   })

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report for all sources."""
        return self.health_monitor.get_health_report()
