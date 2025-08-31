"""
Graceful degradation system for maintaining functionality during partial failures.
"""

import time
from typing import Any, Dict, List, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage


class DegradationLevel(Enum):
    """Levels of system degradation."""
    NORMAL = "normal"          # Full functionality
    MINOR = "minor"           # Minor features degraded
    MODERATE = "moderate"     # Moderate functionality loss
    SEVERE = "severe"         # Severe functionality loss
    CRITICAL = "critical"     # Critical systems only


class ComponentStatus(Enum):
    """Status of system components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ComponentHealth:
    """Health status of a system component."""
    name: str
    status: ComponentStatus
    last_check: float
    failure_count: int = 0
    consecutive_failures: int = 0
    degradation_level: DegradationLevel = DegradationLevel.NORMAL
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DegradationRule:
    """Rule for graceful degradation."""
    component_name: str
    failure_threshold: int
    degradation_action: Callable
    recovery_action: Optional[Callable] = None
    degradation_level: DegradationLevel = DegradationLevel.MODERATE
    cooldown_period: float = 300.0  # 5 minutes


class GracefulDegradationManager:
    """
    Manages graceful degradation of system functionality during failures.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("graceful_degradation")
        self.components = {}
        self.degradation_rules = {}
        self.overall_degradation_level = DegradationLevel.NORMAL
        self.degradation_history = []

    def register_component(self,
                          name: str,
                          health_check: Optional[Callable] = None,
                          degradation_rules: Optional[List[DegradationRule]] = None):
        """
        Register a system component for health monitoring.

        Args:
            name: Component name
            health_check: Function to check component health
            degradation_rules: Rules for handling component failures
        """
        self.components[name] = ComponentHealth(
            name=name,
            status=ComponentStatus.HEALTHY,
            last_check=time.time()
        )

        if degradation_rules:
            for rule in degradation_rules:
                self.degradation_rules[f"{name}:{rule.degradation_level.value}"] = rule

        if health_check:
            self.components[name].metadata['health_check'] = health_check

        self.logger.info("Component registered for graceful degradation",
                        structured_data={
                            'component': name,
                            'has_health_check': health_check is not None,
                            'rules_count': len(degradation_rules) if degradation_rules else 0
                        })

    def update_component_health(self,
                               name: str,
                               status: ComponentStatus,
                               error_message: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None):
        """
        Update health status of a component.

        Args:
            name: Component name
            status: New component status
            error_message: Error message if failed
            metadata: Additional metadata
        """
        if name not in self.components:
            self.logger.warning("Attempted to update unknown component",
                              structured_data={'component': name})
            return

        component = self.components[name]
        previous_status = component.status

        # Update component status
        component.status = status
        component.last_check = time.time()
        component.error_message = error_message

        if metadata:
            component.metadata.update(metadata)

        # Update failure counts
        if status == ComponentStatus.FAILED:
            component.failure_count += 1
            component.consecutive_failures += 1
        elif status == ComponentStatus.HEALTHY:
            component.consecutive_failures = 0

        # Check for degradation rules
        self._check_degradation_rules(component)

        # Log status change
        if previous_status != status:
            self.logger.info("Component status changed",
                           structured_data={
                               'component': name,
                               'previous_status': previous_status.value,
                               'new_status': status.value,
                               'consecutive_failures': component.consecutive_failures,
                               'error_message': error_message
                           })

        # Update overall system degradation level
        self._update_overall_degradation_level()

    def _check_degradation_rules(self, component: ComponentHealth):
        """Check and apply degradation rules for a component."""
        for rule_key, rule in self.degradation_rules.items():
            if rule.component_name == component.name:
                # Check if rule conditions are met
                if (component.consecutive_failures >= rule.failure_threshold and
                    component.degradation_level != rule.degradation_level):

                    # Check cooldown period
                    if 'last_degradation' in component.metadata:
                        time_since_last = time.time() - component.metadata['last_degradation']
                        if time_since_last < rule.cooldown_period:
                            continue

                    # Apply degradation
                    try:
                        rule.degradation_action()
                        component.degradation_level = rule.degradation_level
                        component.metadata['last_degradation'] = time.time()

                        self.degradation_history.append({
                            'timestamp': time.time(),
                            'component': component.name,
                            'action': 'degraded',
                            'level': rule.degradation_level.value,
                            'consecutive_failures': component.consecutive_failures
                        })

                        self.logger.warning("Component degraded",
                                          error_category=ErrorCategory.UNKNOWN_ERROR,
                                          structured_data={
                                              'component': component.name,
                                              'degradation_level': rule.degradation_level.value,
                                              'consecutive_failures': component.consecutive_failures,
                                              'failure_threshold': rule.failure_threshold
                                          })

                    except Exception as e:
                        self.logger.error("Failed to apply degradation rule",
                                        error_category=ErrorCategory.UNKNOWN_ERROR,
                                        structured_data={
                                            'component': component.name,
                                            'rule': rule_key,
                                            'error': str(e)
                                        })

    def _update_overall_degradation_level(self):
        """Update the overall system degradation level."""
        if not self.components:
            return

        # Count components by status
        status_counts = {}
        for component in self.components.values():
            status = component.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        total_components = len(self.components)
        failed_components = status_counts.get(ComponentStatus.FAILED.value, 0)
        degraded_components = status_counts.get(ComponentStatus.DEGRADED.value, 0)

        # Determine overall degradation level
        failure_rate = failed_components / total_components
        degradation_rate = (failed_components + degraded_components) / total_components

        if failure_rate >= 0.5 or degradation_rate >= 0.7:
            new_level = DegradationLevel.CRITICAL
        elif failure_rate >= 0.3 or degradation_rate >= 0.5:
            new_level = DegradationLevel.SEVERE
        elif failure_rate >= 0.2 or degradation_rate >= 0.3:
            new_level = DegradationLevel.MODERATE
        elif degradation_rate >= 0.1:
            new_level = DegradationLevel.MINOR
        else:
            new_level = DegradationLevel.NORMAL

        # Update if changed
        if new_level != self.overall_degradation_level:
            previous_level = self.overall_degradation_level
            self.overall_degradation_level = new_level

            self.degradation_history.append({
                'timestamp': time.time(),
                'component': 'system',
                'action': 'overall_degradation_changed',
                'level': new_level.value,
                'failure_rate': failure_rate,
                'degradation_rate': degradation_rate
            })

            self.logger.info("Overall system degradation level changed",
                           structured_data={
                               'previous_level': previous_level.value,
                               'new_level': new_level.value,
                               'failure_rate': failure_rate,
                               'degradation_rate': degradation_rate,
                               'status_counts': status_counts
                           })

    def get_component_status(self, name: str) -> Optional[ComponentHealth]:
        """Get status of a specific component."""
        return self.components.get(name)

    def get_all_component_statuses(self) -> Dict[str, ComponentHealth]:
        """Get status of all components."""
        return self.components.copy()

    def get_overall_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        status_counts = {}
        for component in self.components.values():
            status = component.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            'overall_degradation_level': self.overall_degradation_level.value,
            'total_components': len(self.components),
            'status_counts': status_counts,
            'degradation_history': self.degradation_history[-10:]  # Last 10 events
        }

    def attempt_recovery(self, component_name: str) -> bool:
        """
        Attempt to recover a failed component.

        Args:
            component_name: Name of component to recover

        Returns:
            True if recovery was attempted, False otherwise
        """
        if component_name not in self.components:
            return False

        component = self.components[component_name]

        # Find recovery rule
        recovery_rule = None
        for rule_key, rule in self.degradation_rules.items():
            if (rule.component_name == component_name and
                rule.recovery_action is not None):
                recovery_rule = rule
                break

        if not recovery_rule:
            self.logger.debug("No recovery rule found for component",
                            structured_data={'component': component_name})
            return False

        try:
            # Attempt recovery
            recovery_rule.recovery_action()

            # Reset component state
            component.status = ComponentStatus.HEALTHY
            component.consecutive_failures = 0
            component.error_message = None
            component.degradation_level = DegradationLevel.NORMAL

            self.degradation_history.append({
                'timestamp': time.time(),
                'component': component_name,
                'action': 'recovered',
                'level': DegradationLevel.NORMAL.value
            })

            self.logger.info("Component recovery successful",
                           structured_data={'component': component_name})

            # Update overall degradation level
            self._update_overall_degradation_level()

            return True

        except Exception as e:
            self.logger.error("Component recovery failed",
                            error_category=ErrorCategory.UNKNOWN_ERROR,
                            structured_data={
                                'component': component_name,
                                'error': str(e)
                            })
            return False

    def should_skip_operation(self, operation_name: str, component_name: str) -> bool:
        """
        Determine if an operation should be skipped based on component health.

        Args:
            operation_name: Name of the operation
            component_name: Required component name

        Returns:
            True if operation should be skipped
        """
        component = self.components.get(component_name)
        if not component:
            return False

        # Skip operations based on degradation level
        if component.degradation_level == DegradationLevel.CRITICAL:
            return True
        elif component.degradation_level == DegradationLevel.SEVERE:
            # Skip non-essential operations
            non_essential_ops = ['detailed_analysis', 'extended_processing', 'optional_enrichment']
            return operation_name in non_essential_ops
        elif component.degradation_level == DegradationLevel.MODERATE:
            # Skip less critical operations
            moderate_ops = ['caching', 'optimization', 'background_tasks']
            return operation_name in moderate_ops

        return False

    def get_degraded_functionality(self) -> Dict[str, Any]:
        """Get information about currently degraded functionality."""
        degraded_components = {}
        skipped_operations = []

        for name, component in self.components.items():
            if component.status != ComponentStatus.HEALTHY:
                degraded_components[name] = {
                    'status': component.status.value,
                    'degradation_level': component.degradation_level.value,
                    'consecutive_failures': component.consecutive_failures,
                    'error_message': component.error_message
                }

        return {
            'degraded_components': degraded_components,
            'overall_degradation_level': self.overall_degradation_level.value,
            'skipped_operations': skipped_operations,
            'degradation_summary': self._get_degradation_summary()
        }

    def _get_degradation_summary(self) -> str:
        """Get a human-readable degradation summary."""
        if self.overall_degradation_level == DegradationLevel.NORMAL:
            return "System operating normally with full functionality."

        level_descriptions = {
            DegradationLevel.MINOR: "Minor functionality degradation detected.",
            DegradationLevel.MODERATE: "Moderate functionality loss - some features may be limited.",
            DegradationLevel.SEVERE: "Severe functionality degradation - core features may be affected.",
            DegradationLevel.CRITICAL: "Critical degradation - system operating in emergency mode."
        }

        failed_count = sum(1 for c in self.components.values()
                          if c.status == ComponentStatus.FAILED)
        degraded_count = sum(1 for c in self.components.values()
                            if c.status == ComponentStatus.DEGRADED)

        summary = level_descriptions.get(self.overall_degradation_level, "Unknown degradation level")

        if failed_count > 0 or degraded_count > 0:
            summary += f" ({failed_count} failed, {degraded_count} degraded components)"

        return summary


# Pre-configured degradation rules for common components
def create_database_degradation_rules():
    """Create degradation rules for database operations."""
    def reduce_connection_pool():
        """Reduce database connection pool size."""
        # Implementation would reduce connection pool size
        pass

    def enable_read_only_mode():
        """Enable read-only mode for database."""
        # Implementation would switch to read-only operations
        pass

    return [
        DegradationRule(
            component_name="database",
            failure_threshold=3,
            degradation_action=reduce_connection_pool,
            degradation_level=DegradationLevel.MODERATE
        ),
        DegradationRule(
            component_name="database",
            failure_threshold=5,
            degradation_action=enable_read_only_mode,
            degradation_level=DegradationLevel.SEVERE
        )
    ]


def create_ai_degradation_rules():
    """Create degradation rules for AI operations."""
    def switch_to_mock_mode():
        """Switch AI analyzer to mock mode."""
        # Implementation would enable mock AI responses
        pass

    def reduce_analysis_depth():
        """Reduce depth of AI analysis."""
        # Implementation would use simpler analysis
        pass

    return [
        DegradationRule(
            component_name="ai_analyzer",
            failure_threshold=2,
            degradation_action=reduce_analysis_depth,
            degradation_level=DegradationLevel.MODERATE
        ),
        DegradationRule(
            component_name="ai_analyzer",
            failure_threshold=5,
            degradation_action=switch_to_mock_mode,
            degradation_level=DegradationLevel.SEVERE
        )
    ]


def create_network_degradation_rules():
    """Create degradation rules for network operations."""
    def increase_timeouts():
        """Increase network timeouts."""
        # Implementation would increase timeout values
        pass

    def reduce_concurrent_requests():
        """Reduce number of concurrent network requests."""
        # Implementation would limit concurrent operations
        pass

    return [
        DegradationRule(
            component_name="network",
            failure_threshold=5,
            degradation_action=increase_timeouts,
            degradation_level=DegradationLevel.MODERATE
        ),
        DegradationRule(
            component_name="network",
            failure_threshold=10,
            degradation_action=reduce_concurrent_requests,
            degradation_level=DegradationLevel.SEVERE
        )
    ]


# Global degradation manager instance
degradation_manager = GracefulDegradationManager()