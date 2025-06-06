#!/usr/bin/env python3
"""
Test script to verify deduplication works.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from collectors.main_collector import MainCollector
from processors.deduplicator import ArticleDeduplicator
from logger import setup_logger

def test_deduplication():
    """Test deduplication functionality."""
    logger = setup_logger("test_dedup")
    
    logger.info("=== Testing Article Deduplication ===")
    
    # Step 1: Collect articles
    logger.info("Step 1: Collecting articles...")
    collector = MainCollector()
    raw_articles = collector.collect_all_articles()
    
    logger.info(f"Collected {len(raw_articles)} raw articles")
    
    if not raw_articles:
        logger.error("No articles to test with!")
        return False
    
    # Step 2: Test deduplication
    logger.info("Step 2: Testing deduplication...")
    deduplicator = ArticleDeduplicator()
    unique_articles = deduplicator.deduplicate_articles(raw_articles)
    
    dedup_rate = (len(raw_articles) - len(unique_articles)) / len(raw_articles)
    logger.info(f"Deduplication results:")
    logger.info(f"  - Original articles: {len(raw_articles)}")
    logger.info(f"  - Unique articles: {len(unique_articles)}")
    logger.info(f"  - Deduplication rate: {dedup_rate:.2%}")
    
    # Step 3: Test clustering
    logger.info("Step 3: Testing clustering...")
    clusters = deduplicator.cluster_articles(unique_articles[:50])  # Test with subset for speed
    
    logger.info(f"Clustering results:")
    logger.info(f"  - Input articles: {min(50, len(unique_articles))}")
    logger.info(f"  - Clusters created: {len(clusters)}")
    
    if clusters:
        logger.info("Sample clusters:")
        for i, cluster in enumerate(clusters[:3], 1):
            logger.info(f"  {i}. Cluster {cluster.cluster_id} (score: {cluster.cluster_score:.2f})")
            logger.info(f"     Main article: {cluster.main_article.title}")
            logger.info(f"     Articles in cluster: {len(cluster.articles)}")
            if len(cluster.articles) > 1:
                logger.info(f"     Other articles:")
                for article in cluster.articles[1:]:
                    logger.info(f"       - {article.title} ({article.source})")
            logger.info("")
    
    return len(unique_articles) > 0 and len(clusters) > 0

if __name__ == "__main__":
    success = test_deduplication()
    if success:
        print("✅ Deduplication test passed!")
    else:
        print("❌ Deduplication test failed!")
        sys.exit(1)
