"""
Sitemap generator for SEO optimization and search engine discoverability.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


class SitemapGenerator:
    """Generates XML sitemaps conforming to sitemaps.org protocol."""

    def __init__(self, output_dir: str = "docs", base_url: Optional[str] = None):
        """Initialize sitemap generator."""
        self.output_dir = Path(output_dir)
        self.base_url = base_url or Config.SITE_BASE_URL
        self.sitemap_path = self.output_dir / "sitemap.xml"
        self.robots_path = self.output_dir / "robots.txt"

        # Priority and frequency mappings
        self.page_priorities = {
            "index.html": 1.0,
            "about.html": 0.8,
            "archive.html": 0.7,
            "dashboard.html": 0.6,
            "newsletters/": 0.9,  # Base priority for newsletter pages
        }

        self.page_frequencies = {
            "index.html": "daily",
            "about.html": "monthly",
            "archive.html": "weekly",
            "dashboard.html": "daily",
            "newsletters/": "never",  # Individual newsletters don't change
        }

        logger.info(f"Sitemap generator initialized: {self.output_dir}")

    def generate_sitemap(self) -> str:
        """
        Generate complete XML sitemap for the site.

        Returns:
            Path to generated sitemap file
        """
        try:
            # Discover all pages
            pages = self._discover_pages()

            # Generate XML sitemap
            sitemap_xml = self._generate_xml_sitemap(pages)

            # Validate XML
            if not self._validate_sitemap_xml(sitemap_xml):
                raise ValueError("Generated sitemap XML is invalid")

            # Write sitemap file
            with open(self.sitemap_path, 'w', encoding='utf-8') as f:
                f.write(sitemap_xml)

            # Generate robots.txt
            self._generate_robots_txt()

            logger.info(f"Sitemap generated with {len(pages)} pages: {self.sitemap_path}")
            return str(self.sitemap_path)

        except Exception as e:
            logger.error(f"Failed to generate sitemap: {e}")
            raise

    def _discover_pages(self) -> List[Dict[str, str]]:
        """
        Discover all pages in the site.

        Returns:
            List of page dictionaries with URL, priority, frequency, and lastmod
        """
        pages = []

        try:
            # Add main pages
            main_pages = ["index.html", "about.html", "archive.html", "dashboard.html"]

            for page in main_pages:
                page_path = self.output_dir / page
                if page_path.exists():
                    page_info = self._get_page_info(page_path, page)
                    if page_info:
                        pages.append(page_info)
                else:
                    logger.warning(f"Main page not found: {page_path}")

            # Add newsletter pages
            newsletters_dir = self.output_dir / "newsletters"
            if newsletters_dir.exists():
                newsletter_files = sorted(newsletters_dir.glob("newsletter-*.html"), reverse=True)

                for newsletter_file in newsletter_files:
                    page_info = self._get_page_info(newsletter_file, f"newsletters/{newsletter_file.name}")
                    if page_info:
                        pages.append(page_info)

            # Add feed.xml if it exists
            feed_path = self.output_dir / "feed.xml"
            if feed_path.exists():
                page_info = self._get_page_info(feed_path, "feed.xml")
                if page_info:
                    pages.append(page_info)

            logger.info(f"Discovered {len(pages)} pages")

        except Exception as e:
            logger.error(f"Error discovering pages: {e}")

        return pages

    def _get_page_info(self, file_path: Path, relative_path: str) -> Optional[Dict[str, str]]:
        """
        Get page information for sitemap entry.

        Args:
            file_path: Path to the file
            relative_path: Relative path from site root

        Returns:
            Dictionary with page information or None if invalid
        """
        try:
            # Get file modification time
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            lastmod = mtime.strftime('%Y-%m-%d')

            # Determine priority
            priority = self._get_page_priority(relative_path)

            # Determine change frequency
            changefreq = self._get_page_frequency(relative_path)

            # Build full URL
            url = urljoin(self.base_url + '/', relative_path)

            # Validate URL
            if not self._validate_url(url):
                logger.warning(f"Invalid URL generated: {url}")
                return None

            return {
                'url': url,
                'lastmod': lastmod,
                'priority': str(priority),
                'changefreq': changefreq
            }

        except Exception as e:
            logger.error(f"Error getting page info for {file_path}: {e}")
            return None

    def _get_page_priority(self, relative_path: str) -> float:
        """Get priority for a page based on its path."""
        # Check for exact matches first
        if relative_path in self.page_priorities:
            return self.page_priorities[relative_path]

        # Check for path prefixes
        for path_prefix, priority in self.page_priorities.items():
            if path_prefix.endswith('/') and relative_path.startswith(path_prefix):
                return priority

        # Default priority
        return 0.5

    def _get_page_frequency(self, relative_path: str) -> str:
        """Get change frequency for a page based on its path."""
        # Check for exact matches first
        if relative_path in self.page_frequencies:
            return self.page_frequencies[relative_path]

        # Check for path prefixes
        for path_prefix, frequency in self.page_frequencies.items():
            if path_prefix.endswith('/') and relative_path.startswith(path_prefix):
                return frequency

        # Default frequency
        return "monthly"

    def _validate_url(self, url: str) -> bool:
        """Validate URL format and accessibility."""
        try:
            parsed = urlparse(url)

            # Check basic URL structure
            if not parsed.scheme or not parsed.netloc:
                return False

            # Ensure it's an HTTP/HTTPS URL
            if parsed.scheme not in ['http', 'https']:
                return False

            # Check for valid domain
            if not parsed.netloc or '.' not in parsed.netloc:
                return False

            return True

        except Exception:
            return False

    def _generate_xml_sitemap(self, pages: List[Dict[str, str]]) -> str:
        """Generate XML sitemap content."""
        # XML declaration and root element
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        # Add each page
        for page in pages:
            xml_content += '  <url>\n'
            xml_content += f'    <loc>{self._escape_xml(page["url"])}</loc>\n'
            xml_content += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
            xml_content += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
            xml_content += f'    <priority>{page["priority"]}</priority>\n'
            xml_content += '  </url>\n'

        xml_content += '</urlset>\n'

        return xml_content

    def _escape_xml(self, text: str) -> str:
        """Escape special characters for XML."""
        return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

    def _validate_sitemap_xml(self, xml_content: str) -> bool:
        """Validate XML sitemap structure."""
        try:
            # Parse XML to check for well-formedness
            root = ET.fromstring(xml_content)

            # Check root element
            if root.tag != '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset':
                logger.error("Root element is not urlset")
                return False

            # Check namespace
            if not root.tag.startswith('{http://www.sitemaps.org/schemas/sitemap/0.9}'):
                logger.error("Missing or incorrect XML namespace")
                return False

            # Validate each URL entry
            for url_elem in root:
                if url_elem.tag != '{http://www.sitemaps.org/schemas/sitemap/0.9}url':
                    logger.error(f"Invalid element: {url_elem.tag}")
                    return False

                # Check required elements
                loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is None or not loc.text:
                    logger.error("Missing or empty loc element")
                    return False

            logger.info("Sitemap XML validation passed")
            return True

        except ET.ParseError as e:
            logger.error(f"Sitemap XML parsing error: {e}")
            return False
        except Exception as e:
            logger.error(f"Sitemap validation error: {e}")
            return False

    def _generate_robots_txt(self):
        """Generate robots.txt file with sitemap reference."""
        try:
            robots_content = f"""User-agent: *
Allow: /

# Sitemap
Sitemap: {self.base_url}/sitemap.xml

# Crawl delay (optional)
Crawl-delay: 1
"""

            with open(self.robots_path, 'w', encoding='utf-8') as f:
                f.write(robots_content)

            logger.info(f"Robots.txt generated: {self.robots_path}")

        except Exception as e:
            logger.error(f"Failed to generate robots.txt: {e}")
            raise

    def get_stats(self) -> Dict[str, int]:
        """Get sitemap generation statistics."""
        try:
            if not self.sitemap_path.exists():
                return {"total_urls": 0, "file_size": 0}

            # Count URLs in sitemap
            with open(self.sitemap_path, 'r', encoding='utf-8') as f:
                content = f.read()

            url_count = content.count('<url>')

            return {
                "total_urls": url_count,
                "file_size": len(content),
                "last_generated": datetime.fromtimestamp(self.sitemap_path.stat().st_mtime).isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting sitemap stats: {e}")
            return {"total_urls": 0, "file_size": 0}