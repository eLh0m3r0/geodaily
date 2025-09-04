#!/usr/bin/env python3
"""
Generate unified dashboard for GeoPolitical Daily.
Replaces multiple dashboard systems with single streamlined version.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.dashboard.unified_dashboard import UnifiedDashboard
from logger import get_logger

logger = get_logger(__name__)


def main():
    """Generate unified dashboard."""
    try:
        dashboard = UnifiedDashboard()
        dashboard_path = dashboard.generate_dashboard()
        print(f"✅ Unified dashboard generated: {dashboard_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate unified dashboard: {e}")
        print(f"❌ Dashboard generation failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)