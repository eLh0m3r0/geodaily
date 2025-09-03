"""
Intelligent Full-Text Article Scraper for enhanced AI analysis.

This module provides comprehensive content extraction capabilities for articles,
enabling Claude to make more informed decisions with full context.
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
from ..models import Article
from ..config import Config

logger = logging.getLogger(__name__)

@dataclass
class ContentExtractionResult:
    """Result of content extraction process."""
    full_content: str
    word_count: int
    extraction_method: str
    quality_score: float
    extraction_time: float
    success: bool
    error_message: Optional[str] = None

class IntelligentContentScraper:
    """Advanced content scraper with intelligent extraction strategies."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.extraction_stats = {
            'total_attempts': 0,
            'successful_extractions': 0,
            'fallback_used': 0,
            'failed_extractions': 0
        }
        
        # Content extraction strategies by domain
        self.domain_strategies = {
            'bbc.co.uk': {
                'selectors': ['div[data-component="text-block"]', 'div.ssrcss-11r1m41-RichTextComponentWrapper', 'p'],
                'remove': ['aside', 'nav', 'footer', '.related-content']
            },
            'theguardian.com': {
                'selectors': ['div[data-gu-name="body"]', 'div.content__article-body', 'p'],
                'remove': ['aside', 'nav', 'footer', '.element-rich-link']
            },
            'foreignaffairs.com': {
                'selectors': ['.article-dropcap-body', '.paywall-fade-container', 'p'],
                'remove': ['aside', 'nav', 'footer', '.paywall']
            },
            'foreignpolicy.com': {
                'selectors': ['.post-content-main', '.article-content', 'p'],
                'remove': ['aside', 'nav', 'footer', '.ad-container']
            },
            'atlanticcouncil.org': {
                'selectors': ['.content', '.article-content', 'p'],
                'remove': ['aside', 'nav', 'footer']
            },
            'csis.org': {
                'selectors': ['.article-content', '.content', 'p'],
                'remove': ['aside', 'nav', 'footer']
            }
        }
        
        # Generic fallback strategy
        self.generic_strategy = {
            'selectors': [
                'article', '.article-body', '.content', '.post-content',
                '.entry-content', '.article-content', 'main', 'p'
            ],
            'remove': [
                'nav', 'footer', 'aside', 'header', '.advertisement',
                '.ad-container', '.social-share', '.related-articles',
                '.comments', '.sidebar', 'script', 'style'
            ]
        }

    async def __aenter__(self):
        """Async context manager entry."""
        timeout = aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={'User-Agent': Config.USER_AGENT}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def extract_full_content(self, article: Article) -> ContentExtractionResult:
        """
        Extract full content from article URL with intelligent strategies.
        
        Args:
            article: Article object with URL to scrape
            
        Returns:
            ContentExtractionResult with extracted content and metadata
        """
        import time
        start_time = time.time()
        self.extraction_stats['total_attempts'] += 1
        
        try:
            print(f"📖 Extracting full content for: {article.title[:50]}...")
            
            # Validate session exists
            if not self.session:
                raise RuntimeError("Session not initialized - use async context manager")
            
            # Try intelligent extraction first
            result = await self._intelligent_extraction(article)
            
            if result.success and result.quality_score > 0.5:
                self.extraction_stats['successful_extractions'] += 1
                result.extraction_time = time.time() - start_time
                logger.info(f"Successfully extracted content: {result.word_count} words, "
                           f"quality: {result.quality_score:.2f}, method: {result.extraction_method}")
                return result
            
            # Fallback to generic extraction
            logger.info(f"Intelligent extraction failed, trying generic strategy")
            fallback_result = await self._generic_extraction(article)
            
            if fallback_result.success:
                self.extraction_stats['fallback_used'] += 1
                fallback_result.extraction_time = time.time() - start_time
                logger.info(f"Fallback extraction succeeded: {fallback_result.word_count} words")
                return fallback_result
            
            # Final fallback to summary
            self.extraction_stats['failed_extractions'] += 1
            logger.warning(f"Content extraction failed, using summary fallback")
            
            return ContentExtractionResult(
                full_content=article.summary,
                word_count=len(article.summary.split()),
                extraction_method="summary_fallback",
                quality_score=0.3,
                extraction_time=time.time() - start_time,
                success=True,
                error_message="Full extraction failed, using summary"
            )
            
        except Exception as e:
            self.extraction_stats['failed_extractions'] += 1
            logger.error(f"Content extraction error for {article.url}: {e}")
            
            return ContentExtractionResult(
                full_content=article.summary,
                word_count=len(article.summary.split()),
                extraction_method="error_fallback",
                quality_score=0.2,
                extraction_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )

    async def _intelligent_extraction(self, article: Article) -> ContentExtractionResult:
        """Extract content using domain-specific intelligent strategies."""
        domain = urlparse(article.url).netloc.lower()
        
        # Find matching domain strategy
        strategy = None
        for domain_key, domain_strategy in self.domain_strategies.items():
            if domain_key in domain:
                strategy = domain_strategy
                break
        
        if not strategy:
            return await self._generic_extraction(article)
        
        try:
            async with self.session.get(article.url, ssl=False) as response:
                if response.status != 200:
                    return ContentExtractionResult(
                        full_content="", word_count=0, extraction_method="intelligent_failed",
                        quality_score=0.0, extraction_time=0, success=False,
                        error_message=f"HTTP {response.status}"
                    )
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove unwanted elements
                for selector in strategy.get('remove', []):
                    for element in soup.select(selector):
                        element.decompose()
                
                # Extract content using prioritized selectors with memory limit
                content_parts = []
                total_length = 0
                max_content_length = 50000  # Character limit to prevent memory issues
                
                for selector in strategy['selectors']:
                    elements = soup.select(selector)
                    if elements:
                        for element in elements:
                            text = element.get_text(strip=True)
                            if len(text) > 50 and total_length + len(text) < max_content_length:
                                content_parts.append(text)
                                total_length += len(text)
                            elif total_length >= max_content_length:
                                break
                    if total_length >= max_content_length:
                        break
                
                if content_parts:
                    full_content = ' '.join(content_parts)
                    cleaned_content = self._clean_content(full_content)
                    quality_score = self._assess_quality(cleaned_content, article)
                    
                    return ContentExtractionResult(
                        full_content=cleaned_content,
                        word_count=len(cleaned_content.split()),
                        extraction_method=f"intelligent_{domain}",
                        quality_score=quality_score,
                        extraction_time=0,
                        success=True
                    )
                
                return ContentExtractionResult(
                    full_content="", word_count=0, extraction_method="intelligent_empty",
                    quality_score=0.0, extraction_time=0, success=False,
                    error_message="No content found with intelligent selectors"
                )
                
        except Exception as e:
            return ContentExtractionResult(
                full_content="", word_count=0, extraction_method="intelligent_error",
                quality_score=0.0, extraction_time=0, success=False,
                error_message=str(e)
            )

    async def _generic_extraction(self, article: Article) -> ContentExtractionResult:
        """Fallback generic content extraction."""
        try:
            async with self.session.get(article.url, ssl=False) as response:
                if response.status != 200:
                    return ContentExtractionResult(
                        full_content="", word_count=0, extraction_method="generic_failed",
                        quality_score=0.0, extraction_time=0, success=False,
                        error_message=f"HTTP {response.status}"
                    )
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove unwanted elements
                for selector in self.generic_strategy['remove']:
                    for element in soup.select(selector):
                        element.decompose()
                
                # Try different content extraction methods
                content_parts = []
                
                # Method 1: Try article tag
                article_tag = soup.find('article')
                if article_tag:
                    content_parts.append(article_tag.get_text(strip=True))
                
                # Method 2: Try common content selectors
                if not content_parts:
                    for selector in self.generic_strategy['selectors']:
                        elements = soup.select(selector)
                        if elements:
                            for element in elements:
                                text = element.get_text(strip=True)
                                if len(text) > 100:
                                    content_parts.append(text)
                            if content_parts:
                                break
                
                # Method 3: Fallback to all paragraphs
                if not content_parts:
                    paragraphs = soup.find_all('p')
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if len(text) > 50:
                            content_parts.append(text)
                
                if content_parts:
                    full_content = ' '.join(content_parts)
                    cleaned_content = self._clean_content(full_content)
                    quality_score = self._assess_quality(cleaned_content, article)
                    
                    return ContentExtractionResult(
                        full_content=cleaned_content,
                        word_count=len(cleaned_content.split()),
                        extraction_method="generic",
                        quality_score=quality_score,
                        extraction_time=0,
                        success=True
                    )
                
                return ContentExtractionResult(
                    full_content="", word_count=0, extraction_method="generic_empty",
                    quality_score=0.0, extraction_time=0, success=False,
                    error_message="No content found with generic selectors"
                )
                
        except Exception as e:
            return ContentExtractionResult(
                full_content="", word_count=0, extraction_method="generic_error",
                quality_score=0.0, extraction_time=0, success=False,
                error_message=str(e)
            )

    def _clean_content(self, content: str) -> str:
        """Clean and normalize extracted content."""
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove common noise patterns
        noise_patterns = [
            r'Advertisement\s*',
            r'Subscribe to.*?Newsletter',
            r'Follow us on.*?Twitter',
            r'Copyright.*?reserved',
            r'All rights reserved',
            r'Click here to.*?',
            r'Read more:.*?',
            r'Share this article:.*?',
        ]
        
        for pattern in noise_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Limit content length for AI processing (Claude has token limits)
        max_words = 1500  # Roughly 2000 tokens
        words = content.split()
        if len(words) > max_words:
            content = ' '.join(words[:max_words]) + '... [Content truncated for AI processing]'
        
        return content.strip()

    def _assess_quality(self, content: str, article: Article) -> float:
        """Assess the quality of extracted content."""
        if not content:
            return 0.0
        
        quality_score = 0.0
        word_count = len(content.split())
        
        # Word count scoring
        if word_count > 100:
            quality_score += 0.3
        if word_count > 300:
            quality_score += 0.2
        if word_count > 500:
            quality_score += 0.2
        
        # Content richness scoring
        if any(keyword in content.lower() for keyword in ['analysis', 'experts', 'sources', 'according to']):
            quality_score += 0.1
        
        # Coherence with title/summary
        title_words = set(article.title.lower().split())
        content_words = set(content.lower().split())
        overlap = len(title_words & content_words) / len(title_words) if title_words else 0
        quality_score += overlap * 0.2
        
        return min(1.0, quality_score)

    async def enrich_articles_batch(self, articles: List[Article]) -> List[Tuple[Article, ContentExtractionResult]]:
        """
        Enrich a batch of articles with full content extraction.
        
        Args:
            articles: List of articles to enrich
            
        Returns:
            List of (article, extraction_result) tuples
        """
        print(f"📚 Starting batch content extraction for {len(articles)} articles...")
        
        # Process articles concurrently but with rate limiting
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def extract_with_semaphore(article):
            async with semaphore:
                try:
                    return article, await self.extract_full_content(article)
                except Exception as e:
                    logger.error(f"Individual extraction error for {article.title}: {e}")
                    return article, ContentExtractionResult(
                        full_content=article.summary,
                        word_count=len(article.summary.split()),
                        extraction_method="error_fallback",
                        quality_score=0.2,
                        extraction_time=0,
                        success=False,
                        error_message=str(e)
                    )
        
        tasks = [extract_with_semaphore(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful extractions
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch extraction error: {result}")
            else:
                successful_results.append(result)
        
        self._log_extraction_stats()
        return successful_results

    def _log_extraction_stats(self):
        """Log extraction statistics."""
        stats = self.extraction_stats
        total = stats['total_attempts']
        success_rate = (stats['successful_extractions'] / total * 100) if total > 0 else 0
        fallback_rate = (stats['fallback_used'] / total * 100) if total > 0 else 0
        
        logger.info(f"Content extraction stats: {success_rate:.1f}% success rate, "
                   f"{fallback_rate:.1f}% fallback rate, "
                   f"{total} total attempts")
        
        print(f"📊 Content Extraction Stats:")
        print(f"   • Total attempts: {total}")
        print(f"   • Successful: {stats['successful_extractions']} ({success_rate:.1f}%)")
        print(f"   • Fallback used: {stats['fallback_used']} ({fallback_rate:.1f}%)")
        print(f"   • Failed: {stats['failed_extractions']}")

# Convenience function for easy usage
async def enrich_articles_with_content(articles: List[Article]) -> List[Tuple[Article, ContentExtractionResult]]:
    """Convenience function to enrich articles with full content."""
    async with IntelligentContentScraper() as scraper:
        return await scraper.enrich_articles_batch(articles)