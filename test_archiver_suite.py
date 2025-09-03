#!/usr/bin/env python3
"""
Comprehensive test runner for AI archiver and dashboard functionality.
"""

import sys
import pytest
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Run the complete archiver test suite."""
    print("🧪 Running GeoPolitical Daily Archiver Test Suite")
    print("=" * 60)
    
    # Test files to run
    test_files = [
        "tests/test_archiver.py",
        "tests/test_archive_utilities.py"
    ]
    
    # Check that test files exist
    missing_files = []
    for test_file in test_files:
        if not Path(test_file).exists():
            missing_files.append(test_file)
    
    if missing_files:
        print(f"❌ Missing test files: {missing_files}")
        return 1
    
    # Run tests with verbose output
    args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--strict-markers",  # Strict marker checking
        "-x",  # Stop on first failure
    ]
    
    # Add test files
    args.extend(test_files)
    
    print(f"📋 Running tests: {', '.join(test_files)}")
    print()
    
    # Run pytest
    exit_code = pytest.main(args)
    
    print()
    print("=" * 60)
    
    if exit_code == 0:
        print("✅ All archiver tests passed successfully!")
        print()
        print("📊 Test Coverage Summary:")
        print("   • AI Data Archiver: Core functionality, configuration, statistics")
        print("   • Debug Dashboard: HTML generation, visualization, data loading")
        print("   • Archive Cleanup: Retention policies, dry-run mode, file management")
        print("   • Dashboard Generator: CLI interface, batch generation, index creation")
        print("   • Integration Tests: End-to-end workflows, realistic data scenarios")
        print()
        print("🚀 The archiver system is ready for production use!")
    else:
        print(f"❌ Tests failed with exit code: {exit_code}")
        print()
        print("💡 To debug test failures:")
        print("   • Run individual test files: python -m pytest tests/test_archiver.py -v")
        print("   • Run specific test: python -m pytest tests/test_archiver.py::TestAIDataArchiver::test_start_new_run -v")
        print("   • Enable more detailed output: python -m pytest tests/ -vvv --tb=long")
    
    return exit_code

if __name__ == "__main__":
    exit(main())