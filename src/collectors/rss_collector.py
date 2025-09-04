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
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models import Article, NewsSource, SourceCategory
from ..config import Config
from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from .source_health_monitor import source_health_monitor
from ..performance.connection_pool import connection_pool_manager
from .article_content_fetcher import article_content_fetcher

logger = get_structured_logger(__name__)

class RSSCollector:
    """Collects articles from RSS feeds."""
    
    def __init__(self, fetch_full_content: bool = True):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': Config.USER_AGENT
        })
        self.fetch_full_content = fetch_full_content
    
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
            logger.info(f"Collecting from RSS source: {source.name}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       structured_data={'source_name': source.name, 'source_url': source.url})

            # Parse RSS feed with retry logic
            feed_data = self._fetch_feed_with_retry(source.url, source.name)
            if not feed_data:
                logger.error(f"Failed to fetch RSS feed: {source.name}",
                           pipeline_stage=PipelineStage.COLLECTION,
                           error_category=ErrorCategory.NETWORK_ERROR,
                           structured_data={'source_name': source.name, 'source_url': source.url})
                return articles

            feed = feedparser.parse(feed_data)

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS feed has issues ({source.name}): {feed.bozo_exception}",
                             pipeline_stage=PipelineStage.COLLECTION,
                             error_category=ErrorCategory.PARSING_ERROR,
                             structured_data={'source_name': source.name, 'feed_bozo_exception': str(feed.bozo_exception)})

            # Process each entry and collect valid articles
            parsed_articles = []
            for entry in feed.entries:
                try:
                    article = self._parse_rss_entry(entry, source)
                    if article:
                        # Filter articles by publication date (only last 24 hours)
                        if self._is_recent_article(article):
                            parsed_articles.append(article)
                        else:
                            logger.debug(f"Skipping old article: {article.title} ({article.published_date})",
                                       pipeline_stage=PipelineStage.COLLECTION,
                                       structured_data={
                                           'source_name': source.name,
                                           'article_title': article.title[:50],
                                           'published_date': article.published_date.isoformat() if article.published_date else None,
                                           'reason': 'too_old'
                                       })
                except Exception as e:
                    logger.error(f"Error parsing RSS entry from {source.name}: {e}",
                               pipeline_stage=PipelineStage.COLLECTION,
                               error_category=ErrorCategory.PARSING_ERROR,
                               structured_data={
                                   'source_name': source.name,
                                   'error_type': type(e).__name__,
                                   'error_message': str(e)
                               })
                    continue
            
            # Enhance articles with full content in parallel if enabled
            if self.fetch_full_content and parsed_articles:
                articles = self._enhance_articles_parallel(parsed_articles)
            else:
                articles = parsed_articles

            logger.info(f"Collected {len(articles)} recent articles from {source.name}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       structured_data={
                           'source_name': source.name,
                           'articles_collected': len(articles),
                           'source_url': source.url
                       })

        except Exception as e:
            logger.error(f"Error collecting from RSS source {source.name}: {e}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       error_category=ErrorCategory.UNKNOWN_ERROR,
                       structured_data={
                           'source_name': source.name,
                           'source_url': source.url,
                           'error_type': type(e).__name__,
                           'error_message': str(e)
                       })

        return articles
    
    def _fetch_feed_with_retry(self, url: str, source_name: str) -> Optional[str]:
        """Fetch RSS feed with retry logic, health monitoring, and connection pooling."""
        start_time = time.time()
        success = False
        error_type = None

        for attempt in range(Config.MAX_RETRIES):
            try:
                # Use connection pool manager for better performance
                response = connection_pool_manager.make_request(
                    url=url,
                    method='GET',
                    headers={
                        'User-Agent': 'GeopoliticalDaily/1.0 (RSS Reader)',
                        'Accept': 'application/rss+xml, application/xml, text/xml'
                    }
                )
                response.raise_for_status()

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

                return response.content

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
            logger.error(f"Error parsing RSS entry: {e}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       error_category=ErrorCategory.PARSING_ERROR,
                       structured_data={
                           'error_type': type(e).__name__,
                           'error_message': str(e)
                       })
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
        logger.warning("No valid date found in RSS entry, using current time",
                     pipeline_stage=PipelineStage.COLLECTION,
                     error_category=ErrorCategory.VALIDATION_ERROR,
                     structured_data={'fallback_action': 'current_time'})
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

    def _is_recent_article(self, article) -> bool:
        """Check if article was published within the last 48 hours."""
        from datetime import datetime, timezone, timedelta

        if not article.published_date:
            return False

        # Ensure published_date is timezone-aware
        if article.published_date.tzinfo is None:
            article.published_date = article.published_date.replace(tzinfo=timezone.utc)

        # Get current time in UTC
        now = datetime.now(timezone.utc)

        # Check if article is from last 48 hours
        time_diff = now - article.published_date
        is_recent = time_diff <= timedelta(hours=48)

        logger.debug(f"Article age check: {article.title[:50]}... - {time_diff} - Recent: {is_recent}",
                   pipeline_stage=PipelineStage.COLLECTION,
                   structured_data={
                       'article_title': article.title[:50],
                       'time_diff_hours': time_diff.total_seconds() / 3600,
                       'is_recent': is_recent,
                       'published_date': article.published_date.isoformat() if article.published_date else None
                   })

        return is_recent
    
    def _enhance_articles_parallel(self, articles: List[Article]) -> List[Article]:
        """Enhance articles with full content fetching in parallel."""
        # Filter articles that need enhancement (short summaries)
        articles_to_enhance = [
            article for article in articles 
            if not article.summary or len(article.summary) < 200
        ]
        
        if not articles_to_enhance:
            return articles
        
        logger.info(f"Enhancing {len(articles_to_enhance)} articles with full content",
                   pipeline_stage=PipelineStage.COLLECTION,
                   structured_data={'articles_to_enhance': len(articles_to_enhance)})
        
        # Use ThreadPoolExecutor for parallel fetching
        max_workers = min(Config.MAX_PARALLEL_FETCHES, len(articles_to_enhance))
        enhanced_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit content fetching tasks
            future_to_article = {
                executor.submit(self._enhance_single_article, article): article 
                for article in articles_to_enhance
            }
            
            # Process completed tasks
            for future in as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    enhanced = future.result(timeout=Config.CONTENT_FETCH_TIMEOUT)
                    if enhanced:
                        enhanced_count += 1
                except Exception as e:
                    logger.debug(f"Failed to enhance article: {article.title[:50]}... - {e}",
                               pipeline_stage=PipelineStage.COLLECTION,
                               error_category=ErrorCategory.NETWORK_ERROR)
        
        logger.info(f"Successfully enhanced {enhanced_count}/{len(articles_to_enhance)} articles",
                   pipeline_stage=PipelineStage.COLLECTION,
                   structured_data={
                       'enhanced_count': enhanced_count,
                       'total_attempted': len(articles_to_enhance),
                       'success_rate': enhanced_count / len(articles_to_enhance) if articles_to_enhance else 0
                   })
        
        return articles
    
    def _enhance_single_article(self, article: Article) -> bool:
        """Enhance a single article with full content."""
        try:
            full_text, enhanced_summary = article_content_fetcher.fetch_article_content(article.url)
            
            if enhanced_summary and len(enhanced_summary) > len(article.summary or ''):
                original_length = len(article.summary or '')
                article.summary = enhanced_summary
                
                logger.debug(f"Enhanced: {article.title[:50]}... ({original_length} → {len(enhanced_summary)} chars)",
                           pipeline_stage=PipelineStage.COLLECTION,
                           structured_data={
                               'article_title': article.title[:50],
                               'original_length': original_length,
                               'enhanced_length': len(enhanced_summary)
                           })
                return True
                
        except Exception as e:
            logger.debug(f"Error enhancing article {article.url}: {e}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       error_category=ErrorCategory.NETWORK_ERROR)
        
        return False
