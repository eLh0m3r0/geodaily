"""
Geopolitical Daily Newsletter - Automated geopolitical news aggregation and analysis.

This package provides automated collection, analysis, and publishing of geopolitical news
from multiple sources using AI-powered analysis.
"""

__version__ = "1.0.0"
__author__ = "Geopolitical Daily Team"

# Core imports for easy access
from .models import Article, NewsSource, ArticleCluster, AIAnalysis, ProcessingStats
from .config import Config
from .logger import setup_logger, get_logger

__all__ = [
    'Article',
    'NewsSource', 
    'ArticleCluster',
    'AIAnalysis',
    'ProcessingStats',
    'Config',
    'setup_logger',
    'get_logger'
]