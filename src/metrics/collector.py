"""
Metrics collector for integrating with existing pipeline components.
"""

import time
import uuid
from datetime import datetime, date
from typing import List, Dict, Any, Optional

try:
    from .database import (
        MetricsDatabase, PipelineRun, CollectionMetrics,
        ProcessingMetrics, AIMetrics, PublishingMetrics
    )
    from ..models import Article, ArticleCluster, AIAnalysis, NewsSource, Newsletter
    from ..config import Config
    from ..logger import get_logger
except ImportError:
    # Fallback for standalone execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from metrics.database import (
        MetricsDatabase, PipelineRun, CollectionMetrics,
        ProcessingMetrics, AIMetrics, PublishingMetrics
    )
    from models import Article, ArticleCluster, AIAnalysis, NewsSource, Newsletter
    from config import Config
    from logger import get_logger

logger = get_logger(__name__)

class MetricsCollector:
    """Collects and stores metrics from pipeline components."""

    def __init__(self, db_path: str = "data/metrics.db"):
        """Initialize metrics collector."""
        self.db = MetricsDatabase(db_path)
        self.current_run_id = None
        self.current_run = None
        self.run_start_time = None

    def start_pipeline_run(self) -> str:
        """Start a new pipeline run and return the run ID."""
        self.current_run_id = str(uuid.uuid4())
        self.run_start_time = datetime.now()

        self.current_run = PipelineRun(
            run_id=self.current_run_id,
            run_date=date.today(),
            start_time=self.run_start_time,
            status="running"
        )

        success = self.db.create_pipeline_run(self.current_run)
        if success:
            logger.info(f"Started pipeline run: {self.current_run_id}")
        else:
            logger.error("Failed to create pipeline run record")

        return self.current_run_id

    def end_pipeline_run(self, success: bool = True, errors: List[str] = None):
        """End the current pipeline run."""
        if not self.current_run:
            logger.warning("No active pipeline run to end")
            return

        end_time = datetime.now()
        processing_time = (end_time - self.run_start_time).total_seconds()

        self.current_run.end_time = end_time
        self.current_run.status = "completed" if success else "failed"
        self.current_run.processing_time_seconds = processing_time

        if errors:
            self.current_run.errors = errors

        success = self.db.update_pipeline_run(self.current_run)
        if success:
            logger.info(f"Ended pipeline run: {self.current_run_id} ({self.current_run.status})")
        else:
            logger.error("Failed to update pipeline run record")

    def collect_collection_metrics(self, sources: List[NewsSource], articles: List[Article],
                                 collection_times: Dict[str, float] = None,
                                 errors: Dict[str, str] = None):
        """Collect metrics from the collection phase."""
        if not self.current_run:
            logger.warning("No active pipeline run for collection metrics")
            return

        # Update pipeline run with total articles collected
        self.current_run.total_articles_collected = len(articles)
        self.db.update_pipeline_run(self.current_run)

        # Collect per-source metrics
        for source in sources:
            source_articles = [a for a in articles if a.source == source.name]
            collection_time = collection_times.get(source.name, 0.0) if collection_times else 0.0
            error_message = errors.get(source.name) if errors else None
            success = error_message is None

            metrics = CollectionMetrics(
                run_id=self.current_run_id,
                source_name=source.name,
                source_category=source.category.value,
                source_tier=source.tier.value,
                articles_collected=len(source_articles),
                collection_time_seconds=collection_time,
                success=success,
                error_message=error_message
            )

            self.db.save_collection_metrics(metrics)

        logger.info(f"Collected metrics for {len(sources)} sources")

    def collect_processing_metrics(self, input_articles: List[Article],
                                 output_clusters: List[ArticleCluster],
                                 processing_time: float):
        """Collect metrics from the processing phase."""
        if not self.current_run:
            logger.warning("No active pipeline run for processing metrics")
            return

        # Calculate processing metrics
        articles_after_deduplication = sum(len(cluster.articles) for cluster in output_clusters)
        duplicates_removed = len(input_articles) - articles_after_deduplication
        deduplication_rate = duplicates_removed / len(input_articles) if input_articles else 0.0

        # Estimate success rate (simplified)
        success_rate = 0.95 if not output_clusters else 1.0  # Assume high success if clusters created

        metrics = ProcessingMetrics(
            run_id=self.current_run_id,
            total_articles_input=len(input_articles),
            articles_after_deduplication=articles_after_deduplication,
            duplicates_removed=duplicates_removed,
            clusters_created=len(output_clusters),
            processing_time_seconds=processing_time,
            deduplication_rate=deduplication_rate,
            success_rate=success_rate
        )

        success = self.db.save_processing_metrics(metrics)
        if success:
            # Update pipeline run
            self.current_run.articles_after_processing = articles_after_deduplication
            self.current_run.clusters_created = len(output_clusters)
            self.db.update_pipeline_run(self.current_run)
            logger.info(f"Collected processing metrics: {len(output_clusters)} clusters created")
        else:
            logger.error("Failed to save processing metrics")

    def collect_ai_metrics(self, analyses: List[AIAnalysis], analysis_time: float,
                          model_used: str = "", mock_mode: bool = False,
                          tokens_used: int = 0, cost: float = 0.0):
        """Collect metrics from AI analysis phase."""
        if not self.current_run:
            logger.warning("No active pipeline run for AI metrics")
            return

        if not analyses:
            logger.info("No AI analyses to collect metrics for")
            return

        # Calculate averages
        avg_confidence = sum(a.confidence for a in analyses) / len(analyses)
        avg_impact_score = sum(a.impact_score for a in analyses) / len(analyses)

        metrics = AIMetrics(
            run_id=self.current_run_id,
            model_used=model_used or Config.AI_MODEL,
            total_tokens_used=tokens_used,
            total_cost=cost,
            stories_analyzed=len(analyses),
            average_confidence=avg_confidence,
            average_impact_score=avg_impact_score,
            analysis_time_seconds=analysis_time,
            mock_mode=mock_mode
        )

        success = self.db.save_ai_metrics(metrics)
        if success:
            # Update pipeline run
            self.current_run.stories_selected = len(analyses)
            self.current_run.ai_tokens_used = tokens_used
            self.current_run.ai_cost = cost
            self.db.update_pipeline_run(self.current_run)
            logger.info(f"Collected AI metrics: {len(analyses)} stories analyzed")
        else:
            logger.error("Failed to save AI metrics")

    def collect_publishing_metrics(self, newsletter: Newsletter,
                                 github_url: str = None,
                                 substack_files: List[str] = None,
                                 notifications_sent: int = 0,
                                 publishing_time: float = 0.0,
                                 success: bool = True):
        """Collect metrics from publishing phase."""
        if not self.current_run:
            logger.warning("No active pipeline run for publishing metrics")
            return

        metrics = PublishingMetrics(
            run_id=self.current_run_id,
            newsletter_date=newsletter.date.date(),
            github_pages_url=github_url,
            substack_exports=substack_files or [],
            email_notifications_sent=notifications_sent,
            publishing_time_seconds=publishing_time,
            success=success
        )

        success = self.db.save_publishing_metrics(metrics)
        if success:
            # Update pipeline run
            self.current_run.newsletter_published = success
            self.db.update_pipeline_run(self.current_run)
            logger.info("Collected publishing metrics")
        else:
            logger.error("Failed to save publishing metrics")

    def get_recent_runs(self, limit: int = 10) -> List[PipelineRun]:
        """Get recent pipeline runs."""
        return self.db.get_recent_pipeline_runs(limit)

    def get_daily_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get daily statistics."""
        return self.db.get_daily_stats(days)

    def get_source_performance(self, days: int = 30) -> Dict[str, Any]:
        """Get source performance metrics."""
        return self.db.get_source_performance(days)

    def get_ai_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get AI usage statistics."""
        return self.db.get_ai_usage_stats(days)

    def get_comprehensive_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive statistics for dashboard."""
        return {
            'daily_stats': self.get_daily_stats(days),
            'source_performance': self.get_source_performance(days),
            'ai_usage': self.get_ai_usage_stats(days),
            'recent_runs': [asdict(run) for run in self.get_recent_runs(10)]
        }

    def close(self):
        """Close database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()