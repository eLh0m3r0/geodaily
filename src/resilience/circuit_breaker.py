"""
Circuit Breaker pattern implementation for resilient API calls.
"""

import time
import threading
from enum import Enum
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass
from contextlib import contextmanager

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Circuit breaker statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


class CircuitBreaker:
    """
    Circuit Breaker implementation with configurable thresholds and recovery.
    """

    def __init__(self,
                 name: str,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Exception = Exception,
                 success_threshold: int = 3,
                 logger=None):
        """
        Initialize circuit breaker.

        Args:
            name: Unique identifier for this circuit
            failure_threshold: Number of consecutive failures to open circuit
            recovery_timeout: Time in seconds before attempting recovery
            expected_exception: Exception type to count as failure
            success_threshold: Number of successes needed in half-open state
            logger: Structured logger instance
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self.half_open_successes = 0

        self._lock = threading.RLock()
        self.logger = logger or get_structured_logger(f"circuit_breaker_{name}")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpen: If circuit is open
            Original exception: If function fails
        """
        with self._lock:
            if self.state == CircuitState.OPEN:
                if not self._should_attempt_reset():
                    raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")

                self._transition_to_half_open()

            if self.state == CircuitState.HALF_OPEN:
                try:
                    result = func(*args, **kwargs)
                    self._record_success()
                    return result
                except self.expected_exception as e:
                    self._record_failure()
                    raise e

            # CLOSED state
            try:
                result = func(*args, **kwargs)
                self._record_success()
                return result
            except self.expected_exception as e:
                self._record_failure()
                raise e

    @contextmanager
    def protect(self):
        """
        Context manager for protecting code blocks.
        """
        with self._lock:
            if self.state == CircuitState.OPEN:
                if not self._should_attempt_reset():
                    raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")
                self._transition_to_half_open()

            try:
                yield
                self._record_success()
            except self.expected_exception as e:
                self._record_failure()
                raise e

    def _record_success(self):
        """Record successful operation."""
        self.stats.total_requests += 1
        self.stats.successful_requests += 1
        self.stats.consecutive_failures = 0
        self.stats.last_success_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.success_threshold:
                self._transition_to_closed()

        self.logger.debug(f"Circuit {self.name} success recorded",
                         structured_data={
                             'state': self.state.value,
                             'success_rate': self.get_success_rate(),
                             'consecutive_failures': self.stats.consecutive_failures
                         })

    def _record_failure(self):
        """Record failed operation."""
        self.stats.total_requests += 1
        self.stats.failed_requests += 1
        self.stats.consecutive_failures += 1
        self.stats.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self.stats.consecutive_failures >= self.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()

        self.logger.warning(f"Circuit {self.name} failure recorded",
                           error_category=ErrorCategory.API_ERROR,
                           structured_data={
                               'state': self.state.value,
                               'consecutive_failures': self.stats.consecutive_failures,
                               'failure_threshold': self.failure_threshold,
                               'success_rate': self.get_success_rate()
                           })

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.stats.last_failure_time is None:
            return True

        return (time.time() - self.stats.last_failure_time) >= self.recovery_timeout

    def _transition_to_open(self):
        """Transition to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.stats.state_changes += 1
        self.half_open_successes = 0

        self.logger.warning(f"Circuit {self.name} transitioned: {old_state.value} -> {self.state.value}",
                           error_category=ErrorCategory.API_ERROR,
                           structured_data={
                               'consecutive_failures': self.stats.consecutive_failures,
                               'recovery_timeout': self.recovery_timeout
                           })

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.stats.state_changes += 1
        self.half_open_successes = 0

        self.logger.info(f"Circuit {self.name} transitioned: {old_state.value} -> {self.state.value}",
                        structured_data={
                            'recovery_attempt': True,
                            'time_since_last_failure': time.time() - (self.stats.last_failure_time or 0)
                        })

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.stats.state_changes += 1
        self.half_open_successes = 0

        self.logger.info(f"Circuit {self.name} transitioned: {old_state.value} -> {self.state.value}",
                        structured_data={
                            'recovery_successful': True,
                            'half_open_successes': self.half_open_successes
                        })

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.stats.total_requests == 0:
            return 100.0
        return (self.stats.successful_requests / self.stats.total_requests) * 100

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self.state.value,
            'total_requests': self.stats.total_requests,
            'successful_requests': self.stats.successful_requests,
            'failed_requests': self.stats.failed_requests,
            'success_rate': self.get_success_rate(),
            'consecutive_failures': self.stats.consecutive_failures,
            'state_changes': self.stats.state_changes,
            'last_failure_time': self.stats.last_failure_time,
            'last_success_time': self.stats.last_success_time,
            'half_open_successes': self.half_open_successes
        }

    def reset(self):
        """Reset circuit breaker to initial state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self.half_open_successes = 0
            self.logger.info(f"Circuit {self.name} reset to initial state")


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    """

    def __init__(self):
        self.circuits: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
        self.logger = get_structured_logger("circuit_breaker_registry")

    def get_or_create(self,
                     name: str,
                     failure_threshold: int = 5,
                     recovery_timeout: float = 60.0,
                     **kwargs) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures to open circuit
            recovery_timeout: Time before recovery attempt
            **kwargs: Additional CircuitBreaker parameters

        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if name not in self.circuits:
                self.circuits[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    logger=self.logger,
                    **kwargs
                )
                self.logger.info(f"Created circuit breaker: {name}",
                               structured_data={
                                   'failure_threshold': failure_threshold,
                                   'recovery_timeout': recovery_timeout
                               })

            return self.circuits[name]

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        with self._lock:
            return {name: circuit.get_stats() for name, circuit in self.circuits.items()}

    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for name, circuit in self.circuits.items():
                circuit.reset()
            self.logger.info("Reset all circuit breakers")

    def get_unhealthy_circuits(self) -> list:
        """Get list of circuits that are currently open."""
        with self._lock:
            return [name for name, circuit in self.circuits.items()
                   if circuit.state == CircuitState.OPEN]


# Global registry instance
circuit_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create a circuit breaker from global registry.

    Args:
        name: Circuit breaker name
        **kwargs: CircuitBreaker parameters

    Returns:
        CircuitBreaker instance
    """
    return circuit_registry.get_or_create(name, **kwargs)