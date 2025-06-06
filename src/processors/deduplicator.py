"""
Article deduplication and clustering functionality.
"""

import re
from typing import List, Dict, Set, Tuple
from difflib import SequenceMatcher
from collections import defaultdict
import hashlib

try:
    from ..models import Article, ArticleCluster
    from ..logger import get_logger
except ImportError:
    from models import Article, ArticleCluster
    from logger import get_logger

logger = get_logger(__name__)

class ArticleDeduplicator:
    """Handles deduplication and clustering of articles."""
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize deduplicator.
        
        Args:
            similarity_threshold: Minimum similarity score to consider articles duplicates
        """
        self.similarity_threshold = similarity_threshold
    
    def deduplicate_articles(self, articles: List[Article]) -> List[Article]:
        """
        Remove duplicate articles based on title and content similarity.
        
        Args:
            articles: List of articles to deduplicate
            
        Returns:
            List of unique articles
        """
        if not articles:
            return []
        
        logger.info(f"Starting deduplication of {len(articles)} articles")
        
        # First pass: exact URL duplicates
        unique_articles = self._remove_exact_url_duplicates(articles)
        logger.info(f"After URL deduplication: {len(unique_articles)} articles")
        
        # Second pass: title similarity
        unique_articles = self._remove_similar_titles(unique_articles)
        logger.info(f"After title deduplication: {len(unique_articles)} articles")
        
        return unique_articles
    
    def cluster_articles(self, articles: List[Article]) -> List[ArticleCluster]:
        """
        Group similar articles into clusters.
        
        Args:
            articles: List of articles to cluster
            
        Returns:
            List of article clusters
        """
        if not articles:
            return []
        
        logger.info(f"Starting clustering of {len(articles)} articles")
        
        clusters = []
        processed_articles = set()
        
        for i, article in enumerate(articles):
            if id(article) in processed_articles:
                continue
            
            # Create new cluster with this article as the main one
            cluster_articles = [article]
            processed_articles.add(id(article))
            
            # Find similar articles
            for j, other_article in enumerate(articles[i+1:], i+1):
                if id(other_article) in processed_articles:
                    continue
                
                similarity = self._calculate_title_similarity(article.title, other_article.title)
                if similarity >= self.similarity_threshold * 0.7:  # Lower threshold for clustering
                    cluster_articles.append(other_article)
                    processed_articles.add(id(other_article))
            
            # Create cluster if we have multiple articles or if it's a high-quality single article
            if len(cluster_articles) > 1 or self._is_high_quality_article(article):
                cluster = ArticleCluster(
                    cluster_id=f"cluster_{len(clusters)}",
                    articles=cluster_articles,
                    main_article=self._select_best_article(cluster_articles),
                    cluster_score=self._calculate_cluster_score(cluster_articles)
                )
                clusters.append(cluster)
        
        logger.info(f"Created {len(clusters)} clusters")
        return clusters
    
    def _remove_exact_url_duplicates(self, articles: List[Article]) -> List[Article]:
        """Remove articles with identical URLs."""
        seen_urls = set()
        unique_articles = []
        
        for article in articles:
            normalized_url = self._normalize_url(article.url)
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                unique_articles.append(article)
        
        return unique_articles
    
    def _remove_similar_titles(self, articles: List[Article]) -> List[Article]:
        """Remove articles with very similar titles."""
        unique_articles = []
        
        for article in articles:
            is_duplicate = False
            
            for existing_article in unique_articles:
                similarity = self._calculate_title_similarity(article.title, existing_article.title)
                if similarity >= self.similarity_threshold:
                    # Keep the article from a higher-weight source
                    if self._get_source_weight(article) > self._get_source_weight(existing_article):
                        # Replace existing article with this one
                        unique_articles.remove(existing_article)
                        unique_articles.append(article)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_articles.append(article)
        
        return unique_articles
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        # Normalize titles
        norm_title1 = self._normalize_title(title1)
        norm_title2 = self._normalize_title(title2)
        
        # Use SequenceMatcher for similarity
        similarity = SequenceMatcher(None, norm_title1, norm_title2).ratio()
        
        return similarity
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Convert to lowercase
        title = title.lower()
        
        # Remove common punctuation and extra spaces
        title = re.sub(r'[^\w\s]', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove common stop words that don't affect meaning
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [word for word in title.split() if word not in stop_words]
        
        return ' '.join(words)
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        # Remove common tracking parameters
        url = re.sub(r'[?&](utm_|fbclid|gclid|ref=)', '', url)
        
        # Remove trailing slash
        url = url.rstrip('/')
        
        # Convert to lowercase
        url = url.lower()
        
        return url
    
    def _get_source_weight(self, article: Article) -> float:
        """Get weight of article's source category."""
        weights = {
            'think_tank': 1.3,
            'analysis': 1.1,
            'regional': 1.0,
            'mainstream': 0.8
        }
        return weights.get(article.source_category.value, 1.0)
    
    def _select_best_article(self, articles: List[Article]) -> Article:
        """Select the best article from a cluster to be the main one."""
        if len(articles) == 1:
            return articles[0]
        
        # Score articles based on various factors
        best_article = articles[0]
        best_score = self._calculate_article_quality_score(best_article)
        
        for article in articles[1:]:
            score = self._calculate_article_quality_score(article)
            if score > best_score:
                best_score = score
                best_article = article
        
        return best_article
    
    def _calculate_article_quality_score(self, article: Article) -> float:
        """Calculate quality score for an article."""
        score = 0.0
        
        # Source weight
        score += self._get_source_weight(article)
        
        # Title length (prefer meaningful titles)
        title_length = len(article.title.split())
        if 5 <= title_length <= 15:
            score += 0.5
        
        # Summary length (prefer articles with good summaries)
        if article.summary and len(article.summary) > 100:
            score += 0.3
        
        return score
    
    def _calculate_cluster_score(self, articles: List[Article]) -> float:
        """Calculate overall score for a cluster."""
        if not articles:
            return 0.0
        
        # Base score from number of articles
        score = len(articles) * 0.1
        
        # Add quality scores of all articles
        for article in articles:
            score += self._calculate_article_quality_score(article)
        
        # Bonus for diverse sources
        unique_sources = len(set(article.source for article in articles))
        score += unique_sources * 0.2
        
        return score
    
    def _is_high_quality_article(self, article: Article) -> bool:
        """Determine if a single article is high quality enough to form its own cluster."""
        score = self._calculate_article_quality_score(article)
        return score >= 1.0  # Lower threshold for testing
