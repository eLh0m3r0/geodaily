"""
Tests for data collection modules.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import feedparser

from src.models import NewsSource, SourceCategory, SourceTier, Article
from src.collectors.rss_collector import RSSCollector
from src.collectors.web_scraper import WebScraper
from src.collectors.main_collector import MainCollector

class TestRSSCollector:
    """Test RSS collection functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.collector = RSSCollector()
        self.test_source = NewsSource(
            name="Test RSS Source",
            url="https://example.com/rss.xml",
            category=SourceCategory.MAINSTREAM,
            tier=SourceTier.TIER1_RSS,
            weight=1.0
        )
    
    def test_collector_initialization(self):
        """Test that RSS collector initializes correctly."""
        assert self.collector is not None
        assert hasattr(self.collector, 'session')
    
    @patch('src.collectors.rss_collector.feedparser.parse')
    @patch('requests.Session.get')
    def test_collect_from_source_success(self, mock_get, mock_parse):
        """Test successful RSS collection."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b'<rss>test</rss>'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Mock feedparser response
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article1"
        mock_entry.summary = "Test summary"
        mock_entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        mock_feed = Mock()
        mock_feed.entries = [mock_entry]
        mock_feed.bozo = False
        mock_parse.return_value = mock_feed
        
        # Test collection
        articles = self.collector.collect_from_source(self.test_source)
        
        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        assert articles[0].url == "https://example.com/article1"
        assert articles[0].source == "Test RSS Source"
    
    @patch('requests.Session.get')
    def test_collect_from_source_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = Exception("Network error")
        
        articles = self.collector.collect_from_source(self.test_source)
        
        assert len(articles) == 0
    
    def test_parse_date_with_valid_date(self):
        """Test date parsing with valid date."""
        mock_entry = Mock()
        mock_entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        date = self.collector._parse_date(mock_entry)
        
        assert isinstance(date, datetime)
        assert date.year == 2024
        assert date.month == 1
        assert date.day == 1
    
    def test_parse_date_with_no_date(self):
        """Test date parsing when no date is available."""
        mock_entry = Mock()
        # Remove all date attributes
        for attr in ['published_parsed', 'updated_parsed', 'created_parsed', 
                     'published', 'updated', 'created']:
            if hasattr(mock_entry, attr):
                delattr(mock_entry, attr)
        
        date = self.collector._parse_date(mock_entry)
        
        assert isinstance(date, datetime)
        # Should default to current time
        assert abs((datetime.now(timezone.utc) - date).total_seconds()) < 60

class TestWebScraper:
    """Test web scraping functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scraper = WebScraper()
        self.test_source = NewsSource(
            name="Test Web Source",
            url="https://example.com",
            category=SourceCategory.ANALYSIS,
            tier=SourceTier.TIER2_SCRAPING,
            weight=1.0,
            selectors={
                "container": "article",
                "title": "h2",
                "link": "a",
                "summary": ".summary"
            }
        )
    
    def test_scraper_initialization(self):
        """Test that web scraper initializes correctly."""
        assert self.scraper is not None
        assert hasattr(self.scraper, 'session')
    
    @patch('requests.Session.get')
    def test_collect_from_source_success(self, mock_get):
        """Test successful web scraping."""
        # Mock HTML response
        html_content = """
        <html>
            <body>
                <article>
                    <h2><a href="/article1">Test Article 1</a></h2>
                    <div class="summary">Test summary 1</div>
                </article>
                <article>
                    <h2><a href="/article2">Test Article 2</a></h2>
                    <div class="summary">Test summary 2</div>
                </article>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        articles = self.scraper.collect_from_source(self.test_source)
        
        assert len(articles) == 2
        assert articles[0].title == "Test Article 1"
        assert articles[0].url == "https://example.com/article1"
        assert articles[0].summary == "Test summary 1"
    
    @patch('requests.Session.get')
    def test_collect_from_source_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = Exception("Network error")
        
        articles = self.scraper.collect_from_source(self.test_source)
        
        assert len(articles) == 0

class TestMainCollector:
    """Test main collector coordination."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.collector = MainCollector()
    
    def test_collector_initialization(self):
        """Test that main collector initializes correctly."""
        assert self.collector is not None
        assert hasattr(self.collector, 'rss_collector')
        assert hasattr(self.collector, 'web_scraper')
        assert hasattr(self.collector, 'stats')
    
    @patch('src.config.Config.load_sources')
    def test_parse_sources_config(self, mock_load_sources):
        """Test parsing of sources configuration."""
        mock_config = {
            "tier1_sources": [
                {
                    "name": "Test RSS",
                    "url": "https://example.com/rss",
                    "category": "mainstream",
                    "weight": 0.8
                }
            ],
            "tier2_sources": [
                {
                    "name": "Test Web",
                    "url": "https://example.com",
                    "category": "analysis",
                    "weight": 1.0,
                    "selectors": {"container": "article"}
                }
            ]
        }
        
        sources = self.collector._parse_sources_config(mock_config)
        
        assert len(sources) == 2
        assert sources[0].name == "Test RSS"
        assert sources[0].tier == SourceTier.TIER1_RSS
        assert sources[1].name == "Test Web"
        assert sources[1].tier == SourceTier.TIER2_SCRAPING
