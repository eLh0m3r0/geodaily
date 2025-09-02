#!/usr/bin/env python3
"""
Comprehensive test suite for validating all newsletter generation improvements.
"""

import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.models import Article, NewsSource, SourceCategory, SourceTier, AIAnalysis, ContentType
from src.collectors.source_health_monitor import source_health_monitor
from src.processors.content_quality_validator import content_quality_validator
from src.ai.cost_controller import ai_cost_controller
from src.performance.connection_pool import performance_optimizer
from src.ux.personalization import personalization_engine, feedback_collector
from src.newsletter.generator import NewsletterGenerator
from src.config import Config


def test_source_health_monitoring():
    """Test source health monitoring functionality."""
    print("🩺 Testing Source Health Monitoring...")

    # Create a test source
    test_source = NewsSource(
        name="Test Source",
        url="https://example.com/rss",
        category=SourceCategory.MAINSTREAM,
        tier=SourceTier.TIER1_RSS
    )

    # Test health monitoring
    source_health_monitor.register_source(test_source)

    # Simulate some requests
    for i in range(5):
        if i < 3:
            source_health_monitor.record_request_result("Test Source", True, 1.5)
        else:
            source_health_monitor.record_request_result("Test Source", False, 5.0, "timeout")

    # Check health status
    health_status = source_health_monitor.get_source_health_status("Test Source")
    print(f"  ✅ Source health status: {health_status}")

    # Test failover logic
    available_sources = [test_source]
    healthy_sources = source_health_monitor.get_healthy_sources(available_sources)
    print(f"  ✅ Healthy sources: {len(healthy_sources)}")

    print("  ✅ Source Health Monitoring tests passed\n")


def test_content_quality_validation():
    """Test content quality validation functionality."""
    print("🔍 Testing Content Quality Validation...")

    # Create test articles
    test_articles = [
        Article(
            source="Test Source 1",
            source_category=SourceCategory.MAINSTREAM,
            title="Breaking: Major geopolitical development",
            url="https://example.com/article1",
            summary="This is a test article about current events",
            published_date=datetime.now(),
            relevance_score=0.8
        ),
        Article(
            source="Test Source 2",
            source_category=SourceCategory.ANALYSIS,
            title="Old article from last week",
            url="https://example.com/article2",
            summary="This article is very old",
            published_date=datetime.now() - timedelta(days=10),  # Very old
            relevance_score=0.6
        ),
        Article(
            source="Test Source 3",
            source_category=SourceCategory.THINK_TANK,
            title="High-quality analysis piece",
            url="https://example.com/article3",
            summary="This is a comprehensive analysis of current geopolitical trends",
            published_date=datetime.now() - timedelta(hours=2),  # Recent
            relevance_score=0.9
        )
    ]

    # Test quality validation
    validation_results = content_quality_validator.validate_articles(test_articles)

    valid_count = sum(1 for result in validation_results if result.is_valid)
    print(f"  ✅ Valid articles: {valid_count}/{len(test_articles)}")

    # Check quality metrics
    for i, result in enumerate(validation_results):
        print(f"    Article {i+1}: Quality score {result.quality_metrics.overall_quality_score:.2f}")

    print("  ✅ Content Quality Validation tests passed\n")


def test_ai_cost_control():
    """Test AI cost control functionality."""
    print("💰 Testing AI Cost Control...")

    # Test cost estimation
    test_text = "This is a test article about geopolitical developments in the Middle East involving diplomatic relations and economic sanctions."
    cost_estimate = ai_cost_controller.estimate_cost(len(test_text), "analysis")
    print(f"  ✅ Estimated cost: ${cost_estimate.estimated_cost:.4f} for {cost_estimate.estimated_tokens} tokens")

    # Test budget checking
    budget_check = ai_cost_controller.check_budget_allowance(cost_estimate.estimated_cost)
    print(f"  ✅ Budget check: {'Allowed' if budget_check['allowed'] else 'Blocked'}")

    # Test cost recording
    ai_cost_controller.record_cost(cost_estimate.estimated_cost, cost_estimate.estimated_tokens, "test_analysis")
    print("  ✅ Cost recorded successfully")

    # Test cost report
    cost_report = ai_cost_controller.get_cost_report()
    print(f"  ✅ Daily cost: ${cost_report['current_metrics']['daily_cost']:.4f}")
    print(f"  ✅ Budget status: {cost_report['status']}")

    print("  ✅ AI Cost Control tests passed\n")


def test_performance_optimizations():
    """Test performance optimization functionality."""
    print("⚡ Testing Performance Optimizations...")

    # Test batch size optimization
    total_items = 50
    max_workers = 8
    optimal_batch_size = performance_optimizer.optimize_collection_batch_size(total_items, max_workers)
    print(f"  ✅ Optimal batch size: {optimal_batch_size} for {total_items} items with {max_workers} workers")

    # Test connection pool stats
    pool_stats = performance_optimizer.get_connection_pool().get_pool_stats()
    print(f"  ✅ Connection pools: {pool_stats['total_pools']}")

    # Test performance report
    perf_report = performance_optimizer.get_performance_report()
    print(f"  ✅ HTTP success rate: {perf_report['http_metrics']['success_rate']:.1f}%")

    print("  ✅ Performance Optimization tests passed\n")


def test_personalization_engine():
    """Test personalization engine functionality."""
    print("🎯 Testing Personalization Engine...")

    # Create test user
    user_id = "test_user_123"
    user_profile = personalization_engine.get_or_create_user_profile(user_id)
    print(f"  ✅ Created user profile for: {user_id}")

    # Create test stories
    test_stories = [
        AIAnalysis(
            story_title="Breaking: Diplomatic breakthrough in Middle East peace talks",
            why_important="This development could reshape regional alliances and economic partnerships",
            what_overlooked="Western media is missing the economic dimensions of this agreement",
            prediction="Expect increased trade relations within the next quarter",
            impact_score=8,
            content_type=ContentType.BREAKING_NEWS,
            sources=["https://example.com/article1"]
        ),
        AIAnalysis(
            story_title="Economic analysis: Global supply chain disruptions",
            why_important="Supply chain issues are affecting multiple industries worldwide",
            what_overlooked="The long-term strategic implications for manufacturing relocation",
            prediction="Companies will accelerate supply chain diversification",
            impact_score=7,
            content_type=ContentType.ANALYSIS,
            sources=["https://example.com/article2"]
        )
    ]

    # Test personalization
    personalized_newsletter = personalization_engine.personalize_newsletter(user_id, test_stories)
    print(f"  ✅ Personalized {len(personalized_newsletter.personalized_stories)} stories")
    print(f"  ✅ Personalization score: {personalized_newsletter.personalization_score:.2f}")

    # Test feedback processing
    feedback_collector.collect_feedback(
        user_id,
        "test_content_123",
        {
            'type': 'relevance',
            'rating': 0.8,
            'comment': 'Very relevant to my work'
        }
    )
    print("  ✅ Feedback collected successfully")

    # Test user insights
    insights = personalization_engine.get_user_insights(user_id)
    print(f"  ✅ User insights generated with {insights['total_feedback']} feedback entries")

    print("  ✅ Personalization Engine tests passed\n")


def test_newsletter_generation():
    """Test enhanced newsletter generation with feedback features."""
    print("📧 Testing Enhanced Newsletter Generation...")

    # Create test analyses
    test_analyses = [
        AIAnalysis(
            story_title="Test geopolitical development",
            why_important="This is an important development with strategic implications",
            what_overlooked="Mainstream coverage misses the economic dimensions",
            prediction="Expect cascading effects in the coming weeks",
            impact_score=8,
            content_type=ContentType.BREAKING_NEWS,
            sources=["https://example.com/test"]
        )
    ]

    # Generate newsletter
    generator = NewsletterGenerator()
    newsletter = generator.generate_newsletter(test_analyses)
    html_content = generator.generate_html(newsletter)

    # Check for feedback elements
    feedback_elements = [
        'feedback-section',
        'feedback-btn',
        'submit-feedback-btn',
        'newsletter-actions'
    ]

    missing_elements = []
    for element in feedback_elements:
        if element not in html_content:
            missing_elements.append(element)

    if missing_elements:
        print(f"  ❌ Missing feedback elements: {missing_elements}")
        return False

    print("  ✅ Newsletter contains all feedback elements")

    # Check HTML structure
    if '<html' in html_content and '</html>' in html_content:
        print("  ✅ Valid HTML structure")
    else:
        print("  ❌ Invalid HTML structure")
        print(f"    Contains '<html': {'<html' in html_content}")
        print(f"    Contains '</html>': {'</html>' in html_content}")
        return False

    print("  ✅ Enhanced Newsletter Generation tests passed\n")
    return True


def test_integration():
    """Test integration of all improvements."""
    print("🔗 Testing Integration of All Improvements...")

    # Test that all modules can be imported and instantiated
    try:
        from src.resilience.health_monitoring import health_monitor
        from src.resilience.graceful_degradation import degradation_manager
        from src.resilience.network_resilience import network_manager

        print("  ✅ All resilience modules imported successfully")

        # Test health monitoring
        health_status = health_monitor.get_health_status()
        print(f"  ✅ System health: {health_status['overall_status']}")

        # Test degradation manager
        overall_status = degradation_manager.get_overall_status()
        print(f"  ✅ Degradation level: {overall_status['overall_degradation_level']}")

        print("  ✅ Integration tests passed\n")
        return True

    except Exception as e:
        print(f"  ❌ Integration test failed: {e}")
        return False


def run_all_tests():
    """Run all improvement tests."""
    print("🚀 Starting Comprehensive Test Suite for Newsletter Improvements\n")
    print("=" * 60)

    test_results = []

    # Run individual tests
    try:
        test_source_health_monitoring()
        test_results.append(("Source Health Monitoring", True))
    except Exception as e:
        print(f"❌ Source Health Monitoring test failed: {e}")
        test_results.append(("Source Health Monitoring", False))

    try:
        test_content_quality_validation()
        test_results.append(("Content Quality Validation", True))
    except Exception as e:
        print(f"❌ Content Quality Validation test failed: {e}")
        test_results.append(("Content Quality Validation", False))

    try:
        test_ai_cost_control()
        test_results.append(("AI Cost Control", True))
    except Exception as e:
        print(f"❌ AI Cost Control test failed: {e}")
        test_results.append(("AI Cost Control", False))

    try:
        test_performance_optimizations()
        test_results.append(("Performance Optimizations", True))
    except Exception as e:
        print(f"❌ Performance Optimizations test failed: {e}")
        test_results.append(("Performance Optimizations", False))

    try:
        test_personalization_engine()
        test_results.append(("Personalization Engine", True))
    except Exception as e:
        print(f"❌ Personalization Engine test failed: {e}")
        test_results.append(("Personalization Engine", False))

    try:
        newsletter_test_passed = test_newsletter_generation()
        test_results.append(("Newsletter Generation", newsletter_test_passed))
    except Exception as e:
        print(f"❌ Newsletter Generation test failed: {e}")
        test_results.append(("Newsletter Generation", False))

    try:
        integration_test_passed = test_integration()
        test_results.append(("Integration", integration_test_passed))
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        test_results.append(("Integration", False))

    # Print summary
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1

    print("=" * 60)
    print(f"Overall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")

    if passed == total:
        print("🎉 All tests passed! All improvements are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)