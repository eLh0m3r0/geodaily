"""
Configuration management for resilience features.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

from ..config import Config


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    name_prefix: str = "resilience"


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    enabled: bool = True
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter_range: float = 0.1
    retryable_exceptions: List[str] = field(default_factory=lambda: [
        "ConnectionError", "TimeoutError", "HTTPError", "ApiError"
    ])


@dataclass
class DatabaseConfig:
    """Configuration for database resilience."""
    enabled: bool = True
    max_connections: int = 10
    connection_timeout: float = 30.0
    max_idle_time: float = 300.0
    circuit_breaker_name: str = "database"


@dataclass
class NetworkConfig:
    """Configuration for network resilience."""
    enabled: bool = True
    request_timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 2.0
    circuit_breaker_name: str = "network"
    connectivity_check_interval: float = 60.0


@dataclass
class FallbackConfig:
    """Configuration for fallback content generation."""
    enabled: bool = True
    max_fallback_articles: int = 10
    fallback_quality_threshold: float = 0.5
    enable_ai_fallback: bool = True
    cache_fallback_content: bool = True
    cache_ttl_seconds: int = 3600


@dataclass
class DegradationConfig:
    """Configuration for graceful degradation."""
    enabled: bool = True
    health_check_interval: float = 60.0
    degradation_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "minor": 0.1,
        "moderate": 0.3,
        "severe": 0.5,
        "critical": 0.7
    })
    component_weights: Dict[str, float] = field(default_factory=lambda: {
        "database": 1.0,
        "network": 0.8,
        "ai_analyzer": 0.6,
        "collectors": 0.7,
        "publishers": 0.5
    })


@dataclass
class RecoveryConfig:
    """Configuration for recovery procedures."""
    enabled: bool = True
    max_concurrent_recoveries: int = 3
    recovery_timeout: float = 300.0
    cleanup_interval_hours: int = 24
    auto_recovery_enabled: bool = True
    recovery_cooldown_seconds: float = 60.0


@dataclass
class HealthMonitoringConfig:
    """Configuration for health monitoring."""
    enabled: bool = True
    check_interval_seconds: float = 60.0
    failure_threshold: int = 3
    recovery_threshold: int = 2
    alert_on_failure: bool = True
    alert_cooldown_seconds: float = 300.0


@dataclass
class ResilienceConfig:
    """Main configuration for all resilience features."""
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    degradation: DegradationConfig = field(default_factory=DegradationConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    health_monitoring: HealthMonitoringConfig = field(default_factory=HealthMonitoringConfig)

    # Global settings
    enabled: bool = True
    log_level: str = "INFO"
    metrics_enabled: bool = True
    alert_enabled: bool = False
    alert_webhook_url: Optional[str] = None


class ResilienceConfigManager:
    """
    Manages resilience configuration loading, validation, and updates.
    """

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or Config.PROJECT_ROOT / "resilience_config.json"
        self._config = None
        self._load_config()

    def _load_config(self):
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = ResilienceConfig(**data)
            except Exception as e:
                print(f"Error loading resilience config: {e}")
                self._config = ResilienceConfig()
        else:
            self._config = ResilienceConfig()

    def save_config(self):
        """Save current configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._config), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving resilience config: {e}")

    def get_config(self) -> ResilienceConfig:
        """Get current configuration."""
        return self._config

    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values."""
        def update_nested(obj, key_path: List[str], value: Any):
            if len(key_path) == 1:
                setattr(obj, key_path[0], value)
            else:
                current = getattr(obj, key_path[0])
                update_nested(current, key_path[1:], value)

        for key, value in updates.items():
            key_path = key.split('.')
            update_nested(self._config, key_path, value)

        self.save_config()

    def reset_to_defaults(self):
        """Reset configuration to default values."""
        self._config = ResilienceConfig()
        self.save_config()

    def validate_config(self) -> List[str]:
        """Validate current configuration and return list of issues."""
        issues = []

        config = self._config

        # Validate circuit breaker settings
        if config.circuit_breaker.failure_threshold < 1:
            issues.append("circuit_breaker.failure_threshold must be >= 1")
        if config.circuit_breaker.recovery_timeout < 1:
            issues.append("circuit_breaker.recovery_timeout must be >= 1")

        # Validate retry settings
        if config.retry.max_attempts < 1:
            issues.append("retry.max_attempts must be >= 1")
        if config.retry.base_delay <= 0:
            issues.append("retry.base_delay must be > 0")
        if config.retry.max_delay < config.retry.base_delay:
            issues.append("retry.max_delay must be >= retry.base_delay")

        # Validate database settings
        if config.database.max_connections < 1:
            issues.append("database.max_connections must be >= 1")
        if config.database.connection_timeout <= 0:
            issues.append("database.connection_timeout must be > 0")

        # Validate network settings
        if config.network.request_timeout <= 0:
            issues.append("network.request_timeout must be > 0")
        if config.network.max_retries < 0:
            issues.append("network.max_retries must be >= 0")

        # Validate fallback settings
        if config.fallback.max_fallback_articles < 1:
            issues.append("fallback.max_fallback_articles must be >= 1")
        if not (0 <= config.fallback.fallback_quality_threshold <= 1):
            issues.append("fallback.fallback_quality_threshold must be between 0 and 1")

        # Validate degradation settings
        for level, threshold in config.degradation.degradation_thresholds.items():
            if not (0 <= threshold <= 1):
                issues.append(f"degradation.degradation_thresholds.{level} must be between 0 and 1")

        # Validate recovery settings
        if config.recovery.max_concurrent_recoveries < 1:
            issues.append("recovery.max_concurrent_recoveries must be >= 1")
        if config.recovery.recovery_timeout <= 0:
            issues.append("recovery.recovery_timeout must be > 0")

        # Validate health monitoring settings
        if config.health_monitoring.check_interval_seconds <= 0:
            issues.append("health_monitoring.check_interval_seconds must be > 0")
        if config.health_monitoring.failure_threshold < 1:
            issues.append("health_monitoring.failure_threshold must be >= 1")

        return issues

    def get_environment_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables."""
        overrides = {}

        # Circuit breaker overrides
        if os.getenv("RESILIENCE_CB_ENABLED"):
            overrides["circuit_breaker.enabled"] = os.getenv("RESILIENCE_CB_ENABLED").lower() == "true"
        if os.getenv("RESILIENCE_CB_FAILURE_THRESHOLD"):
            overrides["circuit_breaker.failure_threshold"] = int(os.getenv("RESILIENCE_CB_FAILURE_THRESHOLD"))
        if os.getenv("RESILIENCE_CB_RECOVERY_TIMEOUT"):
            overrides["circuit_breaker.recovery_timeout"] = float(os.getenv("RESILIENCE_CB_RECOVERY_TIMEOUT"))

        # Retry overrides
        if os.getenv("RESILIENCE_RETRY_ENABLED"):
            overrides["retry.enabled"] = os.getenv("RESILIENCE_RETRY_ENABLED").lower() == "true"
        if os.getenv("RESILIENCE_RETRY_MAX_ATTEMPTS"):
            overrides["retry.max_attempts"] = int(os.getenv("RESILIENCE_RETRY_MAX_ATTEMPTS"))
        if os.getenv("RESILIENCE_RETRY_BASE_DELAY"):
            overrides["retry.base_delay"] = float(os.getenv("RESILIENCE_RETRY_BASE_DELAY"))

        # Database overrides
        if os.getenv("RESILIENCE_DB_ENABLED"):
            overrides["database.enabled"] = os.getenv("RESILIENCE_DB_ENABLED").lower() == "true"
        if os.getenv("RESILIENCE_DB_MAX_CONNECTIONS"):
            overrides["database.max_connections"] = int(os.getenv("RESILIENCE_DB_MAX_CONNECTIONS"))

        # Network overrides
        if os.getenv("RESILIENCE_NETWORK_ENABLED"):
            overrides["network.enabled"] = os.getenv("RESILIENCE_NETWORK_ENABLED").lower() == "true"
        if os.getenv("RESILIENCE_NETWORK_TIMEOUT"):
            overrides["network.request_timeout"] = float(os.getenv("RESILIENCE_NETWORK_TIMEOUT"))

        # Global overrides
        if os.getenv("RESILIENCE_ENABLED"):
            overrides["enabled"] = os.getenv("RESILIENCE_ENABLED").lower() == "true"
        if os.getenv("RESILIENCE_LOG_LEVEL"):
            overrides["log_level"] = os.getenv("RESILIENCE_LOG_LEVEL")

        return overrides

    def apply_environment_overrides(self):
        """Apply environment variable overrides to configuration."""
        overrides = self.get_environment_overrides()
        if overrides:
            self.update_config(overrides)

    def get_feature_flags(self) -> Dict[str, bool]:
        """Get feature flags for resilience features."""
        config = self._config
        return {
            "circuit_breaker": config.enabled and config.circuit_breaker.enabled,
            "retry_mechanisms": config.enabled and config.retry.enabled,
            "database_resilience": config.enabled and config.database.enabled,
            "network_resilience": config.enabled and config.retry.enabled and config.network.enabled,
            "fallback_content": config.enabled and config.fallback.enabled,
            "graceful_degradation": config.enabled and config.degradation.enabled,
            "recovery_procedures": config.enabled and config.recovery.enabled,
            "health_monitoring": config.enabled and config.health_monitoring.enabled,
            "metrics": config.metrics_enabled,
            "alerts": config.alert_enabled
        }


# Global configuration manager instance
config_manager = ResilienceConfigManager()


def get_resilience_config() -> ResilienceConfig:
    """Get current resilience configuration."""
    return config_manager.get_config()


def update_resilience_config(updates: Dict[str, Any]):
    """Update resilience configuration."""
    config_manager.update_config(updates)


def save_resilience_config():
    """Save current resilience configuration."""
    config_manager.save_config()


def validate_resilience_config() -> List[str]:
    """Validate resilience configuration."""
    return config_manager.validate_config()


def get_resilience_feature_flags() -> Dict[str, bool]:
    """Get resilience feature flags."""
    return config_manager.get_feature_flags()