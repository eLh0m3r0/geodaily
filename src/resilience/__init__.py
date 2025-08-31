"""
Resilience module for production reliability.

This module provides comprehensive error resilience and fallback mechanisms
for the Geopolitical Daily newsletter system, including:

- Circuit breaker pattern for API calls
- Exponential backoff retry mechanisms with jitter
- Database connection pooling and resilience
- Network failure handling with multiple strategies
- Fallback content generation
- Graceful degradation for partial failures
- Recovery procedures for transient failures
- Health monitoring and proactive error detection
- Comprehensive configuration management
- Testing framework for resilience mechanisms

The system maintains high availability and provides meaningful content
even during partial failures.
"""

from .circuit_breaker import (
    CircuitBreaker, CircuitBreakerOpen, CircuitBreakerRegistry,
    get_circuit_breaker, circuit_registry
)

from .retry_mechanisms import (
    RetryConfig, RetryError, retry_api_call, retry_network_operation,
    retry_database_operation, retry_manager
)

from .database_resilience import (
    ConnectionPool, ConnectionPoolTimeout, ConnectionPoolError,
    ResilientDatabase, get_resilient_database
)

from .network_resilience import (
    NetworkEndpoint, NetworkResilienceManager, RSSResilienceManager,
    WebScrapingResilienceManager, network_manager, rss_manager, scraping_manager
)

from .fallback_content import (
    FallbackContent, FallbackContentGenerator, fallback_generator
)

from .graceful_degradation import (
    DegradationLevel, ComponentStatus, ComponentHealth,
    DegradationRule, GracefulDegradationManager,
    create_database_degradation_rules, create_ai_degradation_rules,
    create_network_degradation_rules, degradation_manager
)

from .recovery_procedures import (
    RecoveryStrategy, RecoveryStatus, RecoveryAttempt,
    RecoveryProcedure, RecoveryManager,
    create_database_recovery_procedures, create_network_recovery_procedures,
    create_ai_recovery_procedures, recovery_manager
)

from .health_monitoring import (
    HealthStatus, HealthCheck, HealthCheckResult,
    HealthMonitor, create_database_health_checks,
    create_network_health_checks, create_system_health_checks,
    health_monitor
)

from .config import (
    CircuitBreakerConfig, RetryConfig, DatabaseConfig, NetworkConfig,
    FallbackConfig, DegradationConfig, RecoveryConfig, HealthMonitoringConfig,
    ResilienceConfig, ResilienceConfigManager,
    get_resilience_config, update_resilience_config, save_resilience_config,
    validate_resilience_config, get_resilience_feature_flags, config_manager
)

from .testing_framework import (
    ResilienceTestResult, ResilienceTestSuite, ResilienceTestRunner,
    test_component, create_circuit_breaker_tests, create_retry_tests,
    create_network_tests, create_fallback_tests, create_integration_tests,
    run_resilience_tests, test_runner
)

__all__ = [
    # Circuit Breaker
    'CircuitBreaker', 'CircuitBreakerOpen', 'CircuitBreakerRegistry',
    'get_circuit_breaker', 'circuit_registry',

    # Retry Mechanisms
    'RetryConfig', 'RetryError', 'retry_api_call', 'retry_network_operation',
    'retry_database_operation', 'retry_manager',

    # Database Resilience
    'ConnectionPool', 'ConnectionPoolTimeout', 'ConnectionPoolError',
    'ResilientDatabase', 'get_resilient_database',

    # Network Resilience
    'NetworkEndpoint', 'NetworkResilienceManager', 'RSSResilienceManager',
    'WebScrapingResilienceManager', 'network_manager', 'rss_manager', 'scraping_manager',

    # Fallback Content
    'FallbackContent', 'FallbackContentGenerator', 'fallback_generator',

    # Graceful Degradation
    'DegradationLevel', 'ComponentStatus', 'ComponentHealth',
    'DegradationRule', 'GracefulDegradationManager',
    'create_database_degradation_rules', 'create_ai_degradation_rules',
    'create_network_degradation_rules', 'degradation_manager',

    # Recovery Procedures
    'RecoveryStrategy', 'RecoveryStatus', 'RecoveryAttempt',
    'RecoveryProcedure', 'RecoveryManager',
    'create_database_recovery_procedures', 'create_network_recovery_procedures',
    'create_ai_recovery_procedures', 'recovery_manager',

    # Health Monitoring
    'HealthStatus', 'HealthCheck', 'HealthCheckResult',
    'HealthMonitor', 'create_database_health_checks',
    'create_network_health_checks', 'create_system_health_checks',
    'health_monitor',

    # Configuration
    'CircuitBreakerConfig', 'RetryConfig', 'DatabaseConfig', 'NetworkConfig',
    'FallbackConfig', 'DegradationConfig', 'RecoveryConfig', 'HealthMonitoringConfig',
    'ResilienceConfig', 'ResilienceConfigManager',
    'get_resilience_config', 'update_resilience_config', 'save_resilience_config',
    'validate_resilience_config', 'get_resilience_feature_flags', 'config_manager',

    # Testing Framework
    'ResilienceTestResult', 'ResilienceTestSuite', 'ResilienceTestRunner',
    'test_component', 'create_circuit_breaker_tests', 'create_retry_tests',
    'create_network_tests', 'create_fallback_tests', 'create_integration_tests',
    'run_resilience_tests', 'test_runner'
]

__version__ = "1.0.0"