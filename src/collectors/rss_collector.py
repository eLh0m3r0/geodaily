"""
RSS feed collector for Tier 1 sources.
"""

import feedparser
import requests
from datetime import datetime, timezone
from typing import List, Optional
import time
import re
from bs4 import BeautifulSoup

from ..models import Article, NewsSource, SourceCategory
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

class RSSCollector:
    """Collects articles from RSS feeds."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT
        })
    
    def collect_from_source(self, source: NewsSource) -> List[Article]:
        """
        Collect articles from a single RSS source.
        
        Args:
            source: NewsSource configuration
            
        Returns:
            List of Article objects
        """
        articles = []
        
        try:
            logger.info(f"Collecting from RSS source: {source.name}")
            
            # Parse RSS feed with retry logic
            feed_data = self._fetch_feed_with_retry(source.url)
            if not feed_data:
                logger.error(f"Failed to fetch RSS feed: {source.name}")
                return articles
            
            feed = feedparser.parse(feed_data)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS feed has issues ({source.name}): {feed.bozo_exception}")
            
            # Process each entry
            for entry in feed.entries:
                try:
                    article = self._parse_rss_entry(entry, source)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing RSS entry from {source.name}: {e}")
                    continue
            
            logger.info(f"Collected {len(articles)} articles from {source.name}")
            
        except Exception as e:
            logger.error(f"Error collecting from RSS source {source.name}: {e}")
        
        return articles
    
    def _fetch_feed_with_retry(self, url: str) -> Optional[str]:
        """Fetch RSS feed with retry logic."""
        for attempt in range(Config.MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    timeout=Config.REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                response.raise_for_status()
                return response.content
                
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"All retry attempts failed for {url}")
        
        return None
    
    def _parse_rss_entry(self, entry, source: NewsSource) -> Optional[Article]:
        """Parse a single RSS entry into an Article."""
        try:
            # Extract title
            title = self._clean_text(getattr(entry, 'title', ''))
            if not title:
                return None
            
            # Extract URL
            url = getattr(entry, 'link', '')
            if not url:
                return None
            
            # Extract summary/description
            summary = ''
            if hasattr(entry, 'summary'):
                summary = entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description
            
            # Clean HTML from summary
            summary = self._clean_html(summary)
            summary = self._clean_text(summary)
            
            # Extract published date
            published_date = self._parse_date(entry)
            
            # Extract author
            author = getattr(entry, 'author', None)
            
            # Create article
            article = Article(
                source=source.name,
                source_category=source.category,
                title=title,
                url=url,
                summary=summary,
                published_date=published_date,
                author=author
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Error parsing RSS entry: {e}")
            return None
    
    def _parse_date(self, entry) -> datetime:
        """Parse publication date from RSS entry."""
        # Try different date fields
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
        
        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    time_struct = getattr(entry, field)
                    return datetime(*time_struct[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue
        
        # Try string date fields
        string_fields = ['published', 'updated', 'created']
        for field in string_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    date_str = getattr(entry, field)
                    # feedparser usually handles this, but just in case
                    parsed = feedparser._parse_date(date_str)
                    if parsed:
                        return datetime(*parsed[:6], tzinfo=timezone.utc)
                except:
                    continue
        
        # Default to current time if no date found
        logger.warning("No valid date found in RSS entry, using current time")
        return datetime.now(timezone.utc)
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        
        try:
            soup = BeautifulSoup(text, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except Exception:
            # Fallback: simple regex HTML removal
            return re.sub(r'<[^>]+>', '', text)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common RSS artifacts
        text = re.sub(r'\[CDATA\[|\]\]', '', text)
        
        return text
