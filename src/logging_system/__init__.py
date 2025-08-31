"""
Enhanced logging system with structured logging, performance monitoring, and error categorization.
"""

from .structured_logger import (
    StructuredLogger, ErrorCategory, PipelineStage, PerformanceProfiler,
    LogRotator, LogAnalyzer, get_structured_logger, setup_structured_logging
)
from .metrics_integration import (
    MetricsIntegration, MetricsAwareLogger, PipelineTracker,
    get_metrics_integration, get_metrics_aware_logger, shutdown_metrics_integration
)
from .error_handler import (
    ErrorClassifier, ErrorHandler, ErrorAggregator,
    error_handler, retry_on_error
)
from .log_analyzer import LogAnalyzer as LogAnalysisTools, LogDashboard

__all__ = [
    # Core logging
    'StructuredLogger', 'get_structured_logger', 'setup_structured_logging',

    # Enums and types
    'ErrorCategory', 'PipelineStage',

    # Performance and utilities
    'PerformanceProfiler', 'LogRotator', 'LogAnalyzer',

    # Metrics integration
    'MetricsIntegration', 'MetricsAwareLogger', 'PipelineTracker',
    'get_metrics_integration', 'get_metrics_aware_logger', 'shutdown_metrics_integration',

    # Error handling
    'ErrorClassifier', 'ErrorHandler', 'ErrorAggregator',
    'error_handler', 'retry_on_error',

    # Analysis tools
    'LogAnalysisTools', 'LogDashboard'
]