#!/usr/bin/env python3
"""
Test script to verify RSS collector works with real feeds.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models import NewsSource, SourceCategory, SourceTier
from collectors.rss_collector import RSSCollector
from logger import setup_logger

def test_real_rss_feed():
    """Test with a real RSS feed."""
    logger = setup_logger("test_rss")
    
    # Create a test source
    source = NewsSource(
        name="BBC World",
        url="http://feeds.bbci.co.uk/news/world/rss.xml",
        category=SourceCategory.MAINSTREAM,
        tier=SourceTier.TIER1_RSS,
        weight=0.8
    )
    
    # Create collector and test
    collector = RSSCollector()
    
    logger.info("Testing RSS collection with BBC World feed...")
    articles = collector.collect_from_source(source)
    
    logger.info(f"Collected {len(articles)} articles")
    
    if articles:
        logger.info("Sample article:")
        article = articles[0]
        logger.info(f"  Title: {article.title}")
        logger.info(f"  URL: {article.url}")
        logger.info(f"  Summary: {article.summary[:100]}...")
        logger.info(f"  Published: {article.published_date}")
        logger.info(f"  Source: {article.source}")
    
    return len(articles) > 0

if __name__ == "__main__":
    success = test_real_rss_feed()
    if success:
        print("✅ RSS collector test passed!")
    else:
        print("❌ RSS collector test failed!")
        sys.exit(1)
