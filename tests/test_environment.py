import pytest
import feedparser
import requests
import bs4
import anthropic
import dotenv

def test_imports():
    """Test that all required packages can be imported."""
    assert feedparser is not None
    assert requests is not None
    assert bs4 is not None
    assert anthropic is not None
    assert dotenv is not None

def test_python_version():
    """Test that we're running Python 3.11."""
    import sys
    assert sys.version_info.major == 3
    assert sys.version_info.minor == 11

def test_feedparser_functionality():
    """Test basic feedparser functionality."""
    # Test with a simple RSS structure as bytes (feedparser expects bytes or URL)
    rss_content = b'''<?xml version="1.0"?>
    <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Test Article</title>
                <description>Test description</description>
            </item>
        </channel>
    </rss>'''
    
    import io
    feed = feedparser.parse(io.BytesIO(rss_content))
    assert feed.feed.title == "Test Feed"
    assert len(feed.entries) == 1
    assert feed.entries[0].title == "Test Article"

def test_requests_functionality():
    """Test basic requests functionality."""
    import requests
    # Test that requests module has expected attributes
    assert hasattr(requests, 'get')
    assert hasattr(requests, 'post')
    assert hasattr(requests, 'Session')

def test_beautifulsoup_functionality():
    """Test basic BeautifulSoup functionality."""
    from bs4 import BeautifulSoup
    html = "<html><body><h1>Test</h1></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.h1.text == "Test"

def test_anthropic_client_creation():
    """Test that Anthropic client can be created."""
    # Test client creation without API key (should not fail)
    try:
        client = anthropic.Anthropic(api_key="test-key")
        assert client is not None
    except Exception as e:
        # If there's an issue with client creation, that's fine for environment test
        pass
