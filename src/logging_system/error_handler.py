"""
Error handling utilities with automatic categorization and logging integration.
"""

import traceback
import inspect
from typing import Dict, Any, Optional, Callable, Type
from functools import wraps

from .structured_logger import StructuredLogger, ErrorCategory, PipelineStage
from ..config import Config


class ErrorClassifier:
    """Classifies errors into categories based on type and context."""

    # Error type mappings
    ERROR_TYPE_MAPPING = {
        # API and HTTP errors
        'APIError': ErrorCategory.API_ERROR,
        'ApiError': ErrorCategory.API_ERROR,
        'HTTPError': ErrorCategory.API_ERROR,
        'ConnectionError': ErrorCategory.NETWORK_ERROR,
        'Timeout': ErrorCategory.TIMEOUT_ERROR,
        'ConnectTimeout': ErrorCategory.TIMEOUT_ERROR,
        'ReadTimeout': ErrorCategory.TIMEOUT_ERROR,
        'SSLError': ErrorCategory.NETWORK_ERROR,
        'ProxyError': ErrorCategory.NETWORK_ERROR,
        'TooManyRedirects': ErrorCategory.NETWORK_ERROR,
        'RequestException': ErrorCategory.NETWORK_ERROR,
        'ConnectionResetError': ErrorCategory.NETWORK_ERROR,
        'ConnectionAbortedError': ErrorCategory.NETWORK_ERROR,
        'ConnectionRefusedError': ErrorCategory.NETWORK_ERROR,

        # Database errors
        'DatabaseError': ErrorCategory.DATABASE_ERROR,
        'IntegrityError': ErrorCategory.DATABASE_ERROR,
        'OperationalError': ErrorCategory.DATABASE_ERROR,
        'ProgrammingError': ErrorCategory.DATABASE_ERROR,
        'DataError': ErrorCategory.DATABASE_ERROR,
        'InternalError': ErrorCategory.DATABASE_ERROR,
        'NotSupportedError': ErrorCategory.DATABASE_ERROR,
        'InterfaceError': ErrorCategory.DATABASE_ERROR,

        # Parsing and validation errors
        'JSONDecodeError': ErrorCategory.PARSING_ERROR,
        'ValueError': ErrorCategory.VALIDATION_ERROR,
        'TypeError': ErrorCategory.VALIDATION_ERROR,
        'KeyError': ErrorCategory.VALIDATION_ERROR,
        'AttributeError': ErrorCategory.VALIDATION_ERROR,
        'IndexError': ErrorCategory.VALIDATION_ERROR,
        'UnicodeDecodeError': ErrorCategory.PARSING_ERROR,
        'UnicodeEncodeError': ErrorCategory.PARSING_ERROR,

        # Authentication errors
        'AuthenticationError': ErrorCategory.AUTHENTICATION_ERROR,
        'AuthorizationError': ErrorCategory.AUTHENTICATION_ERROR,
        'PermissionError': ErrorCategory.AUTHENTICATION_ERROR,
        'TokenError': ErrorCategory.AUTHENTICATION_ERROR,
        'CredentialsError': ErrorCategory.AUTHENTICATION_ERROR,

        # Configuration errors
        'ConfigError': ErrorCategory.CONFIGURATION_ERROR,
        'ConfigurationError': ErrorCategory.CONFIGURATION_ERROR,
        'FileNotFoundError': ErrorCategory.CONFIGURATION_ERROR,
        'IsADirectoryError': ErrorCategory.CONFIGURATION_ERROR,
        'NotADirectoryError': ErrorCategory.CONFIGURATION_ERROR,
        'PermissionError': ErrorCategory.CONFIGURATION_ERROR,

        # Rate limiting
        'RateLimitError': ErrorCategory.RATE_LIMIT_ERROR,
        'TooManyRequests': ErrorCategory.RATE_LIMIT_ERROR,
        'RateLimitExceeded': ErrorCategory.RATE_LIMIT_ERROR,

        # File system errors
        'OSError': ErrorCategory.CONFIGURATION_ERROR,
        'IOError': ErrorCategory.CONFIGURATION_ERROR,
        'FileExistsError': ErrorCategory.CONFIGURATION_ERROR,
        'FileNotFoundError': ErrorCategory.CONFIGURATION_ERROR,

        # Memory and resource errors
        'MemoryError': ErrorCategory.UNKNOWN_ERROR,
        'RecursionError': ErrorCategory.UNKNOWN_ERROR,
        'SystemExit': ErrorCategory.UNKNOWN_ERROR,
        'KeyboardInterrupt': ErrorCategory.UNKNOWN_ERROR,
    }

    @classmethod
    def classify_error(cls, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorCategory:
        """Classify an error based on its type and context."""
        error_type = type(error).__name__

        # Direct mapping
        if error_type in cls.ERROR_TYPE_MAPPING:
            return cls.ERROR_TYPE_MAPPING[error_type]

        # Check error message for clues
        error_message = str(error).lower()

        # Network-related keywords
        if any(keyword in error_message for keyword in ['connection', 'network', 'timeout', 'dns', 'socket']):
            return ErrorCategory.NETWORK_ERROR

        # API-related keywords
        if any(keyword in error_message for keyword in ['api', 'http', 'request', 'response', 'status']):
            return ErrorCategory.API_ERROR

        # Authentication-related keywords
        if any(keyword in error_message for keyword in ['auth', 'login', 'token', 'credential']):
            return ErrorCategory.AUTHENTICATION_ERROR

        # Rate limiting keywords
        if any(keyword in error_message for keyword in ['rate', 'limit', 'throttle', 'quota']):
            return ErrorCategory.RATE_LIMIT_ERROR

        # Parsing-related keywords
        if any(keyword in error_message for keyword in ['parse', 'decode', 'format', 'json', 'xml']):
            return ErrorCategory.PARSING_ERROR

        # Database-related keywords
        if any(keyword in error_message for keyword in ['database', 'sql', 'query', 'table', 'column']):
            return ErrorCategory.DATABASE_ERROR

        # Configuration-related keywords
        if any(keyword in error_message for keyword in ['config', 'setting', 'parameter', 'environment']):
            return ErrorCategory.CONFIGURATION_ERROR

        # Default to unknown
        return ErrorCategory.UNKNOWN_ERROR

    @classmethod
    def get_error_context(cls, error: Exception, function_name: Optional[str] = None,
                          module_name: Optional[str] = None) -> Dict[str, Any]:
        """Extract contextual information from an error."""
        context = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'function_name': function_name,
            'module_name': module_name,
            'traceback': traceback.format_exc()
        }

        # Add additional context based on error type
        if hasattr(error, '__dict__'):
            # Add any additional attributes from the exception
            for key, value in error.__dict__.items():
                if key not in ['args', '__cause__', '__context__', '__suppress_context__']:
                    context[f'error_{key}'] = str(value)

        return context

    @classmethod
    def get_handling_strategy(cls, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Determine the appropriate handling strategy for an error.

        Args:
            error: The exception that occurred
            context: Additional context about the error

        Returns:
            Dictionary containing handling strategy recommendations
        """
        error_category = cls.classify_error(error, context)
        error_type = type(error).__name__
        error_message = str(error).lower()

        strategy = {
            'category': error_category.value,
            'should_retry': False,
            'retry_strategy': 'exponential_backoff',
            'max_retries': 3,
            'base_delay': 1.0,
            'should_degrade': False,
            'degradation_level': 'minor',
            'should_recover': False,
            'recovery_strategy': 'immediate',
            'circuit_breaker': False,
            'log_level': 'error'
        }

        # Determine strategies based on error category and type
        if error_category == ErrorCategory.NETWORK_ERROR:
            strategy.update({
                'should_retry': True,
                'max_retries': 5,
                'base_delay': 0.5,
                'circuit_breaker': True,
                'should_degrade': True,
                'degradation_level': 'moderate' if 'timeout' in error_message else 'minor'
            })

        elif error_category == ErrorCategory.API_ERROR:
            if 'rate' in error_message or '429' in error_message:
                strategy.update({
                    'should_retry': True,
                    'retry_strategy': 'exponential_backoff',
                    'max_retries': 3,
                    'base_delay': 2.0,
                    'circuit_breaker': True,
                    'should_degrade': True,
                    'degradation_level': 'moderate'
                })
            else:
                strategy.update({
                    'should_retry': True,
                    'max_retries': 3,
                    'circuit_breaker': True,
                    'should_degrade': True,
                    'degradation_level': 'minor'
                })

        elif error_category == ErrorCategory.TIMEOUT_ERROR:
            strategy.update({
                'should_retry': True,
                'max_retries': 2,
                'base_delay': 1.0,
                'circuit_breaker': True,
                'should_degrade': True,
                'degradation_level': 'moderate'
            })

        elif error_category == ErrorCategory.DATABASE_ERROR:
            if any(keyword in error_message for keyword in ['connection', 'timeout', 'pool']):
                strategy.update({
                    'should_retry': True,
                    'max_retries': 3,
                    'base_delay': 0.1,
                    'circuit_breaker': True,
                    'should_recover': True,
                    'recovery_strategy': 'exponential_backoff',
                    'should_degrade': True,
                    'degradation_level': 'severe'
                })
            else:
                strategy.update({
                    'should_retry': False,
                    'should_degrade': True,
                    'degradation_level': 'moderate'
                })

        elif error_category == ErrorCategory.AUTHENTICATION_ERROR:
            strategy.update({
                'should_retry': False,
                'should_recover': True,
                'recovery_strategy': 'service_restart',
                'should_degrade': True,
                'degradation_level': 'severe'
            })

        elif error_category == ErrorCategory.CONFIGURATION_ERROR:
            strategy.update({
                'should_retry': False,
                'should_recover': False,
                'log_level': 'critical'
            })

        elif error_category == ErrorCategory.PARSING_ERROR:
            strategy.update({
                'should_retry': False,
                'should_degrade': True,
                'degradation_level': 'minor'
            })

        elif error_category == ErrorCategory.VALIDATION_ERROR:
            strategy.update({
                'should_retry': False,
                'should_degrade': True,
                'degradation_level': 'minor'
            })

        elif error_category == ErrorCategory.RATE_LIMIT_ERROR:
            strategy.update({
                'should_retry': True,
                'retry_strategy': 'exponential_backoff',
                'max_retries': 5,
                'base_delay': 5.0,
                'circuit_breaker': True,
                'should_degrade': True,
                'degradation_level': 'moderate'
            })

        # Adjust strategy based on specific error types
        if error_type in ['MemoryError', 'RecursionError']:
            strategy.update({
                'should_retry': False,
                'should_recover': True,
                'recovery_strategy': 'service_restart',
                'should_degrade': True,
                'degradation_level': 'critical',
                'log_level': 'critical'
            })

        elif error_type in ['SystemExit', 'KeyboardInterrupt']:
            strategy.update({
                'should_retry': False,
                'should_recover': False,
                'log_level': 'info'
            })

        return strategy


class ErrorHandler:
    """Handles errors with automatic categorization and logging."""

    def __init__(self, logger: StructuredLogger):
        """Initialize error handler."""
        self.logger = logger
        self.error_counts = {}
        self.classifier = ErrorClassifier()

    def handle_error(self, error: Exception, pipeline_stage: Optional[PipelineStage] = None,
                    context: Optional[Dict[str, Any]] = None,
                    re_raise: bool = True) -> None:
        """Handle an error with categorization and logging."""
        # Classify the error
        error_category = self.classifier.classify_error(error, context)

        # Get error context
        frame = inspect.currentframe()
        caller_frame = frame.f_back if frame else None

        function_name = caller_frame.f_code.co_name if caller_frame else None
        module_name = caller_frame.f_globals.get('__name__', None) if caller_frame else None

        error_context = self.classifier.get_error_context(error, function_name, module_name)

        # Update error counts
        self.error_counts[error_category.value] = self.error_counts.get(error_category.value, 0) + 1

        # Add additional context
        if context:
            error_context.update(context)

        error_context['error_count'] = self.error_counts[error_category.value]

        # Log the error
        self.logger.error(f"Error in {module_name}.{function_name}: {error}",
                         pipeline_stage=pipeline_stage,
                         error_category=error_category,
                         structured_data=error_context)

        # Re-raise if requested
        if re_raise:
            raise error

    def handle_and_recover(self, error: Exception, recovery_action: Optional[Callable] = None,
                          pipeline_stage: Optional[PipelineStage] = None,
                          context: Optional[Dict[str, Any]] = None) -> Any:
        """Handle an error and attempt recovery."""
        try:
            self.handle_error(error, pipeline_stage, context, re_raise=False)

            # Attempt recovery
            if recovery_action:
                self.logger.info("Attempting error recovery",
                               pipeline_stage=pipeline_stage,
                               structured_data={'recovery_attempted': True})
                return recovery_action()
            else:
                self.logger.warning("No recovery action specified, returning None",
                                  pipeline_stage=pipeline_stage)
                return None

        except Exception as recovery_error:
            self.logger.critical("Recovery action failed",
                               pipeline_stage=pipeline_stage,
                               error_category=ErrorCategory.UNKNOWN_ERROR,
                               structured_data={
                                   'original_error': str(error),
                                   'recovery_error': str(recovery_error)
                               })
            raise recovery_error


def error_handler(logger: StructuredLogger, pipeline_stage: Optional[PipelineStage] = None,
                 re_raise: bool = True):
    """Decorator for automatic error handling and logging."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler(logger)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler.handle_error(e, pipeline_stage, re_raise=re_raise)
        return wrapper
    return decorator


def retry_on_error(logger: StructuredLogger, max_retries: int = 3,
                   retry_delay: float = 1.0, backoff_factor: float = 2.0,
                   pipeline_stage: Optional[PipelineStage] = None,
                   retryable_errors: Optional[list] = None):
    """Decorator for retrying operations on errors."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler(logger)
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Check if error is retryable
                    if retryable_errors:
                        error_type = type(e).__name__
                        if error_type not in retryable_errors:
                            handler.handle_error(e, pipeline_stage)
                            break

                    if attempt < max_retries:
                        delay = retry_delay * (backoff_factor ** attempt)

                        logger.warning(f"Operation failed, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries + 1})",
                                     pipeline_stage=pipeline_stage,
                                     structured_data={
                                         'attempt': attempt + 1,
                                         'max_retries': max_retries,
                                         'delay_seconds': delay,
                                         'error_type': type(e).__name__
                                     })

                        import time
                        time.sleep(delay)
                    else:
                        # Final attempt failed
                        handler.handle_error(e, pipeline_stage)

            # If we get here, all retries failed
            raise last_error

        return wrapper
    return decorator


class ErrorAggregator:
    """Aggregates and analyzes error patterns."""

    def __init__(self, logger: StructuredLogger):
        """Initialize error aggregator."""
        self.logger = logger
        self.error_patterns = {}
        self.error_timeline = []

    def record_error(self, error: Exception, pipeline_stage: Optional[PipelineStage] = None,
                    context: Optional[Dict[str, Any]] = None):
        """Record an error for pattern analysis."""
        from datetime import datetime

        error_category = ErrorClassifier.classify_error(error, context)
        error_type = type(error).__name__

        # Record pattern
        key = f"{error_category.value}:{error_type}"
        if key not in self.error_patterns:
            self.error_patterns[key] = {
                'count': 0,
                'first_seen': datetime.now(),
                'last_seen': datetime.now(),
                'stages': set(),
                'messages': set()
            }

        pattern = self.error_patterns[key]
        pattern['count'] += 1
        pattern['last_seen'] = datetime.now()
        pattern['stages'].add(pipeline_stage.value if pipeline_stage else 'unknown')
        pattern['messages'].add(str(error))

        # Record timeline
        self.error_timeline.append({
            'timestamp': datetime.now(),
            'error_type': error_type,
            'category': error_category.value,
            'stage': pipeline_stage.value if pipeline_stage else 'unknown',
            'message': str(error),
            'context': context or {}
        })

        # Log pattern analysis
        if pattern['count'] > 1:
            time_since_first = (pattern['last_seen'] - pattern['first_seen']).total_seconds()
            frequency = pattern['count'] / max(time_since_first / 3600, 1)  # errors per hour

            self.logger.warning("Recurring error pattern detected",
                              pipeline_stage=pipeline_stage,
                              error_category=error_category,
                              structured_data={
                                  'pattern_key': key,
                                  'error_count': pattern['count'],
                                  'frequency_per_hour': frequency,
                                  'affected_stages': list(pattern['stages']),
                                  'time_span_hours': time_since_first / 3600
                              })

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error patterns."""
        from datetime import datetime, timedelta

        # Get recent errors (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        recent_errors = [e for e in self.error_timeline if e['timestamp'] > cutoff]

        summary = {
            'total_patterns': len(self.error_patterns),
            'total_errors': sum(p['count'] for p in self.error_patterns.values()),
            'recent_errors': len(recent_errors),
            'most_common_patterns': [],
            'stage_error_distribution': {},
            'error_trends': {}
        }

        # Most common patterns
        sorted_patterns = sorted(self.error_patterns.items(),
                               key=lambda x: x[1]['count'], reverse=True)[:5]
        summary['most_common_patterns'] = [
            {
                'pattern': key,
                'count': pattern['count'],
                'stages': list(pattern['stages'])
            }
            for key, pattern in sorted_patterns
        ]

        # Stage distribution
        for pattern_key, pattern in self.error_patterns.items():
            for stage in pattern['stages']:
                summary['stage_error_distribution'][stage] = \
                    summary['stage_error_distribution'].get(stage, 0) + pattern['count']

        return summary

    def detect_error_spikes(self, time_window_minutes: int = 60) -> list:
        """Detect error spikes within a time window."""
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_errors = [e for e in self.error_timeline if e['timestamp'] > cutoff]

        if len(recent_errors) < 5:  # Need minimum errors to detect spike
            return []

        # Group by time intervals (5-minute buckets)
        bucket_size = timedelta(minutes=5)
        buckets = {}

        for error in recent_errors:
            bucket_time = error['timestamp'].replace(second=0, microsecond=0)
            minutes = bucket_time.minute // 5 * 5
            bucket_time = bucket_time.replace(minute=minutes)

            bucket_key = bucket_time.isoformat()
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(error)

        # Find spikes (buckets with significantly more errors than average)
        bucket_counts = [len(errors) for errors in buckets.values()]
        if not bucket_counts:
            return []

        avg_errors = sum(bucket_counts) / len(bucket_counts)
        spike_threshold = avg_errors * 2  # 2x average

        spikes = []
        for bucket_time, errors in buckets.items():
            if len(errors) >= spike_threshold:
                spikes.append({
                    'timestamp': bucket_time,
                    'error_count': len(errors),
                    'threshold': spike_threshold,
                    'errors': errors[:3]  # First 3 errors as examples
                })

        return spikes