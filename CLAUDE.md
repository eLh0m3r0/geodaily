# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Create virtual environment (Python 3.11+ required)
python -m venv geodaily-env
source geodaily-env/bin/activate  # On Windows: geodaily-env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Testing Commands
```bash
# Run full test suite
python -m pytest tests/ -v

# Test individual components
python test_simple_collection.py      # Test data collection
python test_deduplication.py          # Test processing and dedup rate
python test_newsletter.py             # Test newsletter generation
python test_complete_pipeline.py      # Test end-to-end pipeline

# Test specific modules
python tests/test_environment.py      # Test environment setup
python tests/test_collectors.py       # Test collection system
python tests/test_rss_collector.py    # Test RSS feed collection
python tests/test_web_scraper.py      # Test web scraping
python tests/test_processors.py       # Test processing pipeline
python tests/test_ai_analyzer.py      # Test AI analysis
python tests/test_resilience.py       # Test resilience framework
python tests/test_metrics.py          # Test metrics collection
python tests/test_notifications.py    # Test notification system

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Main Pipeline Commands
```bash
# Run complete pipeline (uses DRY_RUN=true by default)
python src/main_pipeline.py

# Run with API calls (requires API keys)
DRY_RUN=false python src/main_pipeline.py

# Test individual components
python src/test_simple_collection.py   # Test collection from all 26 sources
python src/test_complete_pipeline.py   # End-to-end test

# Run via GitHub Actions (manually trigger)
# Go to Actions tab and run "Daily Geopolitical Newsletter" workflow
```

### Utility Commands
```bash
# Generate dashboard
python src/metrics/dashboard_generator.py

# Clean old data (keeps 30 days by default)
python src/cleanup.py

# Generate sitemap for GitHub Pages
python src/sitemap_generator.py
```

## Architecture Overview

### Pipeline Flow
1. **Collection Layer** (`src/collectors/`): Collects from 26 sources (20 RSS + 6 web scraping)
2. **Processing Layer** (`src/processors/`): Deduplicates, clusters, and scores articles
3. **AI Analysis Layer** (`src/ai/`): Claude API with cost controls and fallback mechanisms
4. **Newsletter Generation** (`src/newsletter/`): Professional HTML newsletter creation
5. **Publishing Layer** (`src/publishers/`): GitHub Pages deployment and email notifications
6. **Metrics & Monitoring**: Performance tracking, cost monitoring, health checks

### Key Components

#### Data Collection
- **RSS Collector** (`src/collectors/rss_collector.py`): Handles 20 tier1 RSS feeds
- **Web Scraper** (`src/collectors/web_scraper.py`): Scrapes 6 tier2 sources
- **Main Collector** (`src/collectors/main_collector.py`): Parallel collection orchestration
- **Connection Pooling**: Optimized HTTP connections for performance

#### Data Processing
- **Deduplicator** (`src/processors/deduplicator.py`): Title similarity-based deduplication
- **Clusterer** (`src/processors/clusterer.py`): Groups related articles
- **Content Validator** (`src/processors/content_quality_validator.py`): Quality assessment
- **Main Processor** (`src/processors/main_processor.py`): Processing pipeline coordinator

#### AI Integration
- **Claude Analyzer** (`src/ai/claude_analyzer.py`): Anthropic Claude API integration
- **Cost Controller** (`src/ai/cost_controller.py`): Budget tracking and spending limits
- Mock analysis fallback for testing and API failures
- Configurable token limits (default: 8000 for production)

#### Resilience Framework
- **Circuit Breakers** (`src/resilience/circuit_breaker.py`): Prevent cascading failures
- **Retry Logic** (`src/resilience/retry_logic.py`): Exponential backoff with jitter
- **Rate Limiter** (`src/resilience/rate_limiter.py`): API rate control
- **Graceful Degradation** (`src/resilience/graceful_degradation.py`): Fallback mechanisms
- **Health Monitor** (`src/resilience/health_monitor.py`): System health tracking

#### Publishing & Notifications
- **GitHub Publisher** (`src/publishers/github_publisher.py`): GitHub Pages deployment
- **Email Notifier** (`src/notifications/email_notifier.py`): Newsletter distribution
- **Dashboard Generator** (`src/metrics/dashboard_generator.py`): Performance visualization

#### Configuration
- **Config** (`src/config.py`): Centralized configuration with env variables
- **Sources** (`sources.json`): 26 news sources configuration
- **Models** (`src/models.py`): Data classes (Article, NewsSource, AIAnalysis, etc.)

### Important Patterns

#### Error Handling
- Comprehensive resilience framework with circuit breakers
- Retry logic with exponential backoff and jitter
- Graceful degradation for all external dependencies
- Structured logging with correlation IDs
- Health monitoring and alerting

#### Testing Strategy
- 15+ test files covering all major components
- Real data validation with actual RSS feeds
- Performance benchmarking included
- DRY_RUN mode for safe testing
- Integration tests for complete pipeline

#### Environment Configuration
- `.env` file for local development
- GitHub Secrets for production API keys
- `DRY_RUN=true` for testing without API costs
- `AI_MAX_TOKENS=8000` for production
- Configurable AI provider support

#### Performance & Metrics
- Metrics collection for all pipeline stages
- Cost tracking for AI API usage
- Performance monitoring with dashboards
- Connection pooling for HTTP optimization
- Database resilience for data persistence

## Development Notes

### Working with Sources
- Current configuration: 26 sources (20 RSS + 6 web)
- Add new RSS sources to `tier1_sources` in `sources.json`
- Add web scraping sources to `tier2_sources`
- Test new sources with `test_simple_collection.py`
- Validate with `src/processors/content_quality_validator.py`

### AI Integration
- Claude API key in `ANTHROPIC_API_KEY` environment variable
- Cost controls via `src/ai/cost_controller.py`
- Token limit: 8000 for production (configurable)
- Mock analysis automatic fallback
- Prompt customization in `claude_analyzer.py`

### Newsletter Generation
- HTML templates in `templates/` directory
- Output saved to `output/` directory
- Professional styling with impact scores
- GitHub Pages deployment to `docs/` directory
- Sitemap generation for SEO

### GitHub Actions
- Daily automation at 6:00 UTC
- Manual trigger with dry-run option
- Issue creation on repeated failures
- Artifact retention for 30 days
- Automatic cleanup of old data

### Monitoring & Alerts
- Health checks via `src/resilience/health_monitor.py`
- Performance metrics in `src/metrics/`
- Cost tracking with budget alerts
- Email notifications for failures
- Dashboard generation for visualization

### Database & Persistence
- SQLite for local data storage
- Database resilience with retry logic
- 30-day data retention policy
- Automated cleanup via `src/cleanup.py`