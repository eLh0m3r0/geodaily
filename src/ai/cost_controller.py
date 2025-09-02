"""
AI Cost Control and Budget Management System.
"""

import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from ..config import Config


class CostAlertLevel(Enum):
    """Alert levels for cost monitoring."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostBudget:
    """Cost budget configuration."""
    daily_limit: float
    monthly_limit: float
    alert_threshold_percent: float = 80.0  # Alert when 80% of budget used
    hard_limit_percent: float = 95.0  # Hard stop when 95% of budget used


@dataclass
class CostMetrics:
    """Cost tracking metrics."""
    total_cost_today: float = 0.0
    total_cost_this_month: float = 0.0
    total_tokens_used_today: int = 0
    total_tokens_used_this_month: int = 0
    api_calls_today: int = 0
    api_calls_this_month: int = 0
    last_reset_date: str = ""
    last_reset_month: str = ""
    cost_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AICostEstimate:
    """Cost estimate for AI operations."""
    estimated_tokens: int
    estimated_cost: float
    confidence: float
    breakdown: Dict[str, Any]


class AICostController:
    """
    Controls AI usage costs with budget monitoring and usage limits.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("ai_cost_controller")
        self.metrics = CostMetrics()
        self.budget = CostBudget(
            daily_limit=Config.AI_MAX_COST_PER_DAY,
            monthly_limit=2.0,  # $2/month default
            alert_threshold_percent=80.0,
            hard_limit_percent=95.0
        )
        self._lock = threading.RLock()
        self.alerts_enabled = True

        # Load existing metrics if available
        self._load_metrics()

    def check_budget_allowance(self, estimated_cost: float) -> Dict[str, Any]:
        """
        Check if an operation is within budget limits.

        Args:
            estimated_cost: Estimated cost of the operation

        Returns:
            Dict with allowance status and details
        """
        with self._lock:
            self._ensure_daily_reset()

            result = {
                'allowed': True,
                'reason': 'within_budget',
                'current_daily_cost': self.metrics.total_cost_today,
                'current_monthly_cost': self.metrics.total_cost_this_month,
                'estimated_total_daily': self.metrics.total_cost_today + estimated_cost,
                'estimated_total_monthly': self.metrics.total_cost_this_month + estimated_cost,
                'daily_limit': self.budget.daily_limit,
                'monthly_limit': self.budget.monthly_limit
            }

            # Check daily limit
            if self.metrics.total_cost_today + estimated_cost > self.budget.daily_limit:
                result['allowed'] = False
                result['reason'] = 'daily_limit_exceeded'
                self.logger.warning("AI operation blocked: Daily budget limit exceeded",
                                  structured_data={
                                      'current_cost': self.metrics.total_cost_today,
                                      'estimated_cost': estimated_cost,
                                      'daily_limit': self.budget.daily_limit,
                                      'overage': (self.metrics.total_cost_today + estimated_cost) - self.budget.daily_limit
                                  })

            # Check monthly limit
            elif self.metrics.total_cost_this_month + estimated_cost > self.budget.monthly_limit:
                result['allowed'] = False
                result['reason'] = 'monthly_limit_exceeded'
                self.logger.warning("AI operation blocked: Monthly budget limit exceeded",
                                  structured_data={
                                      'current_cost': self.metrics.total_cost_this_month,
                                      'estimated_cost': estimated_cost,
                                      'monthly_limit': self.budget.monthly_limit,
                                      'overage': (self.metrics.total_cost_this_month + estimated_cost) - self.budget.monthly_limit
                                  })

            # Check hard limit thresholds
            daily_usage_percent = (self.metrics.total_cost_today / self.budget.daily_limit) * 100
            monthly_usage_percent = (self.metrics.total_cost_this_month / self.budget.monthly_limit) * 100

            if daily_usage_percent >= self.budget.hard_limit_percent:
                result['allowed'] = False
                result['reason'] = 'daily_hard_limit_reached'
            elif monthly_usage_percent >= self.budget.hard_limit_percent:
                result['allowed'] = False
                result['reason'] = 'monthly_hard_limit_reached'

            return result

    def record_cost(self, cost: float, tokens_used: int, operation_type: str = "analysis"):
        """
        Record actual cost and usage.

        Args:
            cost: Actual cost incurred
            tokens_used: Number of tokens used
            operation_type: Type of operation
        """
        with self._lock:
            self._ensure_daily_reset()
            self._ensure_monthly_reset()

            # Update metrics
            self.metrics.total_cost_today += cost
            self.metrics.total_cost_this_month += cost
            self.metrics.total_tokens_used_today += tokens_used
            self.metrics.total_tokens_used_this_month += tokens_used
            self.metrics.api_calls_today += 1
            self.metrics.api_calls_this_month += 1

            # Record in history
            cost_record = {
                'timestamp': time.time(),
                'cost': cost,
                'tokens_used': tokens_used,
                'operation_type': operation_type,
                'daily_total': self.metrics.total_cost_today,
                'monthly_total': self.metrics.total_cost_this_month
            }
            self.metrics.cost_history.append(cost_record)

            # Keep only last 1000 records
            if len(self.metrics.cost_history) > 1000:
                self.metrics.cost_history = self.metrics.cost_history[-1000:]

            # Check for alerts
            self._check_alerts()

            # Save metrics
            self._save_metrics()

            self.logger.info("AI cost recorded",
                            structured_data={
                                'cost': cost,
                                'tokens_used': tokens_used,
                                'operation_type': operation_type,
                                'daily_total': self.metrics.total_cost_today,
                                'monthly_total': self.metrics.total_cost_this_month
                            })

    def estimate_cost(self, text_length: int, operation_type: str = "analysis") -> AICostEstimate:
        """
        Estimate cost for an operation based on text length.

        Args:
            text_length: Length of text to process
            operation_type: Type of operation

        Returns:
            Cost estimate
        """
        # Rough token estimation (1 token ≈ 4 characters)
        estimated_tokens = max(100, int(text_length / 4))

        # Claude pricing (approximate)
        # Input: ~$0.0008 per 1K tokens
        # Output: ~$0.0024 per 1K tokens
        input_cost = (estimated_tokens / 1000) * 0.0008
        output_cost = (estimated_tokens / 1000) * 0.0024  # Assume similar output length
        estimated_cost = input_cost + output_cost

        # Adjust based on operation type
        if operation_type == "clustering":
            estimated_cost *= 0.8  # Clustering might be cheaper
        elif operation_type == "detailed_analysis":
            estimated_cost *= 1.2  # Detailed analysis might be more expensive

        confidence = 0.7  # Base confidence level

        return AICostEstimate(
            estimated_tokens=estimated_tokens,
            estimated_cost=round(estimated_cost, 6),
            confidence=confidence,
            breakdown={
                'input_tokens': estimated_tokens,
                'output_tokens': estimated_tokens,
                'input_cost': round(input_cost, 6),
                'output_cost': round(output_cost, 6),
                'operation_type': operation_type
            }
        )

    def get_cost_report(self) -> Dict[str, Any]:
        """Get comprehensive cost report."""
        with self._lock:
            self._ensure_daily_reset()
            self._ensure_monthly_reset()

            daily_usage_percent = (self.metrics.total_cost_today / self.budget.daily_limit) * 100
            monthly_usage_percent = (self.metrics.total_cost_this_month / self.budget.monthly_limit) * 100

            # Calculate recent trends
            recent_costs = [record['cost'] for record in self.metrics.cost_history[-10:]]
            avg_recent_cost = sum(recent_costs) / len(recent_costs) if recent_costs else 0

            return {
                'current_metrics': {
                    'daily_cost': round(self.metrics.total_cost_today, 4),
                    'monthly_cost': round(self.metrics.total_cost_this_month, 4),
                    'daily_tokens': self.metrics.total_tokens_used_today,
                    'monthly_tokens': self.metrics.total_tokens_used_this_month,
                    'daily_api_calls': self.metrics.api_calls_today,
                    'monthly_api_calls': self.metrics.api_calls_this_month
                },
                'budget_limits': {
                    'daily_limit': self.budget.daily_limit,
                    'monthly_limit': self.budget.monthly_limit,
                    'daily_usage_percent': round(daily_usage_percent, 1),
                    'monthly_usage_percent': round(monthly_usage_percent, 1)
                },
                'alerts': {
                    'daily_alert_threshold': self.budget.alert_threshold_percent,
                    'monthly_alert_threshold': self.budget.alert_threshold_percent,
                    'daily_hard_limit': self.budget.hard_limit_percent,
                    'monthly_hard_limit': self.budget.hard_limit_percent
                },
                'trends': {
                    'avg_recent_cost': round(avg_recent_cost, 6),
                    'recent_operations': len(recent_costs),
                    'cost_history_count': len(self.metrics.cost_history)
                },
                'status': self._get_budget_status()
            }

    def _get_budget_status(self) -> str:
        """Get current budget status."""
        daily_percent = (self.metrics.total_cost_today / self.budget.daily_limit) * 100
        monthly_percent = (self.metrics.total_cost_this_month / self.budget.monthly_limit) * 100

        if daily_percent >= self.budget.hard_limit_percent or monthly_percent >= self.budget.hard_limit_percent:
            return 'critical'
        elif daily_percent >= self.budget.alert_threshold_percent or monthly_percent >= self.budget.alert_threshold_percent:
            return 'warning'
        else:
            return 'normal'

    def _check_alerts(self):
        """Check for cost alerts and trigger notifications."""
        if not self.alerts_enabled:
            return

        daily_percent = (self.metrics.total_cost_today / self.budget.daily_limit) * 100
        monthly_percent = (self.metrics.total_cost_this_month / self.budget.monthly_limit) * 100

        # Daily alerts
        if daily_percent >= self.budget.hard_limit_percent:
            self._trigger_alert(CostAlertLevel.CRITICAL, 'daily_hard_limit',
                              f"Daily AI budget hard limit reached: ${self.metrics.total_cost_today:.4f} / ${self.budget.daily_limit:.4f}")
        elif daily_percent >= self.budget.alert_threshold_percent:
            self._trigger_alert(CostAlertLevel.WARNING, 'daily_threshold',
                              f"Daily AI budget alert: ${self.metrics.total_cost_today:.4f} / ${self.budget.daily_limit:.4f} ({daily_percent:.1f}%)")

        # Monthly alerts
        if monthly_percent >= self.budget.hard_limit_percent:
            self._trigger_alert(CostAlertLevel.CRITICAL, 'monthly_hard_limit',
                              f"Monthly AI budget hard limit reached: ${self.metrics.total_cost_this_month:.4f} / ${self.budget.monthly_limit:.4f}")
        elif monthly_percent >= self.budget.alert_threshold_percent:
            self._trigger_alert(CostAlertLevel.WARNING, 'monthly_threshold',
                              f"Monthly AI budget alert: ${self.metrics.total_cost_this_month:.4f} / ${self.budget.monthly_limit:.4f} ({monthly_percent:.1f}%)")

    def _trigger_alert(self, level: CostAlertLevel, alert_type: str, message: str):
        """Trigger a cost alert."""
        log_method = {
            CostAlertLevel.INFO: self.logger.info,
            CostAlertLevel.WARNING: self.logger.warning,
            CostAlertLevel.CRITICAL: self.logger.error
        }.get(level, self.logger.info)

        log_method(f"AI Cost Alert: {message}",
                  error_category=ErrorCategory.UNKNOWN_ERROR,
                  structured_data={
                      'alert_level': level.value,
                      'alert_type': alert_type,
                      'current_daily_cost': self.metrics.total_cost_today,
                      'current_monthly_cost': self.metrics.total_cost_this_month,
                      'daily_limit': self.budget.daily_limit,
                      'monthly_limit': self.budget.monthly_limit
                  })

    def _ensure_daily_reset(self):
        """Ensure daily metrics are reset if it's a new day."""
        today = datetime.now().strftime('%Y-%m-%d')
        if self.metrics.last_reset_date != today:
            self.logger.info("Resetting daily AI cost metrics",
                            structured_data={
                                'previous_daily_cost': self.metrics.total_cost_today,
                                'previous_daily_tokens': self.metrics.total_tokens_used_today,
                                'previous_daily_calls': self.metrics.api_calls_today
                            })

            self.metrics.total_cost_today = 0.0
            self.metrics.total_tokens_used_today = 0
            self.metrics.api_calls_today = 0
            self.metrics.last_reset_date = today

    def _ensure_monthly_reset(self):
        """Ensure monthly metrics are reset if it's a new month."""
        this_month = datetime.now().strftime('%Y-%m')
        if self.metrics.last_reset_month != this_month:
            self.logger.info("Resetting monthly AI cost metrics",
                            structured_data={
                                'previous_monthly_cost': self.metrics.total_cost_this_month,
                                'previous_monthly_tokens': self.metrics.total_tokens_used_this_month,
                                'previous_monthly_calls': self.metrics.api_calls_this_month
                            })

            self.metrics.total_cost_this_month = 0.0
            self.metrics.total_tokens_used_this_month = 0
            self.metrics.api_calls_this_month = 0
            self.metrics.last_reset_month = this_month

    def _load_metrics(self):
        """Load metrics from persistent storage."""
        try:
            # In a real implementation, this would load from a database or file
            # For now, we'll just initialize with defaults
            pass
        except Exception as e:
            self.logger.warning(f"Failed to load cost metrics: {e}")

    def _save_metrics(self):
        """Save metrics to persistent storage."""
        try:
            # In a real implementation, this would save to a database or file
            # For now, we'll just keep it in memory
            pass
        except Exception as e:
            self.logger.warning(f"Failed to save cost metrics: {e}")

    def reset_metrics(self):
        """Reset all metrics (for testing)."""
        with self._lock:
            self.metrics = CostMetrics()
            self.logger.info("AI cost metrics reset")


# Global AI cost controller instance
ai_cost_controller = AICostController()