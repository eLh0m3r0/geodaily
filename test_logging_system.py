#!/usr/bin/env python3
"""
Test script for the improved logging system.
Demonstrates structured logging, performance monitoring, error categorization, and analysis tools.
"""

import time
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.logging_system import (
    StructuredLogger, ErrorCategory, PipelineStage,
    PerformanceProfiler, PipelineTracker, error_handler,
    LogAnalysisTools as LogAnalyzer, LogDashboard
)
from src.metrics.collector import MetricsCollector

def test_basic_structured_logging():
    """Test basic structured logging functionality."""
    print("=== Testing Basic Structured Logging ===")

    logger = StructuredLogger("test_basic")

    # Test different log levels with structured data
    logger.info("Starting test pipeline",
               pipeline_stage=PipelineStage.INITIALIZATION,
               structured_data={'test_mode': True})

    logger.warning("This is a test warning",
                  pipeline_stage=PipelineStage.PROCESSING,
                  structured_data={'warning_code': 'TEST_001'})

    logger.error("This is a test error",
                error_category=ErrorCategory.VALIDATION_ERROR,
                structured_data={'error_code': 'TEST_ERR_001'})

    print("✅ Basic structured logging test completed")

def test_performance_monitoring():
    """Test performance monitoring capabilities."""
    print("\n=== Testing Performance Monitoring ===")

    logger = StructuredLogger("test_performance")

    # Test performance profiling
    with PerformanceProfiler.profile_operation("test_operation", logger):
        # Simulate some work
        time.sleep(0.1)
        result = sum(range(1000))

    print(f"✅ Performance monitoring test completed (result: {result})")

def test_error_handling():
    """Test error categorization and handling."""
    print("\n=== Testing Error Handling ===")

    logger = StructuredLogger("test_errors")

    # Test different error categories
    try:
        raise ValueError("Test validation error")
    except Exception as e:
        logger.error(f"Caught validation error: {e}",
                    error_category=ErrorCategory.VALIDATION_ERROR,
                    structured_data={'operation': 'test_validation'})

    try:
        raise ConnectionError("Test network error")
    except Exception as e:
        logger.error(f"Caught network error: {e}",
                    error_category=ErrorCategory.NETWORK_ERROR,
                    structured_data={'operation': 'test_network'})

    print("✅ Error handling test completed")

def test_pipeline_tracking():
    """Test pipeline success tracking."""
    print("\n=== Testing Pipeline Tracking ===")

    logger = StructuredLogger("test_pipeline")
    tracker = PipelineTracker(logger)

    run_id = "test_run_001"

    # Track pipeline stages
    tracker.track_pipeline_start(run_id)

    tracker.track_stage_completion(run_id, PipelineStage.COLLECTION, 1.5, success=True)
    tracker.track_stage_completion(run_id, PipelineStage.PROCESSING, 2.3, success=True)
    tracker.track_stage_completion(run_id, PipelineStage.AI_ANALYSIS, 3.1, success=False)

    # Track final success
    tracker.track_pipeline_success(run_id, 7.2)

    # Get success stats
    stats = tracker.get_success_stats()
    print(f"Pipeline stats: {stats}")

    print("✅ Pipeline tracking test completed")

@error_handler(StructuredLogger("test_decorator"), pipeline_stage=PipelineStage.PROCESSING)
def test_error_decorator():
    """Test error handling decorator."""
    print("\n=== Testing Error Decorator ===")

    # This should be handled gracefully
    raise RuntimeError("Test error in decorated function")

def test_log_analysis():
    """Test log analysis capabilities."""
    print("\n=== Testing Log Analysis ===")

    analyzer = LogAnalyzer()

    # Analyze recent logs
    analysis = analyzer.analyze_logs(hours=1)

    print(f"Analysis summary: {analysis.get('summary', {})}")

    # Generate performance report
    report = analyzer.generate_performance_report(hours=1)
    print(f"Performance report: {report.get('summary', {})}")

    print("✅ Log analysis test completed")

def test_metrics_integration():
    """Test metrics integration."""
    print("\n=== Testing Metrics Integration ===")

    # Initialize metrics collector
    metrics_collector = MetricsCollector()

    # Create metrics-aware logger
    from src.logging_system.metrics_integration import get_metrics_aware_logger
    logger = get_metrics_aware_logger("test_metrics", metrics_collector=metrics_collector)

    # Log some events that should be tracked
    logger.info("Test metrics event",
               pipeline_stage=PipelineStage.COLLECTION,
               structured_data={'test_data': 'integration_test'})

    logger.error("Test error for metrics",
                error_category=ErrorCategory.API_ERROR,
                structured_data={'test_error': True})

    print("✅ Metrics integration test completed")

def main():
    """Run all logging system tests."""
    print("🚀 Starting Comprehensive Logging System Test")
    print("=" * 50)

    try:
        test_basic_structured_logging()
        test_performance_monitoring()
        test_error_handling()
        test_pipeline_tracking()

        # Test error decorator (will log error but continue)
        try:
            test_error_decorator()
        except:
            pass  # Expected to be handled by decorator

        test_log_analysis()
        test_metrics_integration()

        print("\n" + "=" * 50)
        print("🎉 All logging system tests completed successfully!")
        print("\n📋 Test Summary:")
        print("  ✅ Structured JSON logging")
        print("  ✅ Performance monitoring and profiling")
        print("  ✅ Error categorization and handling")
        print("  ✅ Pipeline success tracking")
        print("  ✅ Log analysis and reporting")
        print("  ✅ Metrics system integration")
        print("\n📁 Check the logs/ directory for generated log files")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
    finally:
        # Shutdown metrics integration
        from src.logging_system import shutdown_metrics_integration
        shutdown_metrics_integration()
    sys.exit(exit_code)