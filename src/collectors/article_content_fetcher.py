"""
Enhanced article content fetcher that extracts full article text from URLs.
Uses multiple extraction strategies for maximum compatibility.
"""

import requests
from typing import Optional, Dict, Tuple
import time
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from ..config import Config

# Try to import advanced extraction libraries
try:
    from newspaper import Article as NewspaperArticle
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    
try:
    from readability import Readability
    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False

logger = get_structured_logger(__name__)


class ArticleContentFetcher:
    """Fetches and extracts full article content from URLs."""
    
    # Common article content selectors (in order of priority)
    CONTENT_SELECTORS = [
        # News site specific
        'article', 'main article', '[role="main"]', '.article-body',
        '.article-content', '.story-body', '.entry-content',
        '.post-content', '.content-body', 'div.content',
        # Generic fallbacks
        '[itemprop="articleBody"]', '.body-content',
        'div.text', '.post', '.entry', 'main'
    ]
    
    # Elements to remove (ads, navigation, etc)
    REMOVE_SELECTORS = [
        'script', 'style', 'nav', 'header', 'footer', 
        '.advertisement', '.ad', '.social-share', '.related-articles',
        '.comments', '.sidebar', '.navigation', '.menu',
        '[class*="promo"]', '[class*="newsletter"]', '[class*="subscribe"]'
    ]
    
    # Minimum content length to be considered valid
    MIN_CONTENT_LENGTH = 200
    
    def __init__(self, cache_dir: str = "cache/article_content"):
        """Initialize content fetcher with optional caching."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Cache expiry (24 hours)
        self.cache_expiry = timedelta(hours=24)
    
    def fetch_article_content(self, url: str, use_cache: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch and extract article content from URL.
        
        Returns:
            Tuple of (full_text, summary) or (None, None) if extraction fails
        """
        try:
            # Check cache first
            if use_cache:
                cached = self._get_cached_content(url)
                if cached:
                    logger.debug(f"Using cached content for {url}")
                    return cached['full_text'], cached['summary']
            
            logger.info(f"Fetching article content from {url}",
                       pipeline_stage=PipelineStage.COLLECTION,
                       structured_data={'url': url})
            
            # Fetch the page
            html = self._fetch_page(url)
            if not html:
                return None, None
            
            # Try multiple extraction methods in order of preference
            full_text, summary = None, None
            
            # Method 1: Try newspaper3k (most accurate)
            if NEWSPAPER_AVAILABLE and not full_text:
                full_text, summary = self._extract_with_newspaper(url, html)
                if full_text:
                    logger.debug(f"Extracted with newspaper3k: {len(full_text)} chars")
            
            # Method 2: Try readability (good fallback)
            if READABILITY_AVAILABLE and not full_text:
                full_text, summary = self._extract_with_readability(html, url)
                if full_text:
                    logger.debug(f"Extracted with readability: {len(full_text)} chars")
            
            # Method 3: Fallback to BeautifulSoup
            if not full_text:
                full_text, summary = self._extract_with_beautifulsoup(html, url)
                if full_text:
                    logger.debug(f"Extracted with BeautifulSoup: {len(full_text)} chars")
            
            # Validate extracted content
            if full_text and len(full_text) >= self.MIN_CONTENT_LENGTH:
                # Score the content quality
                quality_score = self._score_content_quality(full_text, summary)
                
                # Cache the result
                if use_cache:
                    self._cache_content(url, full_text, summary)
                
                logger.info(f"Successfully extracted {len(full_text)} chars from {urlparse(url).netloc} (quality: {quality_score:.2f})",
                           pipeline_stage=PipelineStage.COLLECTION,
                           structured_data={
                               'url': url,
                               'content_length': len(full_text),
                               'summary_length': len(summary) if summary else 0,
                               'quality_score': quality_score
                           })
                return full_text, summary
            else:
                logger.warning(f"Extracted content too short ({len(full_text) if full_text else 0} chars) from {url}",
                             pipeline_stage=PipelineStage.COLLECTION,
                             error_category=ErrorCategory.VALIDATION_ERROR)
                return None, None
                
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {e}",
                        pipeline_stage=PipelineStage.COLLECTION,
                        error_category=ErrorCategory.NETWORK_ERROR,
                        structured_data={
                            'url': url,
                            'error_type': type(e).__name__,
                            'error_message': str(e)
                        })
            return None, None
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL with retries."""
        for attempt in range(3):
            try:
                # Add random delay to avoid rate limiting
                if attempt > 0:
                    time.sleep(1 + attempt)
                
                response = self.session.get(url, timeout=10, verify=False)
                response.raise_for_status()
                
                # Check if content is HTML
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    logger.warning(f"Non-HTML content type: {content_type} for {url}")
                    return None
                
                return response.text
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/3)")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error for {url}: {e}")
                if attempt == 2:  # Last attempt
                    return None
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return None
        
        return None
    
    def _extract_with_newspaper(self, url: str, html: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract article content using newspaper3k library."""
        try:
            article = NewspaperArticle(url)
            article.download(input_html=html)
            article.parse()
            
            # Get the article text
            full_text = article.text
            
            # Get summary (use article's nlp if available)
            summary = None
            try:
                article.nlp()
                summary = article.summary
            except:
                # If NLP fails, use meta description or first paragraphs
                if article.meta_description:
                    summary = article.meta_description
                elif full_text:
                    paragraphs = full_text.split('\n\n')[:3]
                    summary = ' '.join(paragraphs)[:500]
            
            # Also try to get additional metadata
            if not summary and article.meta_description:
                summary = article.meta_description
            
            return full_text, summary
            
        except Exception as e:
            logger.debug(f"Newspaper3k extraction failed for {url}: {e}",
                        pipeline_stage=PipelineStage.COLLECTION,
                        error_category=ErrorCategory.PARSING_ERROR)
            return None, None
    
    def _extract_with_readability(self, html: str, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract article content using readability library."""
        try:
            doc = Readability(html, url)
            
            # Get the article content
            article_html = doc.summary()
            
            # Convert HTML to text
            soup = BeautifulSoup(article_html, 'html.parser')
            
            # Extract text from paragraphs
            paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            text_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    text_parts.append(text)
            
            full_text = '\n\n'.join(text_parts)
            
            # Get title for summary
            title = doc.short_title() or doc.title()
            
            # Create summary from first paragraphs
            summary = None
            if text_parts:
                summary = ' '.join(text_parts[:3])[:500]
            
            return full_text, summary
            
        except Exception as e:
            logger.debug(f"Readability extraction failed for {url}: {e}",
                        pipeline_stage=PipelineStage.COLLECTION,
                        error_category=ErrorCategory.PARSING_ERROR)
            return None, None
    
    def _extract_with_beautifulsoup(self, html: str, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract article content using BeautifulSoup with multiple strategies."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted elements
            for selector in self.REMOVE_SELECTORS:
                for element in soup.select(selector):
                    element.decompose()
            
            # Strategy 1: Look for Open Graph description (often good summary)
            og_description = None
            og_meta = soup.find('meta', property='og:description')
            if og_meta and og_meta.get('content'):
                og_description = og_meta['content']
            
            # Strategy 2: Try specific content selectors
            article_text = None
            for selector in self.CONTENT_SELECTORS:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Extract text from paragraphs
                    paragraphs = content_elem.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    if paragraphs:
                        text_parts = []
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            if text and len(text) > 20:  # Skip very short paragraphs
                                text_parts.append(text)
                        
                        if text_parts:
                            article_text = '\n\n'.join(text_parts)
                            if len(article_text) >= self.MIN_CONTENT_LENGTH:
                                break
            
            # Strategy 3: Fallback to all paragraphs
            if not article_text or len(article_text) < self.MIN_CONTENT_LENGTH:
                all_paragraphs = soup.find_all('p')
                text_parts = []
                for p in all_paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 50:  # More strict for general paragraphs
                        text_parts.append(text)
                
                if len(text_parts) > 3:  # Need at least a few paragraphs
                    article_text = '\n\n'.join(text_parts)
            
            # Clean up the text
            if article_text:
                article_text = self._clean_text(article_text)
            
            # Generate summary if we don't have one
            summary = og_description
            if not summary and article_text:
                # Take first 2-3 paragraphs as summary
                paragraphs = article_text.split('\n\n')[:3]
                summary = ' '.join(paragraphs)[:500]  # Limit to 500 chars
            
            return article_text, summary
            
        except Exception as e:
            logger.error(f"Error extracting content with BeautifulSoup: {e}",
                        pipeline_stage=PipelineStage.COLLECTION,
                        error_category=ErrorCategory.PARSING_ERROR)
            return None, None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove common artifacts
        text = re.sub(r'Share this article.*?$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Advertisement.*?Continue reading', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Cookie [Pp]olicy.*?Accept', '', text)
        text = re.sub(r'Sign up for.*?newsletter', '', text, flags=re.IGNORECASE)
        
        # Clean up quotes and special characters
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('…', '...')
        
        return text.strip()
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cached_content(self, url: str) -> Optional[Dict]:
        """Get cached content if available and not expired."""
        try:
            cache_key = self._get_cache_key(url)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            
            # Check if cache is expired
            cached_time = datetime.fromisoformat(cached['timestamp'])
            if datetime.now() - cached_time > self.cache_expiry:
                cache_file.unlink()  # Delete expired cache
                return None
            
            return cached
            
        except Exception as e:
            logger.debug(f"Error reading cache for {url}: {e}")
            return None
    
    def _cache_content(self, url: str, full_text: str, summary: Optional[str]):
        """Cache extracted content."""
        try:
            cache_key = self._get_cache_key(url)
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            cache_data = {
                'url': url,
                'full_text': full_text,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.debug(f"Error caching content for {url}: {e}")
    
    def _score_content_quality(self, full_text: str, summary: Optional[str]) -> float:
        """
        Score the quality of extracted content (0.0 to 1.0).
        
        Factors considered:
        - Content length
        - Summary presence and quality
        - Paragraph structure
        - Sentence variety
        - No excessive repetition
        """
        score = 0.0
        
        # Length score (longer is generally better for articles)
        if len(full_text) > 2000:
            score += 0.3
        elif len(full_text) > 1000:
            score += 0.2
        elif len(full_text) > 500:
            score += 0.1
        
        # Summary presence and quality
        if summary:
            if len(summary) > 100:
                score += 0.2
            elif len(summary) > 50:
                score += 0.1
            
            # Check if summary is not just truncated full text
            if not full_text.startswith(summary[:50]):
                score += 0.1
        
        # Paragraph structure (good articles have multiple paragraphs)
        paragraphs = full_text.split('\n\n')
        if len(paragraphs) > 5:
            score += 0.2
        elif len(paragraphs) > 3:
            score += 0.1
        
        # Sentence variety (check for different sentence lengths)
        sentences = re.split(r'[.!?]+', full_text)
        if len(sentences) > 10:
            sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
            if sentence_lengths:
                avg_length = sum(sentence_lengths) / len(sentence_lengths)
                variance = sum((x - avg_length) ** 2 for x in sentence_lengths) / len(sentence_lengths)
                if variance > 20:  # Good variety in sentence lengths
                    score += 0.1
        
        # Check for no excessive repetition (e.g., navigation text repeated)
        lines = full_text.split('\n')
        unique_lines = set(lines)
        if len(unique_lines) / len(lines) > 0.8:  # Most lines are unique
            score += 0.1
        
        return min(score, 1.0)
    
    def clear_cache(self, older_than_days: int = 1):
        """Clear cache files older than specified days."""
        try:
            cutoff = datetime.now() - timedelta(days=older_than_days)
            
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.stat().st_mtime < cutoff.timestamp():
                    cache_file.unlink()
                    
            logger.info(f"Cleared cache files older than {older_than_days} days")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")


# Singleton instance
article_content_fetcher = ArticleContentFetcher()