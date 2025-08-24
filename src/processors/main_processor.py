"""
Main processor that coordinates all data processing steps.
"""

from typing import List
import time

from ..models import Article, ArticleCluster, ProcessingStats
from ..logger import get_logger
from .deduplicator import ArticleDeduplicator

logger = get_logger(__name__)

class MainProcessor:
    """Main processor that coordinates all data processing."""
    
    def __init__(self):
        """Initialize processor with all components."""
        self.deduplicator = ArticleDeduplicator()
        self.stats = ProcessingStats()
    
    def process_articles(self, raw_articles: List[Article]) -> List[ArticleCluster]:
        """
        Process raw articles through the complete pipeline.
        
        Args:
            raw_articles: Raw articles from collection
            
        Returns:
            List of processed and scored article clusters
        """
        start_time = time.time()
        logger.info(f"Starting processing pipeline with {len(raw_articles)} raw articles")
        
        # Update stats
        self.stats.total_articles_collected = len(raw_articles)
        
        try:
            # Step 1: Deduplication
            logger.info("Step 1: Deduplicating articles...")
            unique_articles = self.deduplicator.deduplicate_articles(raw_articles)
            self.stats.articles_after_deduplication = len(unique_articles)
            logger.info(f"After deduplication: {len(unique_articles)} unique articles")
            
            # Step 2: Basic relevance scoring (simplified)
            logger.info("Step 2: Scoring articles for relevance...")
            scored_articles = self._score_articles_basic(unique_articles)
            logger.info("Articles scored for relevance")
            
            # Step 3: Clustering
            logger.info("Step 3: Clustering similar articles...")
            clusters = self.deduplicator.cluster_articles(scored_articles)
            self.stats.clusters_created = len(clusters)
            logger.info(f"Created {len(clusters)} clusters")
            
            # Step 4: Cluster scoring and ranking
            logger.info("Step 4: Scoring and ranking clusters...")
            ranked_clusters = self._rank_clusters(clusters)
            logger.info("Clusters ranked by relevance")
            
            # Update final stats
            self.stats.processing_time_seconds = time.time() - start_time
            
            logger.info(f"Processing completed in {self.stats.processing_time_seconds:.2f}s")
            logger.info(f"Deduplication rate: {self.stats.deduplication_rate:.2%}")
            
            return ranked_clusters
            
        except Exception as e:
            error_msg = f"Error in processing pipeline: {e}"
            logger.error(error_msg)
            self.stats.errors.append(error_msg)
            return []
    
    def _score_articles_basic(self, articles: List[Article]) -> List[Article]:
        """Apply basic relevance scoring to articles."""
        
        # High-priority keywords for geopolitical relevance
        high_priority_keywords = {
            'china', 'taiwan', 'russia', 'ukraine', 'nato', 'sanctions',
            'nuclear', 'energy', 'cyber', 'diplomacy', 'military',
            'trade war', 'semiconductor', 'arctic', 'middle east'
        }
        
        # Medium-priority keywords
        medium_priority_keywords = {
            'election', 'democracy', 'economy', 'climate', 'migration',
            'terrorism', 'africa', 'asia', 'europe', 'g7', 'g20'
        }
        
        for article in articles:
            score = 0.0
            content = f"{article.title} {article.summary}".lower()
            
            # Source category weight
            source_weights = {
                'think_tank': 1.3,
                'analysis': 1.1,
                'regional': 1.0,
                'mainstream': 0.8
            }
            score += source_weights.get(article.source_category.value, 1.0)
            
            # Keyword scoring
            for keyword in high_priority_keywords:
                if keyword in content:
                    score += 1.0
            
            for keyword in medium_priority_keywords:
                if keyword in content:
                    score += 0.5
            
            # Title length bonus (prefer meaningful titles)
            title_words = len(article.title.split())
            if 5 <= title_words <= 15:
                score += 0.5
            
            # Summary quality bonus
            if article.summary and len(article.summary) > 100:
                score += 0.3
            
            article.relevance_score = score
        
        # Sort by relevance score
        articles.sort(key=lambda a: a.relevance_score, reverse=True)
        return articles
    
    def _rank_clusters(self, clusters: List[ArticleCluster]) -> List[ArticleCluster]:
        """Rank clusters by overall relevance and quality."""
        
        for cluster in clusters:
            score = 0.0
            
            # Main article relevance
            if cluster.main_article:
                score += cluster.main_article.relevance_score
            
            # Cluster size bonus
            score += len(cluster.articles) * 0.1
            
            # Source diversity bonus
            unique_sources = len(set(a.source for a in cluster.articles))
            score += unique_sources * 0.2
            
            # Average relevance of all articles
            if cluster.articles:
                avg_relevance = sum(a.relevance_score for a in cluster.articles) / len(cluster.articles)
                score += avg_relevance * 0.5
            
            cluster.cluster_score = score
        
        # Sort by cluster score
        clusters.sort(key=lambda c: c.cluster_score, reverse=True)
        return clusters
    
    def get_processing_summary(self) -> dict:
        """Get a summary of processing statistics."""
        return {
            'total_articles_collected': self.stats.total_articles_collected,
            'articles_after_deduplication': self.stats.articles_after_deduplication,
            'clusters_created': self.stats.clusters_created,
            'deduplication_rate': f"{self.stats.deduplication_rate:.2%}",
            'processing_time_seconds': f"{self.stats.processing_time_seconds:.2f}",
            'errors': self.stats.errors
        }
    
    def get_stats(self) -> ProcessingStats:
        """Get detailed processing statistics."""
        return self.stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = ProcessingStats()
