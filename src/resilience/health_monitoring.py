"""
Health monitoring and proactive error detection system.
"""

import time
import threading
import psutil
from typing import Any, Dict, List, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Definition of a health check."""
    name: str
    component: str
    check_function: Callable
    interval_seconds: float = 60.0
    timeout_seconds: float = 10.0
    failure_threshold: int = 3
    recovery_threshold: int = 2
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class HealthCheckResult:
    """Result of a health check execution."""
    check_name: str
    component: str
    status: HealthStatus
    response_time: float
    timestamp: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    consecutive_failures: int = 0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None


class HealthMonitor:
    """
    Monitors system health and performs proactive error detection.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("health_monitor")
        self.health_checks = {}
        self.check_results = {}
        self.monitoring_threads = {}
        self.stop_monitoring = threading.Event()
        self._lock = threading.RLock()

    def register_health_check(self, check: HealthCheck):
        """
        Register a health check for monitoring.

        Args:
            check: Health check definition
        """
        with self._lock:
            self.health_checks[check.name] = check
            self.check_results[check.name] = HealthCheckResult(
                check_name=check.name,
                component=check.component,
                status=HealthStatus.UNKNOWN,
                response_time=0.0,
                timestamp=time.time()
            )

            self.logger.info("Health check registered",
                           structured_data={
                               'check_name': check.name,
                               'component': check.component,
                               'interval_seconds': check.interval_seconds
                           })

    def start_monitoring(self):
        """Start health monitoring for all registered checks."""
        with self._lock:
            for check_name, check in self.health_checks.items():
                if check.enabled and check_name not in self.monitoring_threads:
                    thread = threading.Thread(
                        target=self._monitor_check,
                        args=(check,),
                        daemon=True,
                        name=f"health_monitor_{check_name}"
                    )
                    self.monitoring_threads[check_name] = thread
                    thread.start()

            self.logger.info("Health monitoring started",
                           structured_data={
                               'active_checks': len(self.monitoring_threads)
                           })

    def stop_monitoring(self):
        """Stop all health monitoring."""
        self.stop_monitoring.set()

        with self._lock:
            for thread in self.monitoring_threads.values():
                thread.join(timeout=5.0)

            self.monitoring_threads.clear()

        self.logger.info("Health monitoring stopped")

    def _monitor_check(self, check: HealthCheck):
        """Monitor a specific health check."""
        while not self.stop_monitoring.is_set():
            try:
                self._execute_health_check(check)
            except Exception as e:
                self.logger.error("Health check monitoring error",
                                error_category=ErrorCategory.UNKNOWN_ERROR,
                                structured_data={
                                    'check_name': check.name,
                                    'error': str(e)
                                })

            # Wait for next check interval
            self.stop_monitoring.wait(check.interval_seconds)

    def _execute_health_check(self, check: HealthCheck) -> HealthCheckResult:
        """Execute a health check and update results."""
        start_time = time.time()

        try:
            # Execute check with timeout
            result = self._execute_with_timeout(check.check_function, check.timeout_seconds)
            response_time = time.time() - start_time

            # Determine status based on result
            if isinstance(result, dict):
                status = result.get('status', HealthStatus.HEALTHY)
                details = result
                error_message = result.get('error_message')
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.CRITICAL
                details = {'result': result}
                error_message = None
            else:
                status = HealthStatus.HEALTHY
                details = {'result': result}
                error_message = None

        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.CRITICAL
            error_message = str(e)
            details = {'error': str(e)}

        # Update check result
        with self._lock:
            current_result = self.check_results[check.name]

            # Update consecutive failures
            if status == HealthStatus.CRITICAL:
                current_result.consecutive_failures += 1
                current_result.last_failure_time = time.time()
            else:
                if current_result.consecutive_failures > 0:
                    current_result.consecutive_failures = 0
                current_result.last_success_time = time.time()

            # Update result
            current_result.status = status
            current_result.response_time = response_time
            current_result.timestamp = time.time()
            current_result.error_message = error_message
            current_result.details = details

            # Log significant status changes
            self._log_status_change(check, current_result)

            return current_result

    def _execute_with_timeout(self, func: Callable, timeout: float) -> Any:
        """Execute function with timeout."""
        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = func()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            raise TimeoutError(f"Health check timed out after {timeout} seconds")

        if exception[0]:
            raise exception[0]

        return result[0]

    def _log_status_change(self, check: HealthCheck, result: HealthCheckResult):
        """Log significant status changes."""
        # Only log critical status or recovery from critical
        if result.status == HealthStatus.CRITICAL:
            self.logger.error("Health check failed",
                            error_category=ErrorCategory.UNKNOWN_ERROR,
                            structured_data={
                                'check_name': check.name,
                                'component': check.component,
                                'consecutive_failures': result.consecutive_failures,
                                'response_time': result.response_time,
                                'error_message': result.error_message
                            })
        elif (result.status == HealthStatus.HEALTHY and
              result.consecutive_failures == 0 and
              result.last_failure_time is not None):
            # Recovery from failure
            downtime = time.time() - result.last_failure_time
            self.logger.info("Health check recovered",
                           structured_data={
                               'check_name': check.name,
                               'component': check.component,
                               'downtime_seconds': downtime,
                               'response_time': result.response_time
                           })

    def get_health_status(self, component: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current health status.

        Args:
            component: Optional component name to filter by

        Returns:
            Health status summary
        """
        with self._lock:
            results = {}
            status_counts = {}

            for check_name, result in self.check_results.items():
                check = self.health_checks[check_name]

                if component and check.component != component:
                    continue

                results[check_name] = {
                    'component': check.component,
                    'status': result.status.value,
                    'response_time': result.response_time,
                    'timestamp': result.timestamp,
                    'consecutive_failures': result.consecutive_failures,
                    'error_message': result.error_message,
                    'details': result.details
                }

                status_counts[result.status.value] = status_counts.get(result.status.value, 0) + 1

            # Determine overall status
            if status_counts.get(HealthStatus.CRITICAL.value, 0) > 0:
                overall_status = HealthStatus.CRITICAL
            elif status_counts.get(HealthStatus.WARNING.value, 0) > 0:
                overall_status = HealthStatus.WARNING
            elif status_counts.get(HealthStatus.HEALTHY.value, 0) > 0:
                overall_status = HealthStatus.HEALTHY
            else:
                overall_status = HealthStatus.UNKNOWN

            return {
                'overall_status': overall_status.value,
                'total_checks': len(results),
                'status_counts': status_counts,
                'checks': results,
                'timestamp': time.time()
            }

    def get_failed_checks(self) -> List[Dict[str, Any]]:
        """Get list of currently failed health checks."""
        with self._lock:
            failed = []
            for check_name, result in self.check_results.items():
                if result.status == HealthStatus.CRITICAL:
                    check = self.health_checks[check_name]
                    failed.append({
                        'check_name': check_name,
                        'component': check.component,
                        'consecutive_failures': result.consecutive_failures,
                        'error_message': result.error_message,
                        'last_failure_time': result.last_failure_time,
                        'response_time': result.response_time
                    })
            return failed

    def force_health_check(self, check_name: str) -> Optional[HealthCheckResult]:
        """
        Force execution of a specific health check.

        Args:
            check_name: Name of health check to execute

        Returns:
            Health check result or None if check not found
        """
        with self._lock:
            check = self.health_checks.get(check_name)
            if not check:
                return None

            return self._execute_health_check(check)


# Pre-configured health checks for common components
def create_database_health_checks():
    """Create health checks for database operations."""
    def check_database_connection():
        """Check database connection health."""
        try:
            # Import here to avoid circular imports
            from ..metrics.database import MetricsDatabase

            db = MetricsDatabase()
            # Simple query to test connection
            cursor = db.conn.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()

            return {
                'status': HealthStatus.HEALTHY,
                'connection_pool_size': 1,  # Would be more sophisticated in real implementation
                'active_connections': 1
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    def check_database_performance():
        """Check database performance metrics."""
        try:
            # Import here to avoid circular imports
            from ..metrics.database import MetricsDatabase

            db = MetricsDatabase()
            start_time = time.time()

            # Test query performance
            cursor = db.conn.execute("SELECT COUNT(*) FROM sqlite_master")
            cursor.fetchone()
            cursor.close()

            response_time = time.time() - start_time

            status = HealthStatus.HEALTHY if response_time < 1.0 else HealthStatus.WARNING

            return {
                'status': status,
                'response_time': response_time,
                'threshold': 1.0
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    return [
        HealthCheck(
            name="database_connection",
            component="database",
            check_function=check_database_connection,
            interval_seconds=30.0,
            failure_threshold=3
        ),
        HealthCheck(
            name="database_performance",
            component="database",
            check_function=check_database_performance,
            interval_seconds=60.0,
            failure_threshold=5
        )
    ]


def create_network_health_checks():
    """Create health checks for network operations."""
    def check_internet_connectivity():
        """Check basic internet connectivity."""
        try:
            import requests
            response = requests.get("https://httpbin.org/status/200", timeout=5)
            return {
                'status': HealthStatus.HEALTHY if response.status_code == 200 else HealthStatus.CRITICAL,
                'response_time': response.elapsed.total_seconds(),
                'status_code': response.status_code
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    def check_dns_resolution():
        """Check DNS resolution capability."""
        try:
            import socket
            start_time = time.time()
            ip = socket.gethostbyname("google.com")
            response_time = time.time() - start_time

            return {
                'status': HealthStatus.HEALTHY,
                'response_time': response_time,
                'resolved_ip': ip
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    return [
        HealthCheck(
            name="internet_connectivity",
            component="network",
            check_function=check_internet_connectivity,
            interval_seconds=60.0,
            failure_threshold=3
        ),
        HealthCheck(
            name="dns_resolution",
            component="network",
            check_function=check_dns_resolution,
            interval_seconds=120.0,
            failure_threshold=2
        )
    ]


def create_system_health_checks():
    """Create health checks for system resources."""
    def check_memory_usage():
        """Check system memory usage."""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            if memory_percent > 90:
                status = HealthStatus.CRITICAL
            elif memory_percent > 80:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY

            return {
                'status': status,
                'memory_percent': memory_percent,
                'available_mb': memory.available / 1024 / 1024,
                'total_mb': memory.total / 1024 / 1024
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    def check_disk_usage():
        """Check disk usage."""
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            if disk_percent > 95:
                status = HealthStatus.CRITICAL
            elif disk_percent > 85:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY

            return {
                'status': status,
                'disk_percent': disk_percent,
                'free_gb': disk.free / 1024 / 1024 / 1024,
                'total_gb': disk.total / 1024 / 1024 / 1024
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    def check_cpu_usage():
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)

            if cpu_percent > 95:
                status = HealthStatus.CRITICAL
            elif cpu_percent > 80:
                status = HealthStatus.WARNING
            else:
                status = HealthStatus.HEALTHY

            return {
                'status': status,
                'cpu_percent': cpu_percent,
                'cpu_count': psutil.cpu_count()
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'error_message': str(e)
            }

    return [
        HealthCheck(
            name="memory_usage",
            component="system",
            check_function=check_memory_usage,
            interval_seconds=30.0,
            failure_threshold=2
        ),
        HealthCheck(
            name="disk_usage",
            component="system",
            check_function=check_disk_usage,
            interval_seconds=300.0,  # 5 minutes
            failure_threshold=1
        ),
        HealthCheck(
            name="cpu_usage",
            component="system",
            check_function=check_cpu_usage,
            interval_seconds=60.0,
            failure_threshold=3
        )
    ]


# Global health monitor instance
health_monitor = HealthMonitor()