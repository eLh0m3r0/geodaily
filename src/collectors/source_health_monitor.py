"""
Source health monitoring and failover system for news collection.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..models import NewsSource, SourceTier, SourceCategory
from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from ..config import Config


class SourceHealthStatus(Enum):
    """Health status of a news source."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class SourceHealthMetrics:
    """Health metrics for a news source."""
    source_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None
    average_response_time: float = 0.0
    last_response_time: float = 0.0
    error_types: Dict[str, int] = field(default_factory=dict)
    health_score: float = 1.0  # 0.0 to 1.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def is_healthy(self) -> bool:
        """Check if source is currently healthy."""
        return (self.health_score >= 0.7 and
                self.consecutive_failures < 3 and
                self.success_rate >= 0.5)

    def update_health_score(self):
        """Update the health score based on recent performance."""
        # Base score on success rate
        score = self.success_rate

        # Penalize consecutive failures
        if self.consecutive_failures > 0:
            score *= max(0.1, 1.0 - (self.consecutive_failures * 0.2))

        # Penalize recent failures
        if self.last_failure_time:
            hours_since_failure = (time.time() - self.last_failure_time) / 3600
            if hours_since_failure < 24:  # Within last 24 hours
                score *= max(0.5, 1.0 - (24 - hours_since_failure) / 24)

        # Bonus for recent success
        if self.last_success_time:
            hours_since_success = (time.time() - self.last_success_time) / 3600
            if hours_since_success < 1:  # Within last hour
                score *= 1.1

        self.health_score = min(1.0, max(0.0, score))


@dataclass
class SourceFailoverConfig:
    """Configuration for source failover."""
    primary_sources: List[str]
    backup_sources: List[str]
    min_healthy_sources: int = 3
    failover_threshold: float = 0.3  # Health score threshold for failover
    recovery_check_interval: int = 300  # 5 minutes


class SourceHealthMonitor:
    """
    Monitors health of news sources and manages failover.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("source_health_monitor")
        self.source_metrics: Dict[str, SourceHealthMetrics] = {}
        self.failover_configs: Dict[str, SourceFailoverConfig] = {}
        self.disabled_sources: Set[str] = set()
        self.monitoring_active = False
        self._lock = threading.RLock()

    def register_source(self, source: NewsSource):
        """Register a source for health monitoring."""
        with self._lock:
            if source.name not in self.source_metrics:
                self.source_metrics[source.name] = SourceHealthMetrics(
                    source_name=source.name
                )
                self.logger.info("Source registered for health monitoring",
                               structured_data={'source_name': source.name})

    def record_request_result(self, source_name: str, success: bool,
                            response_time: float = 0.0, error_type: str = None):
        """Record the result of a request to a source."""
        with self._lock:
            if source_name not in self.source_metrics:
                self.register_source(NewsSource(name=source_name, url="", category=SourceCategory.MAINSTREAM, tier=SourceTier.TIER1_RSS))

            metrics = self.source_metrics[source_name]
            metrics.total_requests += 1
            metrics.last_response_time = response_time
            metrics.average_response_time = (
                (metrics.average_response_time * (metrics.total_requests - 1) + response_time)
                / metrics.total_requests
            )

            if success:
                metrics.successful_requests += 1
                metrics.consecutive_failures = 0
                metrics.last_success_time = time.time()
            else:
                metrics.failed_requests += 1
                metrics.consecutive_failures += 1
                metrics.last_failure_time = time.time()

                if error_type:
                    metrics.error_types[error_type] = metrics.error_types.get(error_type, 0) + 1

            # Update health score
            metrics.update_health_score()

            # Log significant events
            self._log_health_event(source_name, metrics, success, error_type)

    def get_source_health_status(self, source_name: str) -> Optional[SourceHealthStatus]:
        """Get the health status of a source."""
        with self._lock:
            metrics = self.source_metrics.get(source_name)
            if not metrics:
                return None

            if source_name in self.disabled_sources:
                return SourceHealthStatus.DISABLED
            elif not metrics.is_healthy:
                return SourceHealthStatus.FAILED
            elif metrics.health_score < 0.8:
                return SourceHealthStatus.DEGRADED
            else:
                return SourceHealthStatus.HEALTHY

    def get_healthy_sources(self, sources: List[NewsSource]) -> List[NewsSource]:
        """Filter sources to return only healthy ones."""
        with self._lock:
            healthy_sources = []
            for source in sources:
                status = self.get_source_health_status(source.name)
                if status in [SourceHealthStatus.HEALTHY, SourceHealthStatus.DEGRADED]:
                    healthy_sources.append(source)
                else:
                    self.logger.debug("Skipping unhealthy source",
                                    structured_data={
                                        'source_name': source.name,
                                        'status': status.value if status else 'unknown',
                                        'health_score': self.source_metrics.get(source.name, SourceHealthMetrics(source.name)).health_score
                                    })
            return healthy_sources

    def setup_failover_groups(self, category: SourceCategory, sources: List[NewsSource]):
        """Set up failover groups for a category of sources."""
        with self._lock:
            # Group sources by tier
            tier1_sources = [s.name for s in sources if s.tier == SourceTier.TIER1_RSS]
            tier2_sources = [s.name for s in sources if s.tier == SourceTier.TIER2_SCRAPING]

            # Create failover config: prefer RSS, fallback to scraping
            config = SourceFailoverConfig(
                primary_sources=tier1_sources,
                backup_sources=tier2_sources,
                min_healthy_sources=max(2, len(sources) // 2)
            )

            self.failover_configs[category.value] = config

            self.logger.info("Failover group configured",
                           structured_data={
                               'category': category.value,
                               'primary_sources': len(tier1_sources),
                               'backup_sources': len(tier2_sources),
                               'min_healthy_sources': config.min_healthy_sources
                           })

    def get_sources_for_collection(self, category: SourceCategory,
                                 all_sources: List[NewsSource]) -> List[NewsSource]:
        """Get sources for collection, implementing failover logic."""
        with self._lock:
            config = self.failover_configs.get(category.value)
            if not config:
                # No failover config, return all healthy sources
                return self.get_healthy_sources(all_sources)

            # Get healthy sources from primary and backup lists
            primary_healthy = []
            backup_healthy = []

            for source in all_sources:
                if source.name in config.primary_sources:
                    status = self.get_source_health_status(source.name)
                    if status in [SourceHealthStatus.HEALTHY, SourceHealthStatus.DEGRADED]:
                        primary_healthy.append(source)
                elif source.name in config.backup_sources:
                    status = self.get_source_health_status(source.name)
                    if status in [SourceHealthStatus.HEALTHY, SourceHealthStatus.DEGRADED]:
                        backup_healthy.append(source)

            # Prioritize primary sources, but ensure minimum healthy sources
            selected_sources = primary_healthy[:]

            if len(selected_sources) < config.min_healthy_sources:
                # Add backup sources to meet minimum
                needed = config.min_healthy_sources - len(selected_sources)
                selected_sources.extend(backup_healthy[:needed])

            # If still not enough, add any remaining healthy sources
            if len(selected_sources) < config.min_healthy_sources:
                remaining_sources = [s for s in all_sources
                                   if s not in selected_sources and
                                   self.get_source_health_status(s.name) in
                                   [SourceHealthStatus.HEALTHY, SourceHealthStatus.DEGRADED]]
                needed = config.min_healthy_sources - len(selected_sources)
                selected_sources.extend(remaining_sources[:needed])

            self.logger.info("Sources selected for collection",
                           structured_data={
                               'category': category.value,
                               'total_available': len(all_sources),
                               'primary_healthy': len(primary_healthy),
                               'backup_healthy': len(backup_healthy),
                               'selected': len(selected_sources),
                               'selected_names': [s.name for s in selected_sources]
                           })

            return selected_sources

    def disable_source(self, source_name: str, reason: str = "manual"):
        """Temporarily disable a source."""
        with self._lock:
            self.disabled_sources.add(source_name)
            self.logger.warning("Source disabled",
                              structured_data={
                                  'source_name': source_name,
                                  'reason': reason
                              })

    def enable_source(self, source_name: str):
        """Re-enable a disabled source."""
        with self._lock:
            self.disabled_sources.discard(source_name)
            if source_name in self.source_metrics:
                # Reset consecutive failures on re-enable
                self.source_metrics[source_name].consecutive_failures = 0
            self.logger.info("Source re-enabled",
                           structured_data={'source_name': source_name})

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        with self._lock:
            report = {
                'timestamp': time.time(),
                'total_sources': len(self.source_metrics),
                'disabled_sources': list(self.disabled_sources),
                'source_health': {},
                'overall_stats': {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'average_success_rate': 0.0
                }
            }

            total_success_rate = 0.0
            active_sources = 0

            for name, metrics in self.source_metrics.items():
                if name not in self.disabled_sources:
                    active_sources += 1
                    total_success_rate += metrics.success_rate

                    report['overall_stats']['total_requests'] += metrics.total_requests
                    report['overall_stats']['successful_requests'] += metrics.successful_requests
                    report['overall_stats']['failed_requests'] += metrics.failed_requests

                report['source_health'][name] = {
                    'status': self.get_source_health_status(name).value if self.get_source_health_status(name) else 'unknown',
                    'health_score': metrics.health_score,
                    'success_rate': metrics.success_rate,
                    'total_requests': metrics.total_requests,
                    'consecutive_failures': metrics.consecutive_failures,
                    'average_response_time': metrics.average_response_time,
                    'last_success_time': metrics.last_success_time,
                    'last_failure_time': metrics.last_failure_time,
                    'error_types': metrics.error_types,
                    'disabled': name in self.disabled_sources
                }

            if active_sources > 0:
                report['overall_stats']['average_success_rate'] = total_success_rate / active_sources

            return report

    def _log_health_event(self, source_name: str, metrics: SourceHealthMetrics,
                         success: bool, error_type: str = None):
        """Log significant health events."""
        if not success:
            # Log failures
            if metrics.consecutive_failures in [1, 3, 5, 10]:
                self.logger.warning("Source health deteriorating",
                                  error_category=ErrorCategory.NETWORK_ERROR,
                                  structured_data={
                                      'source_name': source_name,
                                      'consecutive_failures': metrics.consecutive_failures,
                                      'health_score': metrics.health_score,
                                      'error_type': error_type,
                                      'success_rate': metrics.success_rate
                                  })
        elif metrics.consecutive_failures >= 3 and success:
            # Log recovery
            self.logger.info("Source recovered from failures",
                           structured_data={
                               'source_name': source_name,
                               'previous_failures': metrics.consecutive_failures,
                               'health_score': metrics.health_score,
                               'success_rate': metrics.success_rate
                           })


# Global source health monitor instance
source_health_monitor = SourceHealthMonitor()