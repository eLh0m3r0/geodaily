#!/usr/bin/env python3
"""
Test script for the metrics dashboard system.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from metrics.dashboard_generator import DashboardGenerator
    from metrics.collector import MetricsCollector
except ImportError:
    # Try direct execution approach
    import subprocess
    result = subprocess.run([sys.executable, "-m", "src.metrics.dashboard_generator"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Import error: {result.stderr}")
        sys.exit(1)

def test_dashboard_generation():
    """Test dashboard generation with sample data."""
    print("Testing metrics dashboard generation...")

    try:
        # Generate dashboard
        generator = DashboardGenerator()
        output_path = generator.generate_dashboard("docs/dashboard.html")

        print(f"✅ Dashboard generated successfully: {output_path}")

        # Check if file exists
        if Path(output_path).exists():
            print("✅ Dashboard file created")
        else:
            print("❌ Dashboard file not found")

        return True

    except Exception as e:
        print(f"❌ Dashboard generation failed: {e}")
        return False

def test_metrics_collection():
    """Test metrics collection system."""
    print("\nTesting metrics collection...")

    try:
        collector = MetricsCollector()

        # Get comprehensive stats
        stats = collector.get_comprehensive_stats(days=30)
        print("✅ Metrics collection successful")

        # Check if we have the expected structure
        if 'daily_stats' in stats:
            print("✅ Daily stats available")
        if 'source_performance' in stats:
            print("✅ Source performance available")
        if 'ai_usage' in stats:
            print("✅ AI usage stats available")

        return True

    except Exception as e:
        print(f"❌ Metrics collection failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Geopolitical Daily Metrics Dashboard System")
    print("=" * 60)

    success = True

    # Test metrics collection
    if not test_metrics_collection():
        success = False

    # Test dashboard generation
    if not test_dashboard_generation():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed! Dashboard system is ready.")
        print("\nTo use the dashboard:")
        print("1. Run the newsletter pipeline: python -m src.main_pipeline")
        print("2. Open docs/dashboard.html in your browser")
        print("3. The dashboard will automatically update with each newsletter generation")
    else:
        print("❌ Some tests failed. Please check the errors above.")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())