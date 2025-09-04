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

# Test archiver and dashboard system
python test_archiver_suite.py         # Test complete archiver functionality
python tests/test_archiver.py         # Test AI data archiver core features
python tests/test_archive_utilities.py # Test cleanup and dashboard utilities

# Test X.com thread generation
python test_x_threads.py              # Test thread generation (mock + real if API key available)

# Test enhanced content extraction
python test_enhanced_content.py      # Test full article content fetching

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

### Main Pipeline Commands
```bash
# Run complete pipeline (uses DRY_RUN=true by default)
python src/main_pipeline.py

# Run with API calls (requires API keys)
DRY_RUN=false python src/main_pipeline.py

# Allow overwriting existing newsletter (for debugging)
ALLOW_OVERWRITE=true python src/main_pipeline.py

# Test individual components
python src/test_simple_collection.py   # Test collection from all 26 sources
python src/test_complete_pipeline.py   # End-to-end test

# Run via GitHub Actions (manually trigger)
# Go to Actions tab and run "Daily Geopolitical Newsletter" workflow
```

### Utility Commands
```bash
# AI Archive Management
python cleanup_archives.py                    # Clean old archive data (30 days retention)
python cleanup_archives.py --days 14         # Keep 14 days of data
python cleanup_archives.py --dry-run         # Preview what would be deleted
python cleanup_archives.py --deep-clean      # Aggressive cleanup (remove failed runs)
python cleanup_archives.py --force           # Skip confirmation prompts

# Dashboard Generation (Unified)
python generate_unified_dashboard.py        # Generate unified dashboard to docs/dashboard.html
python src/cleanup.py                        # Legacy cleanup (keeps 30 days)
python src/sitemap_generator.py             # Generate sitemap for GitHub Pages
```

## Architecture Overview

### Pipeline Flow
1. **Collection Layer** (`src/collectors/`): Collects from 26 sources (20 RSS + 6 web scraping)
2. **Processing Layer** (`src/processors/`): Deduplicates, clusters, and scores articles
3. **AI Analysis Layer** (`src/ai/`): Claude API with cost controls and fallback mechanisms
4. **Newsletter Generation** (`src/newsletter/`): Professional HTML newsletter creation
5. **AI Archive Layer** (`src/archiver/`): Comprehensive data archiving and retention management
6. **Unified Dashboard Layer** (`src/dashboard/`): Single streamlined dashboard for GitHub Pages
7. **Publishing Layer** (`src/publishers/`): GitHub Pages deployment and email notifications
8. **Metrics & Monitoring**: Performance tracking, cost monitoring, health checks

### Key Components

#### Data Collection
- **RSS Collector** (`src/collectors/rss_collector.py`): Handles 20 tier1 RSS feeds with enhanced content extraction
- **Web Scraper** (`src/collectors/web_scraper.py`): Scrapes 6 tier2 sources with SSL bypass for certificate issues
- **Main Collector** (`src/collectors/main_collector.py`): Parallel collection orchestration
- **Article Content Fetcher** (`src/collectors/article_content_fetcher.py`): Advanced full-text extraction from URLs
- **Connection Pooling**: Optimized HTTP connections for performance

#### Enhanced Content Extraction (NEW)
- **Multi-strategy extraction**: Uses newspaper3k, readability-lxml, and BeautifulSoup in order of preference
- **Parallel fetching**: Fetches full article content for up to 5 articles simultaneously  
- **Smart caching**: 24-hour cache to reduce redundant requests
- **Quality scoring**: Scores content quality (0.0-1.0) based on length, structure, and variety
- **Automatic enhancement**: Enhances short RSS summaries (<200 chars) with full article content
- **Configurable**: Enable/disable with `FETCH_FULL_CONTENT` environment variable

#### Data Processing
- **Deduplicator** (`src/processors/deduplicator.py`): Title similarity-based deduplication (0.85 threshold)
- **Clusterer** (`src/processors/clusterer.py`): Groups related articles
- **Content Validator** (`src/processors/content_quality_validator.py`): Quality assessment
- **Main Processor** (`src/processors/main_processor.py`): Processing pipeline coordinator

#### AI Integration
- **Claude Analyzer** (`src/ai/claude_analyzer.py`): Anthropic Claude API integration with multi-dimensional scoring
- **Cost Controller** (`src/ai/cost_controller.py`): Budget tracking and spending limits
- Mock analysis fallback for testing and API failures
- Configurable token limits (default: 8000 for Sonnet 4, increased from 4096 Haiku)
- Enhanced debug logging for API requests/responses
- **AI Data Archiver** (`src/archiver/ai_data_archiver.py`): Comprehensive data archiving for transparency

#### AI Archive System
- **Archive Management**: Tracks all collected articles, clusters, AI requests/responses, and newsletters
- **Retention Policies**: Configurable retention periods (default: 30 days) with intelligent cleanup
- **Data Transparency**: Complete audit trail of what data was sent to AI for analysis
- **Statistics Tracking**: Cost monitoring, request/response times, model usage metrics
- **Storage Optimization**: JSON-based storage with optional compression for old data
- **Structured Organization**: Date-based directory structure with unique run IDs

#### Unified Dashboard System
- **Unified Dashboard** (`src/dashboard/unified_dashboard.py`): Single streamlined dashboard generator
- **GitHub Pages Integration**: Generates directly to `docs/dashboard.html` for seamless publishing
- **Minimalist Design**: Clean, functional interface with essential metrics only
- **Latest Run Data**: Shows most recent pipeline execution results
- **Summary Statistics**: 7-day success rates, cost tracking, performance metrics
- **Real-time Updates**: Automatic generation with each pipeline run

#### AI Scoring Dimensions
The AI analyzer now evaluates stories across multiple dimensions:
- **urgency_score**: Time sensitivity (1=long-term, 10=immediate)
- **scope_score**: Geographic/political impact (1=local, 10=global)
- **novelty_score**: Unexpectedness (1=expected, 10=unprecedented)
- **credibility_score**: Source reliability (1=unverified, 10=confirmed)
- **impact_dimension_score**: Overall geopolitical significance (1=minor, 10=world-changing)
- **content_type**: Classification as breaking_news, analysis, or trend

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

#### Duplicate Prevention
- Pipeline checks for existing newsletter before processing (line 74 in `main_pipeline.py`)
- Can be overridden with `ALLOW_OVERWRITE=true` for debugging
- Prevents duplicate runs on the same date

#### Enhanced Debugging
- Source distribution logging at collection, clustering, and AI selection stages
- Full API request/response logging when analyzing clusters
- Simulation statistics in DRY_RUN mode

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
- `AI_MAX_TOKENS=8000` for Sonnet 4 production (increased from 4096 Haiku)
- `ALLOW_OVERWRITE=true` to regenerate existing newsletters
- Configurable AI provider support
- `FETCH_FULL_CONTENT=true` to enable enhanced article content extraction (default: true)
- `MAX_PARALLEL_FETCHES=5` maximum concurrent content fetches
- `CONTENT_FETCH_TIMEOUT=10` timeout in seconds for each fetch
- `CONTENT_CACHE_DAYS=1` days to cache extracted content

#### Archive Configuration
- `AI_ARCHIVE_ENABLED=true` to enable comprehensive data archiving
- `AI_ARCHIVE_PATH=ai_archive` to set archive directory location
- `AI_ARCHIVE_RETENTION_DAYS=30` for automatic cleanup policy
- `AI_ARCHIVE_MAX_SIZE_MB=500` to set maximum archive size limit
- `DASHBOARD_AUTO_GENERATE=true` for automatic dashboard creation
- `DASHBOARD_OUTPUT_PATH=dashboards` to set dashboard output directory

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
- Add web scraping sources to `tier2_sources` with CSS selectors
- Test new sources with `test_simple_collection.py`
- Validate with `src/processors/content_quality_validator.py`

### AI Integration
- Claude API key in `ANTHROPIC_API_KEY` environment variable
- Cost controls via `src/ai/cost_controller.py`
- Token limit: 8000 for production with Sonnet 4 (configurable)
- Mock analysis automatic fallback with realistic simulations
- Prompt customization in `claude_analyzer.py` (line 217-261)
- Multi-dimensional scoring for better story selection
- **Comprehensive archiving**: All AI requests/responses automatically archived for transparency

### AI Archive System
- **Archiver Integration**: Automatic archiving throughout pipeline execution
- **Data Tracking**: Complete audit trail of collected articles, clusters, AI analysis
- **Retention Management**: Configurable cleanup policies via `cleanup_archives.py`
- **Statistics**: Cost tracking, processing times, model usage across all runs
- **File Organization**: Date-based structure (`YYYY-MM-DD/run_{uuid}/`) for easy navigation
- **JSON Storage**: Human-readable JSON files for all archived data

### Debug Dashboard System
- **Dashboard Generation**: Rich HTML dashboards with interactive Plotly charts
- **Visualization Types**: Source performance, cost analysis, processing times, success rates
- **Multi-view Support**: Individual runs, multi-day summaries, trend analysis
- **Auto-generation**: Integrated into pipeline and GitHub Actions workflow
- **Responsive Design**: Professional styling with mobile-friendly interface
- **Export Options**: PDF generation support via Kaleido engine

### Newsletter Generation
- HTML templates in `templates/` directory
- Output saved to `output/` directory
- Professional styling with multi-dimensional impact scores
- GitHub Pages deployment to `docs/` directory
- Sitemap generation for SEO
- Content balancing: ~25% breaking news, 75% analysis/trends

### X.com Thread Generation (NEW)
- **Thread Generator** (`src/social/x_thread_generator.py`): Generates Czech X.com threads
- **Single API Call**: Everything handled in one Claude call (analysis → Czech translation → formatting)
- **Smart Selection**: Only stories with impact score ≥ 7.0 become threads
- **Czech-Native**: Direct Czech generation, not translation - more natural
- **HTML Preview**: Export to `docs/threads/` for manual review before posting
- **Character Validation**: Automatic 280-char limit checking per tweet
- **Mock Mode**: Test generation without API calls
- **Configuration**:
  - `X_THREADS_ENABLED=true` to enable
  - `X_THREADS_MAX_DAILY=4` max threads per day
  - `X_THREADS_MIN_IMPACT_SCORE=7.0` minimum story score

### GitHub Actions
- Daily automation at 6:00 UTC
- Manual trigger with dry-run option
- Issue creation on repeated failures
- Artifact retention for 30 days including AI archive data and dashboards
- Automatic AI archive cleanup (30-day retention policy)
- Debug dashboard generation and deployment to GitHub Pages
- Concurrency control to prevent conflicts
- Enhanced logging with archive and dashboard status reporting

### Monitoring & Alerts
- Health checks via `src/resilience/health_monitor.py`
- Performance metrics in `src/metrics/`
- Cost tracking with budget alerts
- Email notifications for failures
- **Interactive Debug Dashboards**: Rich HTML dashboards with Plotly visualizations
- **AI Archive Monitoring**: Complete transparency of AI requests/responses and costs
- **Automated Dashboard Generation**: Daily dashboards and multi-day summaries
- Source distribution tracking throughout pipeline
- Real-time processing metrics and success rate monitoring

### Database & Persistence
- SQLite for local data storage
- Database resilience with retry logic
- **AI Archive Storage**: JSON-based comprehensive data archiving
- **Dual Retention Policies**: 30-day retention for both SQLite and AI archive data
- **Automated Cleanup**: Legacy cleanup via `src/cleanup.py` and new archive cleanup via `cleanup_archives.py`
- **Archive Organization**: Date-based directory structure with unique run identifiers
- **Data Transparency**: Complete audit trail of AI interactions and pipeline execution

### Known Issues & Workarounds
- SSL certificate verification disabled for web scraping (line 121 in `web_scraper.py`) - required for some sources with certificate issues
- AI model upgraded to Claude Sonnet 4 with 8000 token limit for better analysis quality
- ALLOW_OVERWRITE environment variable for debugging duplicate prevention
- Archive cleanup required for long-running installations to manage disk space

## Archiving System Benefits

### Complete Data Transparency
The comprehensive AI archiving system provides full visibility into:
- **What data** was collected from each source
- **Which articles** were clustered together 
- **Exact prompts** sent to the AI for analysis
- **Full AI responses** including reasoning and scoring
- **Cost breakdown** per request and total per run
- **Performance metrics** for each pipeline stage

### Advanced Debugging & Monitoring
- **Interactive dashboards** with rich visualizations using Plotly
- **Historical trend analysis** across multiple days/weeks
- **Source performance tracking** to identify problematic feeds
- **AI cost optimization** through detailed cost analysis
- **Processing time monitoring** to identify bottlenecks
- **Success rate tracking** for reliability monitoring

### Operational Intelligence
- **Automated cleanup** with configurable retention policies
- **Intelligent run classification** (successful vs. failed runs)
- **Deep clean options** to remove only failed runs while preserving successful data
- **Storage optimization** with size monitoring and alerts
- **Batch dashboard generation** for comprehensive analysis
- **GitHub Pages integration** for easy access to monitoring dashboards