"""
Dashboard module for comprehensive monitoring and visualization.
"""

# Conditional imports to avoid relative import issues in standalone execution
try:
    from .debug_dashboard import DebugDashboard
    from .unified_dashboard import UnifiedDashboard
    __all__ = ['DebugDashboard', 'UnifiedDashboard']
except ImportError:
    # Skip imports when running standalone
    __all__ = []