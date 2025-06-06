#!/usr/bin/env python3
"""
Test script to verify the complete processing pipeline works.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from collectors.main_collector import MainCollector
from processors.main_processor import MainProcessor
from logger import setup_logger

def test_complete_pipeline():
    """Test the complete collection and processing pipeline."""
    logger = setup_logger("test_pipeline")
    
    logger.info("=== Testing Complete Processing Pipeline ===")
    
    # Step 1: Collect articles
    logger.info("Step 1: Collecting articles from all sources...")
    collector = MainCollector()
    raw_articles = collector.collect_all_articles()
    
    collection_stats = collector.get_stats()
    logger.info(f"Collection completed:")
    logger.info(f"  - Total articles: {collection_stats.total_articles_collected}")
    logger.info(f"  - Collection time: {collection_stats.processing_time_seconds:.2f}s")
    logger.info(f"  - Errors: {len(collection_stats.errors)}")
    
    if not raw_articles:
        logger.error("No articles collected! Check sources and network connectivity.")
        return False
    
    # Step 2: Process articles
    logger.info("Step 2: Processing articles...")
    processor = MainProcessor()
    clusters = processor.process_articles(raw_articles)
    
    processing_stats = processor.get_stats()
    logger.info(f"Processing completed:")
    logger.info(f"  - Articles after deduplication: {processing_stats.articles_after_deduplication}")
    logger.info(f"  - Clusters created: {processing_stats.clusters_created}")
    logger.info(f"  - Deduplication rate: {processing_stats.deduplication_rate:.2%}")
    logger.info(f"  - Processing time: {processing_stats.processing_time_seconds:.2f}s")
    
    # Step 3: Display results
    logger.info("Step 3: Top clusters analysis...")
    
    if clusters:
        logger.info(f"Top {min(5, len(clusters))} clusters:")
        for i, cluster in enumerate(clusters[:5], 1):
            logger.info(f"  {i}. Cluster {cluster.cluster_id} (score: {cluster.cluster_score:.2f})")
            logger.info(f"     Main article: {cluster.main_article.title}")
            logger.info(f"     Source: {cluster.main_article.source}")
            logger.info(f"     Articles in cluster: {len(cluster.articles)}")
            logger.info(f"     URL: {cluster.main_article.url}")
            logger.info("")
    else:
        logger.warning("No clusters created!")
        return False
    
    # Summary
    total_time = collection_stats.processing_time_seconds + processing_stats.processing_time_seconds
    logger.info(f"=== Pipeline Summary ===")
    logger.info(f"Total execution time: {total_time:.2f}s")
    logger.info(f"Articles collected: {collection_stats.total_articles_collected}")
    logger.info(f"Articles after processing: {processing_stats.articles_after_deduplication}")
    logger.info(f"Final clusters: {len(clusters)}")
    logger.info(f"Success rate: {processing_stats.success_rate:.2%}")
    
    return True

if __name__ == "__main__":
    success = test_complete_pipeline()
    if success:
        print("✅ Complete pipeline test passed!")
    else:
        print("❌ Complete pipeline test failed!")
        sys.exit(1)
