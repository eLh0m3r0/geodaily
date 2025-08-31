"""
Recovery procedures for handling transient failures and system restoration.
"""

import time
import threading
from typing import Any, Dict, List, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage


class RecoveryStrategy(Enum):
    """Recovery strategy types."""
    IMMEDIATE = "immediate"      # Immediate retry
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Progressive backoff
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker pattern
    GRADUAL_RECOVERY = "gradual_recovery"  # Gradual load increase
    SERVICE_RESTART = "service_restart"  # Restart service/component


class RecoveryStatus(Enum):
    """Status of recovery operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    attempt_id: str
    component_name: str
    strategy: RecoveryStrategy
    status: RecoveryStatus
    start_time: float
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryProcedure:
    """Definition of a recovery procedure."""
    name: str
    component_name: str
    strategy: RecoveryStrategy
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 300.0  # 5 minutes
    backoff_factor: float = 2.0
    recovery_action: Callable
    validation_action: Optional[Callable] = None
    pre_recovery_checks: List[Callable] = field(default_factory=list)
    post_recovery_checks: List[Callable] = field(default_factory=list)
    cooldown_period: float = 60.0  # 1 minute between attempts


class RecoveryManager:
    """
    Manages recovery procedures for system components.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("recovery_manager")
        self.procedures = {}
        self.attempts = []
        self.active_recoveries = {}
        self.recovery_stats = {}
        self._lock = threading.RLock()

    def register_procedure(self, procedure: RecoveryProcedure):
        """
        Register a recovery procedure.

        Args:
            procedure: Recovery procedure to register
        """
        with self._lock:
            key = f"{procedure.component_name}:{procedure.name}"
            self.procedures[key] = procedure

            # Initialize stats
            if procedure.component_name not in self.recovery_stats:
                self.recovery_stats[procedure.component_name] = {
                    'total_attempts': 0,
                    'successful_recoveries': 0,
                    'failed_recoveries': 0,
                    'last_recovery_time': None,
                    'average_recovery_time': 0.0
                }

            self.logger.info("Recovery procedure registered",
                           structured_data={
                               'procedure': procedure.name,
                               'component': procedure.component_name,
                               'strategy': procedure.strategy.value
                           })

    def trigger_recovery(self, component_name: str, procedure_name: str = None) -> str:
        """
        Trigger recovery for a component.

        Args:
            component_name: Name of component to recover
            procedure_name: Specific procedure name (optional)

        Returns:
            Recovery attempt ID
        """
        with self._lock:
            # Find appropriate procedure
            procedure = self._find_procedure(component_name, procedure_name)
            if not procedure:
                self.logger.warning("No recovery procedure found",
                                  structured_data={
                                      'component': component_name,
                                      'procedure_name': procedure_name
                                  })
                return None

            # Check if recovery is already in progress
            if component_name in self.active_recoveries:
                self.logger.info("Recovery already in progress",
                               structured_data={'component': component_name})
                return self.active_recoveries[component_name]

            # Create recovery attempt
            attempt_id = f"{component_name}_{int(time.time())}_{len(self.attempts)}"
            attempt = RecoveryAttempt(
                attempt_id=attempt_id,
                component_name=component_name,
                strategy=procedure.strategy,
                status=RecoveryStatus.PENDING,
                start_time=time.time()
            )

            self.attempts.append(attempt)
            self.active_recoveries[component_name] = attempt_id

            # Start recovery in background thread
            thread = threading.Thread(
                target=self._execute_recovery,
                args=(procedure, attempt),
                daemon=True
            )
            thread.start()

            self.logger.info("Recovery triggered",
                           structured_data={
                               'component': component_name,
                               'procedure': procedure.name,
                               'attempt_id': attempt_id,
                               'strategy': procedure.strategy.value
                           })

            return attempt_id

    def _find_procedure(self, component_name: str, procedure_name: str = None) -> Optional[RecoveryProcedure]:
        """Find appropriate recovery procedure."""
        if procedure_name:
            key = f"{component_name}:{procedure_name}"
            return self.procedures.get(key)

        # Find default procedure for component
        for key, procedure in self.procedures.items():
            if procedure.component_name == component_name:
                return procedure

        return None

    def _execute_recovery(self, procedure: RecoveryProcedure, attempt: RecoveryAttempt):
        """Execute recovery procedure."""
        try:
            attempt.status = RecoveryStatus.IN_PROGRESS

            # Pre-recovery checks
            if not self._run_checks(procedure.pre_recovery_checks, "pre-recovery"):
                attempt.status = RecoveryStatus.FAILED
                attempt.error_message = "Pre-recovery checks failed"
                return

            # Execute recovery based on strategy
            if procedure.strategy == RecoveryStrategy.IMMEDIATE:
                success = self._execute_immediate_recovery(procedure, attempt)
            elif procedure.strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
                success = self._execute_exponential_backoff_recovery(procedure, attempt)
            elif procedure.strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                success = self._execute_circuit_breaker_recovery(procedure, attempt)
            elif procedure.strategy == RecoveryStrategy.GRADUAL_RECOVERY:
                success = self._execute_gradual_recovery(procedure, attempt)
            elif procedure.strategy == RecoveryStrategy.SERVICE_RESTART:
                success = self._execute_service_restart_recovery(procedure, attempt)
            else:
                attempt.error_message = f"Unknown recovery strategy: {procedure.strategy}"
                success = False

            # Post-recovery checks and validation
            if success:
                if procedure.validation_action:
                    try:
                        validation_result = procedure.validation_action()
                        if not validation_result:
                            success = False
                            attempt.error_message = "Recovery validation failed"
                    except Exception as e:
                        success = False
                        attempt.error_message = f"Recovery validation error: {e}"

                if success and not self._run_checks(procedure.post_recovery_checks, "post-recovery"):
                    success = False
                    attempt.error_message = "Post-recovery checks failed"

            # Update attempt status
            attempt.end_time = time.time()
            attempt.status = RecoveryStatus.SUCCESSFUL if success else RecoveryStatus.FAILED

            # Update statistics
            self._update_recovery_stats(procedure.component_name, success, attempt.end_time - attempt.start_time)

            # Log result
            log_data = {
                'component': procedure.component_name,
                'procedure': procedure.name,
                'attempt_id': attempt.attempt_id,
                'duration': attempt.end_time - attempt.start_time,
                'success': success
            }

            if success:
                self.logger.info("Recovery completed successfully", structured_data=log_data)
            else:
                self.logger.error("Recovery failed",
                                error_category=ErrorCategory.UNKNOWN_ERROR,
                                structured_data={
                                    **log_data,
                                    'error_message': attempt.error_message
                                })

        except Exception as e:
            attempt.status = RecoveryStatus.FAILED
            attempt.end_time = time.time()
            attempt.error_message = str(e)

            self.logger.error("Recovery execution error",
                            error_category=ErrorCategory.UNKNOWN_ERROR,
                            structured_data={
                                'component': procedure.component_name,
                                'procedure': procedure.name,
                                'attempt_id': attempt.attempt_id,
                                'error': str(e)
                            })

        finally:
            # Clean up active recovery
            with self._lock:
                self.active_recoveries.pop(procedure.component_name, None)

    def _run_checks(self, checks: List[Callable], check_type: str) -> bool:
        """Run a list of checks."""
        for check in checks:
            try:
                result = check()
                if not result:
                    self.logger.warning(f"{check_type} check failed",
                                      structured_data={'check': check.__name__})
                    return False
            except Exception as e:
                self.logger.error(f"{check_type} check error",
                                error_category=ErrorCategory.UNKNOWN_ERROR,
                                structured_data={
                                    'check': check.__name__,
                                    'error': str(e)
                                })
                return False
        return True

    def _execute_immediate_recovery(self, procedure: RecoveryProcedure, attempt: RecoveryAttempt) -> bool:
        """Execute immediate recovery."""
        try:
            return procedure.recovery_action()
        except Exception as e:
            attempt.error_message = str(e)
            return False

    def _execute_exponential_backoff_recovery(self, procedure: RecoveryProcedure, attempt: RecoveryAttempt) -> bool:
        """Execute recovery with exponential backoff."""
        for attempt_num in range(procedure.max_attempts):
            try:
                success = procedure.recovery_action()
                if success:
                    return True

                if attempt_num < procedure.max_attempts - 1:
                    delay = min(procedure.base_delay * (procedure.backoff_factor ** attempt_num),
                              procedure.max_delay)
                    time.sleep(delay)

            except Exception as e:
                attempt.error_message = str(e)
                if attempt_num < procedure.max_attempts - 1:
                    delay = min(procedure.base_delay * (procedure.backoff_factor ** attempt_num),
                              procedure.max_delay)
                    time.sleep(delay)
                else:
                    return False

        return False

    def _execute_circuit_breaker_recovery(self, procedure: RecoveryProcedure, attempt: RecoveryAttempt) -> bool:
        """Execute circuit breaker based recovery."""
        # Import here to avoid circular imports
        from .circuit_breaker import get_circuit_breaker

        circuit = get_circuit_breaker(f"recovery_{procedure.component_name}")

        try:
            return circuit.call(procedure.recovery_action)
        except Exception as e:
            attempt.error_message = str(e)
            return False

    def _execute_gradual_recovery(self, procedure: RecoveryProcedure, attempt: RecoveryAttempt) -> bool:
        """Execute gradual recovery with increasing load."""
        # Start with basic recovery
        try:
            base_success = procedure.recovery_action()
            if not base_success:
                return False

            # Gradually increase load/capacity
            for level in range(1, 4):  # 3 levels of load increase
                time.sleep(procedure.base_delay * level)

                # Here you would implement load testing/validation
                # For now, just assume success
                attempt.metadata[f'load_level_{level}'] = True

            return True

        except Exception as e:
            attempt.error_message = str(e)
            return False

    def _execute_service_restart_recovery(self, procedure: RecoveryProcedure, attempt: RecoveryAttempt) -> bool:
        """Execute service restart recovery."""
        try:
            # This would typically involve restarting a service or process
            # For now, just call the recovery action
            return procedure.recovery_action()
        except Exception as e:
            attempt.error_message = str(e)
            return False

    def _update_recovery_stats(self, component_name: str, success: bool, duration: float):
        """Update recovery statistics."""
        stats = self.recovery_stats[component_name]
        stats['total_attempts'] += 1

        if success:
            stats['successful_recoveries'] += 1
        else:
            stats['failed_recoveries'] += 1

        stats['last_recovery_time'] = time.time()

        # Update average recovery time
        if success:
            current_avg = stats['average_recovery_time']
            total_successful = stats['successful_recoveries']
            stats['average_recovery_time'] = (current_avg * (total_successful - 1) + duration) / total_successful

    def get_recovery_status(self, attempt_id: str) -> Optional[RecoveryAttempt]:
        """Get status of a recovery attempt."""
        for attempt in self.attempts:
            if attempt.attempt_id == attempt_id:
                return attempt
        return None

    def get_component_recovery_stats(self, component_name: str) -> Dict[str, Any]:
        """Get recovery statistics for a component."""
        return self.recovery_stats.get(component_name, {})

    def get_active_recoveries(self) -> Dict[str, str]:
        """Get currently active recovery operations."""
        with self._lock:
            return self.active_recoveries.copy()

    def cancel_recovery(self, component_name: str) -> bool:
        """
        Cancel active recovery for a component.

        Args:
            component_name: Name of component

        Returns:
            True if recovery was cancelled, False otherwise
        """
        with self._lock:
            attempt_id = self.active_recoveries.get(component_name)
            if not attempt_id:
                return False

            # Find and update attempt
            for attempt in self.attempts:
                if attempt.attempt_id == attempt_id:
                    attempt.status = RecoveryStatus.CANCELLED
                    attempt.end_time = time.time()
                    break

            # Remove from active recoveries
            self.active_recoveries.pop(component_name, None)

            self.logger.info("Recovery cancelled",
                           structured_data={
                               'component': component_name,
                               'attempt_id': attempt_id
                           })

            return True

    def cleanup_old_attempts(self, max_age_hours: int = 24):
        """Clean up old recovery attempts."""
        cutoff_time = time.time() - (max_age_hours * 3600)

        with self._lock:
            # Remove old attempts
            self.attempts = [
                attempt for attempt in self.attempts
                if attempt.end_time is None or attempt.end_time > cutoff_time
            ]

        self.logger.debug("Cleaned up old recovery attempts",
                         structured_data={
                             'removed_count': len(self.attempts),
                             'max_age_hours': max_age_hours
                         })


# Pre-configured recovery procedures
def create_database_recovery_procedures():
    """Create recovery procedures for database operations."""
    def restart_database_connections():
        """Restart database connections."""
        # Implementation would restart connection pool
        return True

    def rebuild_database_connection():
        """Rebuild database connection from scratch."""
        # Implementation would recreate connection
        return True

    def database_health_check():
        """Check database health."""
        # Implementation would perform health check
        return True

    return [
        RecoveryProcedure(
            name="connection_restart",
            component_name="database",
            strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=3,
            recovery_action=restart_database_connections,
            validation_action=database_health_check,
            pre_recovery_checks=[],
            post_recovery_checks=[database_health_check]
        ),
        RecoveryProcedure(
            name="full_rebuild",
            component_name="database",
            strategy=RecoveryStrategy.CIRCUIT_BREAKER,
            max_attempts=1,
            recovery_action=rebuild_database_connection,
            validation_action=database_health_check
        )
    ]


def create_network_recovery_procedures():
    """Create recovery procedures for network operations."""
    def reset_network_connections():
        """Reset network connections."""
        # Implementation would reset connection pools
        return True

    def test_network_connectivity():
        """Test network connectivity."""
        # Implementation would test connectivity
        return True

    return [
        RecoveryProcedure(
            name="connection_reset",
            component_name="network",
            strategy=RecoveryStrategy.IMMEDIATE,
            max_attempts=2,
            recovery_action=reset_network_connections,
            validation_action=test_network_connectivity
        )
    ]


def create_ai_recovery_procedures():
    """Create recovery procedures for AI operations."""
    def switch_to_fallback_mode():
        """Switch AI to fallback mode."""
        # Implementation would enable fallback AI
        return True

    def restart_ai_service():
        """Restart AI service."""
        # Implementation would restart AI service
        return True

    def ai_health_check():
        """Check AI service health."""
        # Implementation would perform health check
        return True

    return [
        RecoveryProcedure(
            name="fallback_mode",
            component_name="ai_analyzer",
            strategy=RecoveryStrategy.IMMEDIATE,
            recovery_action=switch_to_fallback_mode,
            validation_action=ai_health_check
        ),
        RecoveryProcedure(
            name="service_restart",
            component_name="ai_analyzer",
            strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=2,
            recovery_action=restart_ai_service,
            validation_action=ai_health_check
        )
    ]


# Global recovery manager instance
recovery_manager = RecoveryManager()