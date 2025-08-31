"""
Integration between structured logging and metrics collection system.
"""

import threading
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from queue import Queue
import json

from .structured_logger import StructuredLogger, ErrorCategory, PipelineStage
from ..config import Config


class MetricsIntegration:
    """Integrates structured logging with metrics collection."""

    def __init__(self, metrics_collector: Optional["MetricsCollector"] = None):
        """Initialize metrics integration."""
        self.metrics_collector = metrics_collector
        self.logger = StructuredLogger("metrics_integration")
        self._event_queue = Queue()
        self._processing_thread = None
        self._stop_processing = False

        # Start background processing
        self._start_background_processing()

    def _start_background_processing(self):
        """Start background thread for processing log events."""
        self._processing_thread = threading.Thread(
            target=self._process_events,
            daemon=True,
            name="metrics-integration"
        )
        self._processing_thread.start()

    def _process_events(self):
        """Process queued log events in background."""
        while not self._stop_processing:
            try:
                # Get event with timeout
                event = self._event_queue.get(timeout=1.0)

                # Process the event
                self._handle_log_event(event)

                # Mark task as done
                self._event_queue.task_done()

            except Exception as e:
                # Log processing errors but don't crash
                if not self._stop_processing:
                    print(f"Metrics integration error: {e}")

    def _handle_log_event(self, event: Dict[str, Any]):
        """Handle a log event for metrics collection."""
        try:
            level = event.get('level', 'INFO')
            pipeline_stage = event.get('pipeline_stage')
            error_category = event.get('error_category')
            performance_data = event.get('performance_data', {})
            contextual_data = event.get('contextual_data', {})

            # Track errors by category
            if level in ['ERROR', 'CRITICAL'] and error_category:
                self._track_error_metrics(error_category, event)

            # Track performance metrics
            if performance_data:
                self._track_performance_metrics(performance_data, pipeline_stage)

            # Track pipeline stage metrics
            if pipeline_stage:
                self._track_pipeline_metrics(pipeline_stage, level, event)

        except Exception as e:
            self.logger.error(f"Failed to process log event for metrics: {e}",
                            error_category=ErrorCategory.UNKNOWN_ERROR)

    def _track_error_metrics(self, error_category: str, event: Dict[str, Any]):
        """Track error metrics by category."""
        if not self.metrics_collector:
            return

        # This would typically update error counters in the metrics database
        # For now, we'll log the error tracking
        self.logger.info("Error tracked for metrics",
                        pipeline_stage=PipelineStage.CLEANUP,
                        structured_data={
                            'error_category': error_category,
                            'timestamp': event.get('timestamp'),
                            'logger_name': event.get('logger_name')
                        })

    def _track_performance_metrics(self, performance_data: Dict[str, Any],
                                 pipeline_stage: Optional[str]):
        """Track performance metrics."""
        if not self.metrics_collector:
            return

        # Extract performance data
        execution_time = performance_data.get('execution_time_seconds', 0)
        memory_delta = performance_data.get('memory_delta_mb', 0)
        cpu_usage = performance_data.get('cpu_usage_percent', 0)
        operation = performance_data.get('operation', 'unknown')

        # Log performance tracking
        self.logger.info("Performance metrics tracked",
                        pipeline_stage=PipelineStage.CLEANUP,
                        structured_data={
                            'operation': operation,
                            'execution_time': execution_time,
                            'memory_delta': memory_delta,
                            'cpu_usage': cpu_usage,
                            'stage': pipeline_stage
                        })

    def _track_pipeline_metrics(self, pipeline_stage: str, level: str, event: Dict[str, Any]):
        """Track pipeline stage metrics."""
        if not self.metrics_collector:
            return

        # Track stage completion, errors, etc.
        self.logger.info("Pipeline stage metrics tracked",
                        pipeline_stage=PipelineStage.CLEANUP,
                        structured_data={
                            'tracked_stage': pipeline_stage,
                            'log_level': level,
                            'timestamp': event.get('timestamp')
                        })

    def log_event(self, event: Dict[str, Any]):
        """Queue a log event for processing."""
        if not self._stop_processing:
            self._event_queue.put(event)

    def shutdown(self):
        """Shutdown the metrics integration."""
        self._stop_processing = True
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)

        # Process remaining events
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                self._handle_log_event(event)
                self._event_queue.task_done()
            except Exception:
                break


class MetricsAwareLogger(StructuredLogger):
    """Structured logger with automatic metrics integration."""

    def __init__(self, name: str, run_id: Optional[str] = None,
                 metrics_integration: Optional[MetricsIntegration] = None):
        """Initialize metrics-aware logger."""
        super().__init__(name, run_id)
        self.metrics_integration = metrics_integration

    def _log_with_context(self, level: int, message: str,
                         pipeline_stage: Optional[PipelineStage] = None,
                         error_category: Optional[ErrorCategory] = None,
                         structured_data: Optional[Dict[str, Any]] = None,
                         performance_data: Optional[Dict[str, Any]] = None,
                         run_id: Optional[str] = None):
        """Log message with structured context and metrics integration."""
        # Call parent method
        super()._log_with_context(level, message, pipeline_stage, error_category,
                                structured_data, performance_data, run_id)

        # Send to metrics integration if available
        if self.metrics_integration:
            # Create event dict for metrics processing
            event = {
                'timestamp': datetime.now().isoformat(),
                'level': logging.getLevelName(level),
                'logger_name': self.name,
                'message': message,
                'pipeline_stage': pipeline_stage.value if pipeline_stage else None,
                'run_id': self.run_id,
                'error_category': error_category.value if error_category else None,
                'performance_data': performance_data,
                'contextual_data': structured_data
            }
            self.metrics_integration.log_event(event)


# Global metrics integration instance
_metrics_integration = None
_metrics_lock = threading.Lock()


def get_metrics_integration(metrics_collector: Optional["MetricsCollector"] = None) -> MetricsIntegration:
    """Get or create global metrics integration instance."""
    global _metrics_integration

    with _metrics_lock:
        if _metrics_integration is None:
            _metrics_integration = MetricsIntegration(metrics_collector)

    return _metrics_integration


def get_metrics_aware_logger(name: str, run_id: Optional[str] = None,
                            metrics_collector: Optional["MetricsCollector"] = None) -> MetricsAwareLogger:
    """Get a metrics-aware logger instance."""
    metrics_integration = get_metrics_integration(metrics_collector)
    return MetricsAwareLogger(name, run_id, metrics_integration)


def shutdown_metrics_integration():
    """Shutdown global metrics integration."""
    global _metrics_integration

    with _metrics_lock:
        if _metrics_integration:
            _metrics_integration.shutdown()
            _metrics_integration = None


# Pipeline success tracking
class PipelineTracker:
    """Tracks pipeline success and failure patterns."""

    def __init__(self, logger: StructuredLogger):
        """Initialize pipeline tracker."""
        self.logger = logger
        self.pipeline_stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'stage_failures': {},
            'error_patterns': {},
            'performance_history': []
        }

    def track_pipeline_start(self, run_id: str, pipeline_stage: PipelineStage = PipelineStage.INITIALIZATION):
        """Track pipeline start."""
        self.pipeline_stats['total_runs'] += 1

        self.logger.info("Pipeline started",
                        pipeline_stage=pipeline_stage,
                        run_id=run_id,
                        structured_data={
                            'total_runs': self.pipeline_stats['total_runs']
                        })

    def track_pipeline_success(self, run_id: str, execution_time: float,
                             pipeline_stage: PipelineStage = PipelineStage.CLEANUP):
        """Track successful pipeline completion."""
        self.pipeline_stats['successful_runs'] += 1

        success_rate = self.pipeline_stats['successful_runs'] / self.pipeline_stats['total_runs']

        self.logger.info("Pipeline completed successfully",
                        pipeline_stage=pipeline_stage,
                        run_id=run_id,
                        structured_data={
                            'execution_time_seconds': execution_time,
                            'success_rate': success_rate,
                            'successful_runs': self.pipeline_stats['successful_runs'],
                            'total_runs': self.pipeline_stats['total_runs']
                        })

    def track_pipeline_failure(self, run_id: str, error: Exception,
                             pipeline_stage: PipelineStage = PipelineStage.CLEANUP,
                             error_category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR):
        """Track pipeline failure."""
        self.pipeline_stats['failed_runs'] += 1

        # Track stage failures
        stage_key = pipeline_stage.value
        self.pipeline_stats['stage_failures'][stage_key] = \
            self.pipeline_stats['stage_failures'].get(stage_key, 0) + 1

        # Track error patterns
        error_type = type(error).__name__
        self.pipeline_stats['error_patterns'][error_type] = \
            self.pipeline_stats['error_patterns'].get(error_type, 0) + 1

        failure_rate = self.pipeline_stats['failed_runs'] / self.pipeline_stats['total_runs']

        self.logger.error("Pipeline failed",
                         pipeline_stage=pipeline_stage,
                         run_id=run_id,
                         error_category=error_category,
                         structured_data={
                            'error_type': error_type,
                            'failure_rate': failure_rate,
                            'failed_runs': self.pipeline_stats['failed_runs'],
                            'total_runs': self.pipeline_stats['total_runs'],
                            'stage_failures': self.pipeline_stats['stage_failures'],
                            'error_patterns': self.pipeline_stats['error_patterns']
                         })

    def track_stage_completion(self, run_id: str, stage: PipelineStage,
                             execution_time: float, success: bool = True):
        """Track individual pipeline stage completion."""
        status = "completed" if success else "failed"

        self.logger.info(f"Pipeline stage {status}: {stage.value}",
                        pipeline_stage=stage,
                        run_id=run_id,
                        structured_data={
                            'stage': stage.value,
                            'execution_time_seconds': execution_time,
                            'success': success
                        })

    def get_success_stats(self) -> Dict[str, Any]:
        """Get pipeline success statistics."""
        total_runs = self.pipeline_stats['total_runs']
        if total_runs == 0:
            return {'success_rate': 0.0, 'total_runs': 0}

        success_rate = self.pipeline_stats['successful_runs'] / total_runs
        failure_rate = self.pipeline_stats['failed_runs'] / total_runs

        return {
            'success_rate': success_rate,
            'failure_rate': failure_rate,
            'total_runs': total_runs,
            'successful_runs': self.pipeline_stats['successful_runs'],
            'failed_runs': self.pipeline_stats['failed_runs'],
            'stage_failure_rates': self.pipeline_stats['stage_failures'],
            'common_error_patterns': self.pipeline_stats['error_patterns']
        }