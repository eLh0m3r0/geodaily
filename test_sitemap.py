#!/usr/bin/env python3
"""
Test sitemap generation functionality.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sitemap_generator import SitemapGenerator


def test_sitemap_generation():
    """Test basic sitemap generation."""
    print("\n=== Testing Sitemap Generation ===")

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create some test files
        (temp_path / "index.html").write_text("<html><body>Test</body></html>")
        (temp_path / "newsletters").mkdir()
        (temp_path / "newsletters" / "newsletter-2025-01-15.html").write_text("<html><body>Newsletter</body></html>")
        (temp_path / "about.html").write_text("<html><body>About</body></html>")

        # Initialize sitemap generator
        generator = SitemapGenerator(str(temp_path), base_url="https://example.com")

        # Generate sitemap
        sitemap_path = generator.generate_sitemap()

        # Check that sitemap was created
        assert Path(sitemap_path).exists(), "Sitemap file should be created"

        # Read and validate sitemap content
        with open(sitemap_path, 'r', encoding='utf-8') as f:
            sitemap_content = f.read()

        print(f"Generated sitemap content:\n{sitemap_content}")

        # Basic validation checks
        assert '<?xml version="1.0" encoding="UTF-8"?>' in sitemap_content
        assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in sitemap_content
        assert '<url>' in sitemap_content
        assert '<loc>' in sitemap_content
        assert '<lastmod>' in sitemap_content
        assert '<priority>' in sitemap_content
        assert '<changefreq>' in sitemap_content
        assert '</urlset>' in sitemap_content

        # Check that our test URLs are included
        assert 'https://example.com/index.html' in sitemap_content
        assert 'https://example.com/newsletters/newsletter-2025-01-15.html' in sitemap_content
        assert 'https://example.com/about.html' in sitemap_content

        print("✅ Sitemap generation test passed")


def test_sitemap_validation():
    """Test sitemap XML validation."""
    print("\n=== Testing Sitemap XML Validation ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        (temp_path / "index.html").write_text("<html><body>Test</body></html>")

        generator = SitemapGenerator(str(temp_path), base_url="https://example.com")
        sitemap_path = generator.generate_sitemap()

        # Test validation
        with open(sitemap_path, 'r', encoding='utf-8') as f:
            sitemap_content = f.read()

        is_valid = generator._validate_sitemap_xml(sitemap_content)
        assert is_valid, "Generated sitemap should be valid XML"

        print("✅ Sitemap validation test passed")


def test_robots_txt_generation():
    """Test robots.txt generation with sitemap reference."""
    print("\n=== Testing Robots.txt Generation ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        generator = SitemapGenerator(str(temp_path), base_url="https://example.com")
        generator._generate_robots_txt()

        robots_path = temp_path / "robots.txt"
        assert robots_path.exists(), "robots.txt should be created"

        with open(robots_path, 'r', encoding='utf-8') as f:
            robots_content = f.read()

        print(f"Generated robots.txt content:\n{robots_content}")

        # Check robots.txt content
        assert "User-agent: *" in robots_content
        assert "Allow: /" in robots_content
        assert "Sitemap: https://example.com/sitemap.xml" in robots_content

        print("✅ Robots.txt generation test passed")


def test_sitemap_stats():
    """Test sitemap statistics."""
    print("\n=== Testing Sitemap Statistics ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        (temp_path / "index.html").write_text("<html><body>Test</body></html>")
        (temp_path / "about.html").write_text("<html><body>About</body></html>")

        generator = SitemapGenerator(str(temp_path), base_url="https://example.com")
        generator.generate_sitemap()

        stats = generator.get_stats()

        print(f"Sitemap stats: {stats}")

        assert 'total_urls' in stats
        assert 'file_size' in stats
        assert stats['total_urls'] >= 2  # Should have at least index.html and about.html
        assert stats['file_size'] > 0

        print("✅ Sitemap statistics test passed")


if __name__ == "__main__":
    print("Running sitemap tests...")

    test_sitemap_generation()
    test_sitemap_validation()
    test_robots_txt_generation()
    test_sitemap_stats()

    print("\n✅ All sitemap tests completed successfully!")