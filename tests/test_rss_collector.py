"""
Test RSS collector functionality.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models import NewsSource, SourceCategory, SourceTier
from collectors.rss_collector import RSSCollector

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
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        # Test basic cleaning
        text = "  This is   a test  "
        cleaned = self.collector._clean_text(text)
        assert cleaned == "This is a test"
        
        # Test CDATA removal
        text = "[CDATA[This is content]]"
        cleaned = self.collector._clean_text(text)
        assert cleaned == "This is content"
    
    def test_clean_html(self):
        """Test HTML cleaning functionality."""
        html = "<p>This is <strong>bold</strong> text</p>"
        cleaned = self.collector._clean_html(html)
        assert cleaned == "This is bold text"
        
        # Test with empty input
        assert self.collector._clean_html("") == ""
        assert self.collector._clean_html(None) == ""
    
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
    
    @patch('requests.Session.get')
    def test_fetch_feed_with_retry_success(self, mock_get):
        """Test successful feed fetching."""
        mock_response = Mock()
        mock_response.content = b'<rss>test</rss>'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.collector._fetch_feed_with_retry("https://example.com/rss")
        
        assert result == b'<rss>test</rss>'
        mock_get.assert_called_once()
    
    @patch('requests.Session.get')
    def test_fetch_feed_with_retry_failure(self, mock_get):
        """Test feed fetching with network failure."""
        import requests
        mock_get.side_effect = requests.RequestException("Network error")

        result = self.collector._fetch_feed_with_retry("https://example.com/rss")

        assert result is None
        # Should retry MAX_RETRIES times
        assert mock_get.call_count >= 1
    
    def test_parse_rss_entry_success(self):
        """Test successful RSS entry parsing."""
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.summary = "Test summary"
        mock_entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        mock_entry.author = "Test Author"
        
        article = self.collector._parse_rss_entry(mock_entry, self.test_source)
        
        assert article is not None
        assert article.title == "Test Article"
        assert article.url == "https://example.com/article"
        assert article.summary == "Test summary"
        assert article.source == "Test RSS Source"
        assert article.author == "Test Author"
    
    def test_parse_rss_entry_missing_title(self):
        """Test RSS entry parsing with missing title."""
        mock_entry = Mock()
        mock_entry.title = ""
        mock_entry.link = "https://example.com/article"
        
        article = self.collector._parse_rss_entry(mock_entry, self.test_source)
        
        assert article is None
    
    def test_parse_rss_entry_missing_url(self):
        """Test RSS entry parsing with missing URL."""
        mock_entry = Mock()
        mock_entry.title = "Test Article"
        mock_entry.link = ""
        
        article = self.collector._parse_rss_entry(mock_entry, self.test_source)
        
        assert article is None
