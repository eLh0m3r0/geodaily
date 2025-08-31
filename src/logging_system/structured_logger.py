"""
Structured logging system with JSON formatting, performance monitoring, and error categorization.
"""

import json
import logging
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
from functools import wraps

from ..config import Config

# Optional import for performance monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False


class ErrorCategory(Enum):
    """Error categories for classification."""
    API_ERROR = "api"
    NETWORK_ERROR = "network"
    PARSING_ERROR = "parsing"
    DATABASE_ERROR = "database"
    CONFIGURATION_ERROR = "configuration"
    VALIDATION_ERROR = "validation"
    TIMEOUT_ERROR = "timeout"
    AUTHENTICATION_ERROR = "authentication"
    RATE_LIMIT_ERROR = "rate_limit"
    UNKNOWN_ERROR = "unknown"


class PipelineStage(Enum):
    """Pipeline stages for tracking."""
    INITIALIZATION = "initialization"
    CONFIGURATION = "configuration"
    COLLECTION = "collection"
    PROCESSING = "processing"
    AI_ANALYSIS = "ai_analysis"
    GENERATION = "generation"
    PUBLISHING = "publishing"
    NOTIFICATION = "notification"
    CLEANUP = "cleanup"


@dataclass
class PerformanceMetrics:
    """Performance metrics for logging."""
    execution_time_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    timestamp: datetime


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    level: str
    logger_name: str
    message: str
    pipeline_stage: Optional[str] = None
    run_id: Optional[str] = None
    error_category: Optional[str] = None
    performance_data: Optional[Dict[str, Any]] = None
    contextual_data: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Extract structured data from record
        structured_data = getattr(record, 'structured_data', {})
        performance_data = getattr(record, 'performance_data', None)
        error_category = getattr(record, 'error_category', None)
        pipeline_stage = getattr(record, 'pipeline_stage', None)
        run_id = getattr(record, 'run_id', None)

        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
            pipeline_stage=pipeline_stage,
            run_id=run_id,
            error_category=error_category,
            performance_data=performance_data,
            contextual_data=structured_data,
            stack_trace=self.formatException(record.exc_info) if record.exc_info else None
        )

        return json.dumps(asdict(log_entry), default=str, ensure_ascii=False)


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""

    def __init__(self, name: str, run_id: Optional[str] = None):
        """Initialize structured logger."""
        self.name = name
        self.run_id = run_id
        self.logger = logging.getLogger(name)
        self._setup_logger()

    def _setup_logger(self):
        """Set up logger with JSON formatting."""
        # Clear existing handlers
        self.logger.handlers.clear()

        # Set level
        log_level = getattr(logging, Config.LOG_LEVEL.upper())
        self.logger.setLevel(log_level)

        # JSON formatter
        formatter = JSONFormatter()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler with rotation
        log_file = self._get_log_file_path()
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _get_log_file_path(self) -> Path:
        """Get log file path with date-based naming."""
        timestamp = datetime.now().strftime("%Y%m%d")
        return Config.LOGS_DIR / f"geodaily_{timestamp}.log"

    def _log_with_context(self, level: int, message: str,
                         pipeline_stage: Optional[PipelineStage] = None,
                         error_category: Optional[ErrorCategory] = None,
                         structured_data: Optional[Dict[str, Any]] = None,
                         performance_data: Optional[Dict[str, Any]] = None,
                         run_id: Optional[str] = None):
        """Log message with structured context."""
        # Add context to log record
        extra = {}
        if pipeline_stage:
            extra['pipeline_stage'] = pipeline_stage.value
        if error_category:
            extra['error_category'] = error_category.value
        # Use provided run_id or fall back to self.run_id
        current_run_id = run_id or self.run_id
        if current_run_id:
            extra['run_id'] = current_run_id
        if structured_data:
            extra['structured_data'] = structured_data
        if performance_data:
            extra['performance_data'] = performance_data

        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **context):
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, **context)

    def info(self, message: str, **context):
        """Log info message."""
        self._log_with_context(logging.INFO, message, **context)

    def warning(self, message: str, **context):
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, **context)

    def error(self, message: str, error_category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR, **context):
        """Log error message with categorization."""
        context['error_category'] = error_category
        self._log_with_context(logging.ERROR, message, **context)

    def critical(self, message: str, error_category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR, **context):
        """Log critical message with categorization."""
        context['error_category'] = error_category
        self._log_with_context(logging.CRITICAL, message, **context)

    def exception(self, message: str, error_category: ErrorCategory = ErrorCategory.UNKNOWN_ERROR, **context):
        """Log exception with categorization."""
        context['error_category'] = error_category
        self.logger.exception(message, extra=context)


class PerformanceProfiler:
    """Performance profiling utilities."""

    @staticmethod
    @contextmanager
    def profile_operation(operation_name: str, logger: StructuredLogger):
        """Context manager for profiling operations."""
        start_time = time.time()

        if PSUTIL_AVAILABLE:
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            start_cpu = psutil.cpu_percent(interval=None)
        else:
            start_memory = 0
            start_cpu = 0

        try:
            yield
        finally:
            end_time = time.time()

            if PSUTIL_AVAILABLE:
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                end_cpu = psutil.cpu_percent(interval=None)
                memory_usage = end_memory - start_memory
                cpu_usage = (start_cpu + end_cpu) / 2  # Average CPU usage
            else:
                memory_usage = 0
                cpu_usage = 0

            execution_time = end_time - start_time

            performance_data = {
                'operation': operation_name,
                'execution_time_seconds': execution_time,
                'memory_delta_mb': memory_usage,
                'cpu_usage_percent': cpu_usage,
                'psutil_available': PSUTIL_AVAILABLE
            }

            logger.info(f"Performance profile for {operation_name}",
                       performance_data=performance_data)

    @staticmethod
    def profile_function(logger: StructuredLogger):
        """Decorator for profiling functions."""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                operation_name = f"{func.__module__}.{func.__qualname__}"
                with PerformanceProfiler.profile_operation(operation_name, logger):
                    return func(*args, **kwargs)
            return wrapper
        return decorator


class LogRotator:
    """Log rotation and cleanup management."""

    @staticmethod
    def rotate_logs(max_age_days: int = 30, max_size_mb: int = 100):
        """Rotate and clean up old log files."""
        logs_dir = Config.LOGS_DIR
        if not logs_dir.exists():
            return

        current_time = datetime.now()
        total_size = 0
        files_to_remove = []

        # Find log files
        for log_file in logs_dir.glob("*.log"):
            # Check age
            file_age = current_time - datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_age > timedelta(days=max_age_days):
                files_to_remove.append(log_file)
                continue

            # Check total size
            file_size = log_file.stat().st_size / 1024 / 1024  # MB
            total_size += file_size

        # Remove old files
        for old_file in files_to_remove:
            try:
                old_file.unlink()
                StructuredLogger("log_rotator").info(f"Removed old log file: {old_file.name}")
            except Exception as e:
                StructuredLogger("log_rotator").error(f"Failed to remove log file {old_file.name}: {e}")

        # If total size exceeds limit, remove oldest files
        if total_size > max_size_mb:
            log_files = sorted(logs_dir.glob("*.log"),
                             key=lambda f: f.stat().st_mtime)

            for log_file in log_files:
                if total_size <= max_size_mb:
                    break
                try:
                    file_size = log_file.stat().st_size / 1024 / 1024
                    log_file.unlink()
                    total_size -= file_size
                    StructuredLogger("log_rotator").info(f"Removed log file due to size limit: {log_file.name}")
                except Exception as e:
                    StructuredLogger("log_rotator").error(f"Failed to remove log file {log_file.name}: {e}")


class LogAnalyzer:
    """Log analysis tools for debugging and optimization."""

    def __init__(self, logs_dir: Path = None):
        """Initialize log analyzer."""
        self.logs_dir = logs_dir or Config.LOGS_DIR

    def analyze_recent_logs(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze recent logs for insights."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        analysis = {
            'total_entries': 0,
            'error_count': 0,
            'warning_count': 0,
            'performance_insights': [],
            'error_categories': {},
            'pipeline_stages': {},
            'slow_operations': []
        }

        for log_file in self.logs_dir.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            entry_time = datetime.fromisoformat(entry['timestamp'])

                            if entry_time < cutoff_time:
                                continue

                            analysis['total_entries'] += 1

                            # Count by level
                            level = entry['level']
                            if level == 'ERROR':
                                analysis['error_count'] += 1
                            elif level == 'WARNING':
                                analysis['warning_count'] += 1

                            # Error categories
                            if entry.get('error_category'):
                                category = entry['error_category']
                                analysis['error_categories'][category] = analysis['error_categories'].get(category, 0) + 1

                            # Pipeline stages
                            if entry.get('pipeline_stage'):
                                stage = entry['pipeline_stage']
                                analysis['pipeline_stages'][stage] = analysis['pipeline_stages'].get(stage, 0) + 1

                            # Performance insights
                            if entry.get('performance_data'):
                                perf_data = entry['performance_data']
                                if perf_data.get('execution_time_seconds', 0) > 10:  # Slow operations
                                    analysis['slow_operations'].append({
                                        'operation': perf_data.get('operation', 'unknown'),
                                        'time': perf_data['execution_time_seconds'],
                                        'timestamp': entry['timestamp']
                                    })

                        except json.JSONDecodeError:
                            continue  # Skip malformed lines

            except Exception as e:
                StructuredLogger("log_analyzer").error(f"Failed to analyze log file {log_file.name}: {e}")

        return analysis

    def get_error_patterns(self, days: int = 7) -> Dict[str, Any]:
        """Identify error patterns and trends."""
        analysis = self.analyze_recent_logs(hours=days*24)

        patterns = {
            'most_common_errors': sorted(analysis['error_categories'].items(),
                                       key=lambda x: x[1], reverse=True)[:5],
            'error_rate': analysis['error_count'] / max(analysis['total_entries'], 1),
            'stage_failure_rates': {}
        }

        # Calculate stage-specific failure rates
        for stage, count in analysis['pipeline_stages'].items():
            # This is a simplified calculation - in practice you'd need more sophisticated analysis
            patterns['stage_failure_rates'][stage] = analysis['error_count'] / max(count, 1)

        return patterns


# Global logger instances
_loggers = {}
_logger_lock = threading.Lock()


def get_structured_logger(name: str, run_id: Optional[str] = None) -> StructuredLogger:
    """Get or create a structured logger instance."""
    key = f"{name}:{run_id}"
    with _logger_lock:
        if key not in _loggers:
            _loggers[key] = StructuredLogger(name, run_id)
        return _loggers[key]


def setup_structured_logging(run_id: Optional[str] = None) -> StructuredLogger:
    """Set up structured logging for the application."""
    # Ensure logs directory exists
    Config.LOGS_DIR.mkdir(exist_ok=True)

    # Create main logger
    logger = get_structured_logger("geodaily", run_id)

    # Schedule log rotation (this would typically be done by a scheduler)
    LogRotator.rotate_logs()

    return logger