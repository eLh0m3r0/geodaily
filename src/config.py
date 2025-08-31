"""
Configuration management for the Geopolitical Daily newsletter.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    SUBSTACK_API_KEY = os.getenv("SUBSTACK_API_KEY")
    SUBSTACK_PUBLICATION_ID = os.getenv("SUBSTACK_PUBLICATION_ID")
    
    # Newsletter Configuration
    NEWSLETTER_TITLE = os.getenv("NEWSLETTER_TITLE", "Geopolitical Daily")
    NEWSLETTER_AUTHOR = os.getenv("NEWSLETTER_AUTHOR", "Geopolitical Daily Team")
    NEWSLETTER_FROM_EMAIL = os.getenv("NEWSLETTER_FROM_EMAIL")
    
    # AI Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")
    AI_MODEL = os.getenv("AI_MODEL", "claude-3-haiku-20240307")  # Use cheaper model by default
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2000"))  # Reduce tokens to control cost
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

        return missing
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.TEMPLATES_DIR.mkdir(exist_ok=True)
