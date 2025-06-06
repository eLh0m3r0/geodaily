#!/usr/bin/env python3
"""
Simple test script to verify collection works.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from collectors.main_collector import MainCollector
from logger import setup_logger

def test_simple_collection():
    """Test basic collection functionality."""
    logger = setup_logger("test_collection")
    
    logger.info("=== Testing Article Collection ===")
    
    # Test collection
    collector = MainCollector()
    articles = collector.collect_all_articles()
    
    stats = collector.get_stats()
    logger.info(f"Collection results:")
    logger.info(f"  - Total articles: {stats.total_articles_collected}")
    logger.info(f"  - Collection time: {stats.processing_time_seconds:.2f}s")
    logger.info(f"  - Errors: {len(stats.errors)}")
    
    if stats.errors:
        logger.warning("Errors encountered:")
        for error in stats.errors:
            logger.warning(f"  - {error}")
    
    if articles:
        logger.info(f"Sample articles:")
        for i, article in enumerate(articles[:3], 1):
            logger.info(f"  {i}. {article.title}")
            logger.info(f"     Source: {article.source}")
            logger.info(f"     Category: {article.source_category.value}")
            logger.info(f"     URL: {article.url}")
            logger.info("")
    
    return len(articles) > 0

if __name__ == "__main__":
    success = test_simple_collection()
    if success:
        print("✅ Collection test passed!")
    else:
        print("❌ Collection test failed!")
        sys.exit(1)
