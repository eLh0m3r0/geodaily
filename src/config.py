"""
Configuration management for the Geopolitical Daily newsletter.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv()
else:
    print("Info: .env file not found, using environment variables only")

class Config:
    """Configuration class for the application."""
    
    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent
    SOURCES_FILE = PROJECT_ROOT / "sources.json"
    TEMPLATES_DIR = PROJECT_ROOT / "templates"
    LOGS_DIR = PROJECT_ROOT / "logs"
    
    # API Configuration
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Newsletter Configuration
    NEWSLETTER_TITLE = os.getenv("NEWSLETTER_TITLE", "Geopolitical Daily")
    NEWSLETTER_AUTHOR = os.getenv("NEWSLETTER_AUTHOR", "Geopolitical Daily Team")
    NEWSLETTER_FROM_EMAIL = os.getenv("NEWSLETTER_FROM_EMAIL")

    # Site Configuration
    SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://elh0m3r0.github.io/geodaily")

    # AI Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")
    AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-20250514")  # Use Sonnet 4 for better quality
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "8000"))  # Higher limit for Sonnet 4
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
    AI_MAX_COST_PER_DAY = float(os.getenv("AI_MAX_COST_PER_DAY", "2.0"))  # $2/day limit
    
    # Scraping Configuration
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))
    USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; GeopoliticalDaily/1.0)")
    
    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Notification Configuration
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    
    # Development/Testing
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

    # Cleanup Configuration
    CLEANUP_ENABLED = os.getenv("CLEANUP_ENABLED", "true").lower() == "true"
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    NEWSLETTER_RETENTION_DAYS = int(os.getenv("NEWSLETTER_RETENTION_DAYS", "90"))
    OUTPUT_RETENTION_DAYS = int(os.getenv("OUTPUT_RETENTION_DAYS", "7"))
    METRICS_RETENTION_DAYS = int(os.getenv("METRICS_RETENTION_DAYS", "180"))
    CLEANUP_DRY_RUN = os.getenv("CLEANUP_DRY_RUN", "false").lower() == "true"

    # Cleanup Directories
    OUTPUT_DIR = PROJECT_ROOT / "output"
    NEWSLETTERS_DIR = PROJECT_ROOT / "docs" / "newsletters"
    METRICS_DB_PATH = PROJECT_ROOT / "data" / "metrics.db"
    
    @classmethod
    def load_sources(cls) -> Dict[str, List[Dict[str, Any]]]:
        """Load sources configuration from sources.json."""
        try:
            with open(cls.SOURCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Sources file not found: {cls.SOURCES_FILE}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in sources file: {e}")
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate configuration and return list of missing required settings."""
        missing = []
        warnings = []

        # Skip API key validation in dry run mode
        if not cls.DRY_RUN:
            # Check required API keys based on provider
            if cls.AI_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
                missing.append("ANTHROPIC_API_KEY")
            elif cls.AI_PROVIDER == "gemini" and not cls.GEMINI_API_KEY:
                missing.append("GEMINI_API_KEY")

        # Check if sources file exists
        if not cls.SOURCES_FILE.exists():
            missing.append(f"Sources file: {cls.SOURCES_FILE}")

        # Validate AI Archive settings
        if cls.AI_ARCHIVE_ENABLED:
            if cls.AI_ARCHIVE_RETENTION_DAYS < 1:
                warnings.append("AI_ARCHIVE_RETENTION_DAYS should be at least 1 day")
            if cls.AI_ARCHIVE_RETENTION_DAYS > 365:
                warnings.append("AI_ARCHIVE_RETENTION_DAYS is very high (>365 days)")
            
            if cls.AI_ARCHIVE_MAX_SIZE_MB < 10:
                warnings.append("AI_ARCHIVE_MAX_SIZE_MB is very low (<10MB)")
            if cls.AI_ARCHIVE_MAX_SIZE_MB > 10000:
                warnings.append("AI_ARCHIVE_MAX_SIZE_MB is very high (>10GB)")
            
            # Check if archive path is valid
            try:
                Path(cls.AI_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                missing.append(f"Cannot create AI_ARCHIVE_PATH: {e}")

        # Validate Dashboard settings
        if cls.DASHBOARD_AUTO_GENERATE:
            try:
                Path(cls.DASHBOARD_OUTPUT_PATH).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                missing.append(f"Cannot create DASHBOARD_OUTPUT_PATH: {e}")

        # Print warnings if any
        if warnings:
            print("⚠️  Configuration warnings:")
            for warning in warnings:
                print(f"   • {warning}")

        return missing
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.TEMPLATES_DIR.mkdir(exist_ok=True)
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        cls.NEWSLETTERS_DIR.mkdir(exist_ok=True, parents=True)
        cls.METRICS_DB_PATH.parent.mkdir(exist_ok=True, parents=True)
        
        # Create archive and dashboard directories if enabled
        if cls.AI_ARCHIVE_ENABLED:
            Path(cls.AI_ARCHIVE_PATH).mkdir(exist_ok=True, parents=True)
        
        if cls.DASHBOARD_AUTO_GENERATE:
            Path(cls.DASHBOARD_OUTPUT_PATH).mkdir(exist_ok=True, parents=True)
    
    # AI Archive Configuration
    AI_ARCHIVE_ENABLED = os.getenv("AI_ARCHIVE_ENABLED", "true").lower() == "true"
    AI_ARCHIVE_PATH = os.getenv("AI_ARCHIVE_PATH", "ai_archive")
    AI_ARCHIVE_RETENTION_DAYS = int(os.getenv("AI_ARCHIVE_RETENTION_DAYS", "30"))
    AI_ARCHIVE_MAX_SIZE_MB = int(os.getenv("AI_ARCHIVE_MAX_SIZE_MB", "500"))
    AI_ARCHIVE_COMPRESS_OLD = os.getenv("AI_ARCHIVE_COMPRESS_OLD", "false").lower() == "true"
    
    # Dashboard Configuration  
    DASHBOARD_OUTPUT_PATH = os.getenv("DASHBOARD_OUTPUT_PATH", "dashboards")
    DASHBOARD_AUTO_GENERATE = os.getenv("DASHBOARD_AUTO_GENERATE", "true").lower() == "true"
    DEBUG_DASHBOARD_ENABLED = os.getenv("DEBUG_DASHBOARD", "true").lower() == "true"
