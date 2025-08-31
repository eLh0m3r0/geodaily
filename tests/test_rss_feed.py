"""
Test RSS feed generation and validation.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

from src.models import Newsletter, AIAnalysis
from src.publishers.github_pages_publisher import GitHubPagesPublisher


class TestRSSFeed:
    """Test RSS feed generation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.publisher = GitHubPagesPublisher(str(self.temp_dir))

        # Create mock newsletter data
        self.mock_newsletter = Newsletter(
            date=datetime(2025, 1, 15),
            title="Test Newsletter",
            stories=[
                AIAnalysis(
                    story_title="Test Story 1",
                    why_important="This is very important because...",
                    what_overlooked="What was overlooked is...",
                    prediction="What to watch for...",
                    impact_score=8,
                    sources=["https://example.com/1", "https://example.com/2"],
                    confidence=0.85
                ),
                AIAnalysis(
                    story_title="Test Story 2",
                    why_important="Another important development...",
                    what_overlooked="The key aspect missed...",
                    prediction="Future implications include...",
                    impact_score=7,
                    sources=["https://example.com/3"],
                    confidence=0.92
                )
            ],
            intro_text="This is a test newsletter introduction.",
            footer_text="Test footer content."
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_rss_feed_generation(self):
        """Test basic RSS feed generation."""
        # Create a sample newsletter HTML file
        newsletter_html = self._create_sample_newsletter_html()
        newsletter_path = self.temp_dir / "newsletters" / "newsletter-2025-01-15.html"
        newsletter_path.parent.mkdir(parents=True, exist_ok=True)

        with open(newsletter_path, 'w', encoding='utf-8') as f:
            f.write(newsletter_html)

        # Generate RSS feed
        self.publisher._update_rss_feed()

        # Check that RSS feed was created
        rss_path = self.temp_dir / "feed.xml"
        assert rss_path.exists()

        # Read and validate RSS content
        with open(rss_path, 'r', encoding='utf-8') as f:
            rss_content = f.read()

        # Basic validation checks
        assert '<?xml version="1.0" encoding="UTF-8"?>' in rss_content
        assert '<rss version="2.0"' in rss_content
        assert 'xmlns:atom=' in rss_content
        assert 'xmlns:dc=' in rss_content
        assert '<channel>' in rss_content
        assert '<title>' in rss_content
        assert '<link>' in rss_content
        assert '<description>' in rss_content
        assert '<item>' in rss_content
        assert '<guid' in rss_content
        assert '<category>' in rss_content

    def test_rss_xml_validation(self):
        """Test RSS XML validation."""
        # Create sample newsletter
        newsletter_html = self._create_sample_newsletter_html()
        newsletter_path = self.temp_dir / "newsletters" / "newsletter-2025-01-15.html"
        newsletter_path.parent.mkdir(parents=True, exist_ok=True)

        with open(newsletter_path, 'w', encoding='utf-8') as f:
            f.write(newsletter_html)

        # Generate RSS feed
        self.publisher._update_rss_feed()

        # Read RSS content
        rss_path = self.temp_dir / "feed.xml"
        with open(rss_path, 'r', encoding='utf-8') as f:
            rss_content = f.read()

        # Test XML validation
        is_valid = self.publisher._validate_rss_xml(rss_content)
        assert is_valid, "RSS XML should be valid"

    def test_rss_item_generation(self):
        """Test individual RSS item generation."""
        from pathlib import Path

        # Create sample newsletter file
        newsletter_html = self._create_sample_newsletter_html()
        newsletter_path = self.temp_dir / "newsletters" / "newsletter-2025-01-15.html"
        newsletter_path.parent.mkdir(parents=True, exist_ok=True)

        with open(newsletter_path, 'w', encoding='utf-8') as f:
            f.write(newsletter_html)

        date_obj = datetime(2025, 1, 15)
        guid = "geodaily-20250115"

        # Generate RSS item
        item_content = self.publisher._generate_rss_item(newsletter_path, date_obj, guid)

        # Validate item structure
        assert '<item>' in item_content
        assert '<title>' in item_content
        assert '<link>' in item_content
        assert '<description>' in item_content
        assert '<pubDate>' in item_content
        assert '<guid' in item_content
        assert '<author>' in item_content
        assert '<category>' in item_content
        assert guid in item_content
        assert '</item>' in item_content

    def test_cdata_escaping(self):
        """Test CDATA content escaping."""
        test_text = "This contains ]]> problematic content"
        escaped = self.publisher._escape_for_cdata(test_text)

        # Should escape the CDATA end marker
        assert "]]>" not in escaped or escaped.count("]]>") == 0 or "]]]]><![CDATA[>" in escaped

    def test_category_generation(self):
        """Test category generation from content."""
        content = {
            'stories': [
                {'title': 'China-Russia Military Cooperation', 'summary': 'New developments in Beijing-Moscow relations'},
                {'title': 'Middle East Peace Talks', 'summary': 'Saudi-Iran normalization efforts'}
            ],
            'intro': 'Today we analyze developments in China and the Middle East'
        }

        categories = self.publisher._generate_categories(content)

        # Should include base categories
        assert "Geopolitics" in categories
        assert "Strategic Analysis" in categories

        # Should include content-specific categories
        assert "China" in categories
        assert "Middle East" in categories

    def test_content_extraction(self):
        """Test newsletter content extraction."""
        newsletter_html = self._create_sample_newsletter_html()
        newsletter_path = self.temp_dir / "newsletters" / "newsletter-2025-01-15.html"
        newsletter_path.parent.mkdir(parents=True, exist_ok=True)

        with open(newsletter_path, 'w', encoding='utf-8') as f:
            f.write(newsletter_html)

        content = self.publisher._extract_newsletter_content(newsletter_path)

        assert isinstance(content, dict)
        assert 'stories' in content
        assert 'intro' in content
        assert len(content['stories']) > 0

    def test_error_handling(self):
        """Test error handling in RSS generation."""
        # Test with non-existent file
        fake_path = self.temp_dir / "nonexistent.html"
        date_obj = datetime(2025, 1, 15)
        guid = "test-guid"

        # Should handle gracefully and return basic item
        item_content = self.publisher._generate_rss_item(fake_path, date_obj, guid)
        assert '<item>' in item_content
        assert guid in item_content

    def _create_sample_newsletter_html(self):
        """Create sample newsletter HTML for testing."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test Newsletter - January 15, 2025</title>
</head>
<body>
    <header>
        <h1>Test Newsletter</h1>
        <p class="newsletter-intro">This is a test newsletter about geopolitical developments.</p>
    </header>

    <main>
        <section class="story" id="story-1">
            <header class="story-header">
                <h2 class="story-title">China-Russia Military Cooperation</h2>
            </header>
            <div class="story-content">
                <div class="analysis-section">
                    <h3>Why This Matters</h3>
                    <p>This development signals a major shift in global power dynamics.</p>
                </div>
                <div class="analysis-section">
                    <h3>What Others Are Missing</h3>
                    <p>The strategic implications for NATO and the US are significant.</p>
                </div>
                <div class="sources">
                    <h4>Sources</h4>
                    <ul>
                        <li><a href="https://example.com/1">Source 1</a></li>
                        <li><a href="https://example.com/2">Source 2</a></li>
                    </ul>
                </div>
            </div>
        </section>

        <section class="story" id="story-2">
            <header class="story-header">
                <h2 class="story-title">Middle East Peace Initiatives</h2>
            </header>
            <div class="story-content">
                <div class="analysis-section">
                    <h3>Why This Matters</h3>
                    <p>New diplomatic efforts could reshape regional alliances.</p>
                </div>
                <div class="sources">
                    <h4>Sources</h4>
                    <ul>
                        <li><a href="https://example.com/3">Source 3</a></li>
                    </ul>
                </div>
            </div>
        </section>
    </main>

    <footer>
        <p>Test footer content.</p>
    </footer>
</body>
</html>"""


if __name__ == "__main__":
    # Run basic validation test
    test = TestRSSFeed()
    test.setup_method()

    try:
        print("Running RSS feed generation test...")
        test.test_rss_feed_generation()
        print("✓ RSS feed generation test passed")

        print("Running RSS XML validation test...")
        test.test_rss_xml_validation()
        print("✓ RSS XML validation test passed")

        print("Running RSS item generation test...")
        test.test_rss_item_generation()
        print("✓ RSS item generation test passed")

        print("All tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise
    finally:
        test.teardown_method()