"""
Enhanced retry mechanisms with exponential backoff, jitter, and circuit breaker integration.
"""

import time
import random
import threading
from typing import Any, Callable, Optional, List, Type, Dict, Union
from functools import wraps
from dataclasses import dataclass
from enum import Enum

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpen


class RetryStrategy(Enum):
    """Retry strategies."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter_range: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    retryable_exceptions: Optional[List[Type[Exception]]] = None
    circuit_breaker_name: Optional[str] = None
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 60.0


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""
    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for retry attempt based on strategy.

    Args:
        attempt: Current attempt number (0-based)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    if config.strategy == RetryStrategy.FIXED:
        delay = config.base_delay
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay * (attempt + 1)
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay * (config.backoff_factor ** attempt)
    elif config.strategy == RetryStrategy.EXPONENTIAL_JITTER:
        delay = config.base_delay * (config.backoff_factor ** attempt)
        # Add jitter to prevent thundering herd
        jitter = random.uniform(-config.jitter_range, config.jitter_range) * delay
        delay += jitter
    else:
        delay = config.base_delay

    # Cap at maximum delay
    return min(delay, config.max_delay)


def is_retryable_exception(exception: Exception, retryable_exceptions: Optional[List[Type[Exception]]]) -> bool:
    """
    Check if exception is retryable.

    Args:
        exception: Exception to check
        retryable_exceptions: List of retryable exception types

    Returns:
        True if exception should be retried
    """
    if retryable_exceptions is None:
        return True

    exception_type = type(exception)
    return any(issubclass(exception_type, retryable_type) for retryable_type in retryable_exceptions)


def retry_with_config(config: RetryConfig, logger=None):
    """
    Decorator factory for retrying operations with custom configuration.

    Args:
        config: Retry configuration
        logger: Structured logger instance

    Returns:
        Decorator function
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_structured_logger(f"retry_{func.__name__}")

            circuit_breaker = None
            if config.circuit_breaker_name:
                circuit_breaker = get_circuit_breaker(
                    config.circuit_breaker_name,
                    failure_threshold=config.circuit_failure_threshold,
                    recovery_timeout=config.circuit_recovery_timeout
                )

            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    # Check circuit breaker if configured
                    if circuit_breaker:
                        return circuit_breaker.call(func, *args, **kwargs)

                    # Execute function
                    return func(*args, **kwargs)

                except CircuitBreakerOpen as e:
                    logger.warning(f"Circuit breaker open for {func.__name__}",
                                 structured_data={'attempt': attempt + 1})
                    raise e

                except Exception as e:
                    last_exception = e

                    # Check if exception is retryable
                    if not is_retryable_exception(e, config.retryable_exceptions):
                        logger.debug(f"Non-retryable exception in {func.__name__}: {type(e).__name__}")
                        raise e

                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        break

                    # Calculate delay
                    delay = calculate_delay(attempt, config)

                    logger.warning(f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}",
                                 error_category=ErrorCategory.API_ERROR,
                                 structured_data={
                                     'attempt': attempt + 1,
                                     'max_attempts': config.max_attempts,
                                     'delay_seconds': delay,
                                     'exception_type': type(e).__name__,
                                     'strategy': config.strategy.value
                                 })

                    # Wait before retry
                    time.sleep(delay)

            # All attempts exhausted
            error_msg = f"All {config.max_attempts} attempts failed for {func.__name__}"
            logger.error(error_msg,
                        error_category=ErrorCategory.API_ERROR,
                        structured_data={
                            'total_attempts': config.max_attempts,
                            'last_exception_type': type(last_exception).__name__,
                            'strategy': config.strategy.value
                        })

            raise RetryError(error_msg, last_exception, config.max_attempts)

        return wrapper
    return decorator


# Pre-configured retry decorators for common use cases
def retry_api_call(max_attempts: int = 3, base_delay: float = 1.0, circuit_breaker_name: str = None):
    """
    Decorator for retrying API calls with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries
        circuit_breaker_name: Optional circuit breaker name
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        strategy=RetryStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions=[
            ConnectionError, TimeoutError, OSError,
            Exception  # Broad catch for API errors
        ],
        circuit_breaker_name=circuit_breaker_name
    )
    return retry_with_config(config)


def retry_network_operation(max_attempts: int = 5, base_delay: float = 0.5):
    """
    Decorator for retrying network operations.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_JITTER,
        retryable_exceptions=[
            ConnectionError, TimeoutError, OSError,
            ConnectionResetError, ConnectionAbortedError
        ]
    )
    return retry_with_config(config)


def retry_database_operation(max_attempts: int = 3, base_delay: float = 0.1):
    """
    Decorator for retrying database operations.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=5.0,
        strategy=RetryStrategy.EXPONENTIAL,
        retryable_exceptions=[
            ConnectionError, TimeoutError, OSError,
            Exception  # Broad catch for DB errors
        ]
    )
    return retry_with_config(config)


class RetryManager:
    """
    Manager for handling retries with different strategies and monitoring.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("retry_manager")
        self.retry_stats = {}
        self._lock = threading.RLock()

    def execute_with_retry(self,
                          func: Callable,
                          config: RetryConfig,
                          *args, **kwargs) -> Any:
        """
        Execute function with retry configuration.

        Args:
            func: Function to execute
            config: Retry configuration
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            RetryError: If all attempts fail
        """
        circuit_breaker = None
        if config.circuit_breaker_name:
            circuit_breaker = get_circuit_breaker(
                config.circuit_breaker_name,
                failure_threshold=config.circuit_failure_threshold,
                recovery_timeout=config.circuit_recovery_timeout
            )

        last_exception = None
        start_time = time.time()

        for attempt in range(config.max_attempts):
            try:
                # Check circuit breaker if configured
                if circuit_breaker:
                    result = circuit_breaker.call(func, *args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Record success
                self._record_attempt(func.__name__, attempt + 1, True, time.time() - start_time)
                return result

            except CircuitBreakerOpen as e:
                self.logger.warning(f"Circuit breaker open for {func.__name__}")
                raise e

            except Exception as e:
                last_exception = e

                # Check if exception is retryable
                if not is_retryable_exception(e, config.retryable_exceptions):
                    self._record_attempt(func.__name__, attempt + 1, False, time.time() - start_time)
                    raise e

                # Don't retry on last attempt
                if attempt == config.max_attempts - 1:
                    break

                # Calculate delay
                delay = calculate_delay(attempt, config)

                self.logger.warning(f"Retry attempt {attempt + 1}/{config.max_attempts} for {func.__name__}",
                                  error_category=ErrorCategory.API_ERROR,
                                  structured_data={
                                      'attempt': attempt + 1,
                                      'delay_seconds': delay,
                                      'exception_type': type(e).__name__,
                                      'strategy': config.strategy.value
                                  })

                # Wait before retry
                time.sleep(delay)

        # All attempts exhausted
        total_time = time.time() - start_time
        self._record_attempt(func.__name__, config.max_attempts, False, total_time)

        error_msg = f"All {config.max_attempts} attempts failed for {func.__name__}"
        self.logger.error(error_msg,
                         error_category=ErrorCategory.API_ERROR,
                         structured_data={
                             'total_attempts': config.max_attempts,
                             'total_time_seconds': total_time,
                             'last_exception_type': type(last_exception).__name__
                         })

        raise RetryError(error_msg, last_exception, config.max_attempts)

    def _record_attempt(self, func_name: str, attempt: int, success: bool, duration: float):
        """Record retry attempt statistics."""
        with self._lock:
            if func_name not in self.retry_stats:
                self.retry_stats[func_name] = {
                    'total_attempts': 0,
                    'successful_attempts': 0,
                    'failed_attempts': 0,
                    'total_duration': 0.0,
                    'max_attempts_used': 0
                }

            stats = self.retry_stats[func_name]
            stats['total_attempts'] += 1
            stats['total_duration'] += duration
            stats['max_attempts_used'] = max(stats['max_attempts_used'], attempt)

            if success:
                stats['successful_attempts'] += 1
            else:
                stats['failed_attempts'] += 1

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get retry statistics for all functions."""
        with self._lock:
            return self.retry_stats.copy()

    def reset_stats(self):
        """Reset retry statistics."""
        with self._lock:
            self.retry_stats.clear()
            self.logger.info("Retry statistics reset")


# Global retry manager instance
retry_manager = RetryManager()