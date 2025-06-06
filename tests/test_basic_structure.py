"""
Basic tests to verify project structure and imports.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_config_import():
    """Test that config module can be imported."""
    from config import Config
    assert Config is not None

def test_models_import():
    """Test that models module can be imported."""
    from models import Article, NewsSource, SourceCategory
    assert Article is not None
    assert NewsSource is not None
    assert SourceCategory is not None

def test_logger_import():
    """Test that logger module can be imported."""
    from logger import setup_logger, get_logger
    assert setup_logger is not None
    assert get_logger is not None

def test_sources_file_exists():
    """Test that sources.json file exists and is valid."""
    from config import Config
    sources = Config.load_sources()
    assert 'tier1_sources' in sources
    assert 'tier2_sources' in sources
    assert len(sources['tier1_sources']) > 0

def test_create_news_source():
    """Test creating a NewsSource object."""
    from models import NewsSource, SourceCategory, SourceTier
    
    source = NewsSource(
        name="Test Source",
        url="https://example.com",
        category=SourceCategory.MAINSTREAM,
        tier=SourceTier.TIER1_RSS,
        weight=1.0
    )
    
    assert source.name == "Test Source"
    assert source.category == SourceCategory.MAINSTREAM
    assert source.tier == SourceTier.TIER1_RSS

def test_create_article():
    """Test creating an Article object."""
    from models import Article, SourceCategory
    from datetime import datetime, timezone
    
    article = Article(
        source="Test Source",
        source_category=SourceCategory.MAINSTREAM,
        title="Test Article",
        url="https://example.com/article",
        summary="Test summary",
        published_date=datetime.now(timezone.utc)
    )
    
    assert article.title == "Test Article"
    assert article.source == "Test Source"
    assert article.source_category == SourceCategory.MAINSTREAM
