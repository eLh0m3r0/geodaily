"""
Content quality validation system with cross-verification and freshness checks.
"""

import time
import hashlib
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from collections import defaultdict

from ..models import Article, ArticleCluster, AIAnalysis
from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage


@dataclass
class ContentQualityMetrics:
    """Metrics for content quality assessment."""
    freshness_score: float = 0.0  # 0.0 to 1.0
    cross_verification_score: float = 0.0  # 0.0 to 1.0
    credibility_score: float = 0.0  # 0.0 to 1.0
    uniqueness_score: float = 0.0  # 0.0 to 1.0
    overall_quality_score: float = 0.0  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)


@dataclass
class ContentValidationResult:
    """Result of content validation."""
    article: Article
    quality_metrics: ContentQualityMetrics
    is_valid: bool
    validation_errors: List[str] = field(default_factory=list)


class ContentQualityValidator:
    """
    Validates content quality through freshness, cross-verification, and credibility checks.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("content_quality_validator")
        self.content_cache: Dict[str, Dict[str, Any]] = {}
        self.duplicate_hashes: Set[str] = set()

        # Quality thresholds
        self.freshness_threshold_hours = 48  # Content older than 48 hours gets lower score
        self.min_cross_verification_sources = 2  # Minimum sources for good cross-verification
        self.min_quality_score = 0.6  # Minimum overall quality score to pass

    def validate_articles(self, articles: List[Article]) -> List[ContentValidationResult]:
        """
        Validate a list of articles for quality.

        Args:
            articles: List of articles to validate

        Returns:
            List of validation results
        """
        self.logger.info("Starting content quality validation",
                        structured_data={'articles_count': len(articles)})

        validation_results = []

        for article in articles:
            try:
                result = self._validate_single_article(article)
                validation_results.append(result)

                if not result.is_valid:
                    self.logger.debug("Article failed quality validation",
                                    structured_data={
                                        'article_title': article.title[:50],
                                        'quality_score': result.quality_metrics.overall_quality_score,
                                        'issues': result.validation_errors
                                    })

            except Exception as e:
                self.logger.error("Error validating article",
                                error_category=ErrorCategory.VALIDATION_ERROR,
                                structured_data={
                                    'article_title': article.title[:50] if article else 'unknown',
                                    'error': str(e)
                                })
                # Create failed validation result
                failed_metrics = ContentQualityMetrics(
                    overall_quality_score=0.0,
                    issues=["Validation error occurred"]
                )
                validation_results.append(ContentValidationResult(
                    article=article,
                    quality_metrics=failed_metrics,
                    is_valid=False,
                    validation_errors=["Validation processing failed"]
                ))

        # Log summary
        valid_count = sum(1 for r in validation_results if r.is_valid)
        self.logger.info("Content quality validation completed",
                        structured_data={
                            'total_articles': len(articles),
                            'valid_articles': valid_count,
                            'invalid_articles': len(articles) - valid_count,
                            'validation_rate': valid_count / len(articles) if articles else 0
                        })

        return validation_results

    def _validate_single_article(self, article: Article) -> ContentValidationResult:
        """Validate a single article."""
        metrics = ContentQualityMetrics()

        # Check freshness
        self._assess_freshness(article, metrics)

        # Check for duplicates
        self._check_duplicates(article, metrics)

        # Assess credibility
        self._assess_credibility(article, metrics)

        # Calculate overall quality score
        self._calculate_overall_score(metrics)

        # Determine if article passes validation
        is_valid = metrics.overall_quality_score >= self.min_quality_score
        validation_errors = []

        if not is_valid:
            if metrics.freshness_score < 0.5:
                validation_errors.append("Content too old")
            if metrics.uniqueness_score < 0.7:
                validation_errors.append("Duplicate or similar content detected")
            if metrics.credibility_score < 0.6:
                validation_errors.append("Low credibility source")
            if metrics.overall_quality_score < self.min_quality_score:
                validation_errors.append(f"Overall quality score too low: {metrics.overall_quality_score:.2f}")

        return ContentValidationResult(
            article=article,
            quality_metrics=metrics,
            is_valid=is_valid,
            validation_errors=validation_errors
        )

    def _assess_freshness(self, article: Article, metrics: ContentQualityMetrics):
        """Assess content freshness."""
        if not article.published_date:
            metrics.freshness_score = 0.3  # Unknown date gets low score
            metrics.issues.append("Publication date unknown")
            return

        # Ensure timezone awareness
        if article.published_date.tzinfo is None:
            article.published_date = article.published_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_hours = (now - article.published_date).total_seconds() / 3600

        if age_hours <= 6:  # Very fresh (6 hours)
            metrics.freshness_score = 1.0
        elif age_hours <= 24:  # Fresh (24 hours)
            metrics.freshness_score = 0.9
        elif age_hours <= self.freshness_threshold_hours:  # Acceptable (48 hours)
            metrics.freshness_score = 0.7
        elif age_hours <= 72:  # Getting old (72 hours)
            metrics.freshness_score = 0.4
        else:  # Too old
            metrics.freshness_score = 0.1
            metrics.issues.append(f"Content too old: {age_hours:.1f} hours")

    def _check_duplicates(self, article: Article, metrics: ContentQualityMetrics):
        """Check for duplicate content."""
        # Create content hash based on title and summary
        content_text = f"{article.title} {article.summary}".lower().strip()
        content_hash = hashlib.md5(content_text.encode()).hexdigest()

        # Check for exact duplicates
        if content_hash in self.duplicate_hashes:
            metrics.uniqueness_score = 0.0
            metrics.issues.append("Exact duplicate content detected")
            return

        # Check for similar content in cache
        similar_found = False
        for cached_hash, cached_data in self.content_cache.items():
            if self._calculate_text_similarity(content_text, cached_data['text']) > 0.85:
                similar_found = True
                break

        if similar_found:
            metrics.uniqueness_score = 0.3
            metrics.issues.append("Similar content already processed")
        else:
            metrics.uniqueness_score = 1.0
            # Cache this content
            self.content_cache[content_hash] = {
                'text': content_text,
                'timestamp': time.time(),
                'source': article.source
            }
            self.duplicate_hashes.add(content_hash)

        # Clean old cache entries (older than 24 hours)
        current_time = time.time()
        self.content_cache = {
            h: d for h, d in self.content_cache.items()
            if current_time - d['timestamp'] < 86400  # 24 hours
        }

    def _assess_credibility(self, article: Article, metrics: ContentQualityMetrics):
        """Assess source credibility."""
        source_category = article.source_category.value
        source_name = article.source.lower()

        # Base credibility scores by source category
        category_scores = {
            'mainstream': 0.8,
            'analysis': 0.9,
            'think_tank': 0.95,
            'regional': 0.7
        }

        base_score = category_scores.get(source_category, 0.5)

        # Boost for reputable sources
        reputable_sources = [
            'reuters', 'ap', 'bloomberg', 'wsj', 'nyt', 'ft', 'bbc',
            'cnn', 'al jazeera', 'guardian', 'economist', 'foreign affairs',
            'csis', 'brookings', 'cfr', 'rand'
        ]

        if any(rep_source in source_name for rep_source in reputable_sources):
            base_score = min(1.0, base_score + 0.1)

        # Penalize for potentially biased sources
        biased_sources = ['rt', 'sputnik', 'global times']
        if any(bias_source in source_name for bias_source in biased_sources):
            base_score = max(0.3, base_score - 0.2)
            metrics.issues.append("Source may have political bias")

        metrics.credibility_score = base_score

    def _calculate_overall_score(self, metrics: ContentQualityMetrics):
        """Calculate overall quality score."""
        # Weighted combination of individual scores
        weights = {
            'freshness': 0.3,
            'credibility': 0.3,
            'uniqueness': 0.25,
            'cross_verification': 0.15
        }

        overall_score = (
            metrics.freshness_score * weights['freshness'] +
            metrics.credibility_score * weights['credibility'] +
            metrics.uniqueness_score * weights['uniqueness'] +
            metrics.cross_verification_score * weights['cross_verification']
        )

        metrics.overall_quality_score = overall_score

    def validate_article_clusters(self, clusters: List[ArticleCluster]) -> List[ArticleCluster]:
        """
        Validate and enhance article clusters with quality metrics.

        Args:
            clusters: List of article clusters to validate

        Returns:
            Filtered and enhanced clusters
        """
        self.logger.info("Validating article clusters",
                        structured_data={'clusters_count': len(clusters)})

        validated_clusters = []

        for cluster in clusters:
            try:
                # Validate all articles in the cluster
                validation_results = self.validate_articles(cluster.articles)

                # Filter to only valid articles
                valid_articles = [result.article for result in validation_results if result.is_valid]

                if len(valid_articles) >= 2:  # Require at least 2 valid articles for a cluster
                    # Create enhanced cluster with quality metrics
                    enhanced_cluster = ArticleCluster(
                        cluster_id=cluster.cluster_id,
                        articles=valid_articles,
                        main_article=valid_articles[0],  # Use first valid article as main
                        cluster_score=self._calculate_cluster_score(validation_results)
                    )
                    validated_clusters.append(enhanced_cluster)

                    self.logger.debug("Cluster validated and enhanced",
                                    structured_data={
                                        'cluster_id': cluster.cluster_id,
                                        'original_articles': len(cluster.articles),
                                        'valid_articles': len(valid_articles),
                                        'cluster_score': enhanced_cluster.cluster_score
                                    })
                else:
                    self.logger.debug("Cluster discarded - insufficient valid articles",
                                    structured_data={
                                        'cluster_id': cluster.cluster_id,
                                        'original_articles': len(cluster.articles),
                                        'valid_articles': len(valid_articles)
                                    })

            except Exception as e:
                self.logger.error("Error validating cluster",
                                error_category=ErrorCategory.VALIDATION_ERROR,
                                structured_data={
                                    'cluster_id': cluster.cluster_id,
                                    'error': str(e)
                                })

        self.logger.info("Article cluster validation completed",
                        structured_data={
                            'original_clusters': len(clusters),
                            'validated_clusters': len(validated_clusters)
                        })

        return validated_clusters

    def _calculate_cluster_score(self, validation_results: List[ContentValidationResult]) -> float:
        """Calculate cluster score based on article quality metrics."""
        if not validation_results:
            return 0.0

        # Average quality scores
        avg_quality = sum(r.quality_metrics.overall_quality_score for r in validation_results) / len(validation_results)

        # Bonus for multiple sources
        source_diversity = len(set(r.article.source for r in validation_results))
        diversity_bonus = min(0.2, source_diversity * 0.05)

        # Bonus for cross-verification
        cross_verification_bonus = 0.0
        if source_diversity >= self.min_cross_verification_sources:
            cross_verification_bonus = 0.1

        return min(1.0, avg_quality + diversity_bonus + cross_verification_bonus)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity score."""
        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def get_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive quality report."""
        return {
            'cache_size': len(self.content_cache),
            'duplicate_count': len(self.duplicate_hashes),
            'freshness_threshold_hours': self.freshness_threshold_hours,
            'min_quality_score': self.min_quality_score,
            'validation_settings': {
                'min_cross_verification_sources': self.min_cross_verification_sources
            }
        }


# Global content quality validator instance
content_quality_validator = ContentQualityValidator()