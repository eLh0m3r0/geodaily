"""
Web scraper for Tier 2 sources that don't have RSS feeds.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Optional, Dict
import time
import re
from urllib.parse import urljoin, urlparse

from ..models import Article, NewsSource, SourceCategory
from ..config import Config
from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from .source_health_monitor import source_health_monitor
from ..performance.connection_pool import connection_pool_manager

logger = get_structured_logger(__name__)

class WebScraper:
    """Scrapes articles from websites using CSS selectors."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def collect_from_source(self, source: NewsSource) -> List[Article]:
        """
        Collect articles from a single web source.
        
        Args:
            source: NewsSource configuration with selectors
            
        Returns:
            List of Article objects
        """
        articles = []
        
        try:
            logger.info(f"Scraping web source: {source.name}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       structured_data={'source_name': source.name, 'source_url': source.url})

            # Fetch webpage
            soup = self._fetch_page_with_retry(source.url, source.name)
            if not soup:
                logger.error(f"Failed to fetch webpage: {source.name}",
                           pipeline_stage=PipelineStage.COLLECTION,
                           error_category=ErrorCategory.NETWORK_ERROR,
                           structured_data={'source_name': source.name, 'source_url': source.url})
                return articles

            # Extract articles using selectors
            if source.selectors:
                articles = self._extract_articles(soup, source)
            else:
                logger.warning(f"No selectors defined for {source.name}",
                             pipeline_stage=PipelineStage.COLLECTION,
                             error_category=ErrorCategory.CONFIGURATION_ERROR,
                             structured_data={'source_name': source.name, 'missing_selectors': True})

            logger.info(f"Scraped {len(articles)} articles from {source.name}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       structured_data={
                           'source_name': source.name,
                           'articles_scraped': len(articles),
                           'source_url': source.url
                       })

        except Exception as e:
            logger.error(f"Error scraping web source {source.name}: {e}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       error_category=ErrorCategory.UNKNOWN_ERROR,
                       structured_data={
                           'source_name': source.name,
                           'source_url': source.url,
                           'error_type': type(e).__name__,
                           'error_message': str(e)
                       })
        
        return articles
    
    def _fetch_page_with_retry(self, url: str, source_name: str) -> Optional[BeautifulSoup]:
        """Fetch webpage with retry logic, health monitoring, and connection pooling."""
        start_time = time.time()
        success = False
        error_type = None

        # WARNING: SSL certificate verification is disabled for HTTPS requests to handle sources with certificate issues.
        # This reduces security by making the connection vulnerable to man-in-the-middle attacks.
        # Only use this when necessary and ensure the sources are trusted.
        logger.warning("SSL certificate verification disabled for web scraping requests",
                      pipeline_stage=PipelineStage.COLLECTION,
                      structured_data={'source_name': source_name, 'url': url})

        for attempt in range(Config.MAX_RETRIES):
            try:
                # Prepare request parameters
                request_kwargs = {
                    'headers': {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'User-Agent': 'Mozilla/5.0 (compatible; GeopoliticalDaily/1.0)'
                    }
                }

                # Disable SSL verification for HTTPS requests to handle certificate issues
                if url.startswith('https://'):
                    request_kwargs.update({
                        'cert_reqs': 'CERT_NONE',
                        'assert_hostname': False
                    })
                    logger.debug("SSL parameters added for HTTPS request",
                               structured_data={
                                   'url': url,
                                   'cert_reqs': 'CERT_NONE',
                                   'assert_hostname': False
                               })

                # Use connection pool manager for better performance
                response = connection_pool_manager.make_request(
                    url=url,
                    method='GET',
                    **request_kwargs
                )
                response.raise_for_status()

                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')

                # Success - record metrics
                success = True
                response_time = time.time() - start_time
                source_health_monitor.record_request_result(
                    source_name=source_name,
                    success=True,
                    response_time=response_time
                )

                # Record performance metrics
                from ..performance.connection_pool import performance_optimizer
                performance_optimizer.record_request_metrics(True, response_time)

                return soup

            except Exception as e:
                error_type = type(e).__name__.lower()
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}",
                              pipeline_stage=PipelineStage.COLLECTION,
                              error_category=ErrorCategory.NETWORK_ERROR,
                              structured_data={
                                  'source_name': source_name,
                                  'url': url,
                                  'attempt': attempt + 1,
                                  'max_retries': Config.MAX_RETRIES,
                                  'error_type': error_type,
                                  'error_message': str(e)
                              })

                # Record failed request metrics
                response_time = time.time() - start_time
                from ..performance.connection_pool import performance_optimizer
                performance_optimizer.record_request_metrics(False, response_time)

                if attempt < Config.MAX_RETRIES - 1:
                    time.sleep(Config.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"All retry attempts failed for {url}",
                                pipeline_stage=PipelineStage.COLLECTION,
                                error_category=ErrorCategory.NETWORK_ERROR,
                                structured_data={
                                    'source_name': source_name,
                                    'url': url,
                                    'total_attempts': Config.MAX_RETRIES,
                                    'final_error': str(e)
                                })

        # All attempts failed - record failure
        if not success:
            response_time = time.time() - start_time
            source_health_monitor.record_request_result(
                source_name=source_name,
                success=False,
                response_time=response_time,
                error_type=error_type or "unknown"
            )

        return None
    
    def _extract_articles(self, soup: BeautifulSoup, source: NewsSource) -> List[Article]:
        """Extract articles using CSS selectors."""
        articles = []
        selectors = source.selectors
        
        try:
            # Find article containers
            container_selector = selectors.get('container', 'article')
            containers = soup.select(container_selector)
            
            if not containers:
                logger.warning(f"No containers found with selector '{container_selector}' for {source.name}",
                             pipeline_stage=PipelineStage.COLLECTION,
                             error_category=ErrorCategory.PARSING_ERROR,
                             structured_data={
                                 'source_name': source.name,
                                 'selector': container_selector,
                                 'containers_found': 0
                             })
                return articles

            for container in containers:
                try:
                    article = self._extract_single_article(container, source, soup)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"Error extracting article from {source.name}: {e}",
                               pipeline_stage=PipelineStage.COLLECTION,
                               error_category=ErrorCategory.PARSING_ERROR,
                               structured_data={
                                   'source_name': source.name,
                                   'error_type': type(e).__name__,
                                   'error_message': str(e)
                               })
                    continue

        except Exception as e:
            logger.error(f"Error in article extraction for {source.name}: {e}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       error_category=ErrorCategory.PARSING_ERROR,
                       structured_data={
                           'source_name': source.name,
                           'error_type': type(e).__name__,
                           'error_message': str(e)
                       })
        
        return articles
    
    def _extract_single_article(self, container, source: NewsSource, full_soup: BeautifulSoup) -> Optional[Article]:
        """Extract a single article from a container element."""
        selectors = source.selectors
        
        try:
            # Extract title
            title_selector = selectors.get('title', 'h1, h2, h3, .title, .headline')
            title_elem = container.select_one(title_selector)
            if not title_elem:
                return None
            
            title = self._clean_text(title_elem.get_text())
            if not title:
                return None
            
            # Extract URL
            link_selector = selectors.get('link', 'a')
            link_elem = container.select_one(link_selector)
            if not link_elem:
                return None
            
            url = link_elem.get('href', '')
            if not url:
                return None
            
            # Make URL absolute
            url = urljoin(source.url, url)
            
            # Extract summary/description
            summary = ''
            summary_selector = selectors.get('summary', '.summary, .excerpt, .description, p')
            summary_elem = container.select_one(summary_selector)
            if summary_elem:
                summary = self._clean_text(summary_elem.get_text())
            
            # If no summary found, try to get first paragraph from the article
            if not summary:
                summary = self._extract_summary_from_content(container)
            
            # Extract date
            published_date = self._extract_date(container, selectors)
            
            # Extract author
            author = self._extract_author(container, selectors)
            
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
            logger.error(f"Error extracting single article: {e}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       error_category=ErrorCategory.PARSING_ERROR,
                       structured_data={
                           'source_name': source.name,
                           'error_type': type(e).__name__,
                           'error_message': str(e)
                       })
            return None
    
    def _extract_date(self, container, selectors: Dict[str, str]) -> datetime:
        """Extract publication date from article container."""
        date_selector = selectors.get('date', 'time, .date, .published')
        date_elem = container.select_one(date_selector)
        
        if date_elem:
            # Try datetime attribute first
            date_str = date_elem.get('datetime') or date_elem.get_text()
            if date_str:
                try:
                    # Try to parse various date formats
                    return self._parse_date_string(date_str)
                except:
                    pass
        
        # Default to current time
        return datetime.now(timezone.utc)
    
    def _extract_author(self, container, selectors: Dict[str, str]) -> Optional[str]:
        """Extract author from article container."""
        author_selector = selectors.get('author', '.author, .byline, [rel="author"]')
        author_elem = container.select_one(author_selector)
        
        if author_elem:
            return self._clean_text(author_elem.get_text())
        
        return None
    
    def _extract_summary_from_content(self, container) -> str:
        """Extract summary from article content if no explicit summary found."""
        # Look for paragraphs
        paragraphs = container.select('p')
        if paragraphs:
            # Get first non-empty paragraph
            for p in paragraphs:
                text = self._clean_text(p.get_text())
                if text and len(text) > 50:  # Minimum length for meaningful summary
                    return text[:300] + "..." if len(text) > 300 else text
        
        return ""
    
    def _parse_date_string(self, date_str: str) -> datetime:
        """Parse date string into datetime object."""
        # Clean the date string
        date_str = date_str.strip()
        
        # Common date formats to try
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',  # ISO format with timezone
            '%Y-%m-%dT%H:%M:%SZ',   # ISO format UTC
            '%Y-%m-%d %H:%M:%S',    # Standard format
            '%Y-%m-%d',             # Date only
            '%B %d, %Y',            # Month Day, Year
            '%b %d, %Y',            # Abbreviated month
            '%d %B %Y',             # Day Month Year
            '%d %b %Y',             # Day abbreviated month Year
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # If no timezone info, assume UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        # If all parsing fails, return current time
        logger.warning(f"Could not parse date string: {date_str}",
                     pipeline_stage=PipelineStage.COLLECTION,
                     error_category=ErrorCategory.VALIDATION_ERROR,
                     structured_data={
                         'date_string': date_str,
                         'fallback_action': 'current_time'
                     })
        return datetime.now(timezone.utc)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common artifacts
        text = re.sub(r'\n|\r|\t', ' ', text)
        
        return text
