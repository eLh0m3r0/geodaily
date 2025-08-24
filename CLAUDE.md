# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Create virtual environment
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
python test_simple_collection.py      # Test data collection (481 articles)
python test_deduplication.py          # Test processing (1.46% dedup rate)
python test_newsletter.py             # Test newsletter generation
python test_complete_pipeline.py      # Test end-to-end pipeline

# Test with specific configurations
python tests/test_environment.py      # Test environment setup
python tests/test_collectors.py       # Test collection system
python tests/test_rss_collector.py    # Test RSS feed collection
```

### Main Pipeline Commands
```bash
# Run complete pipeline (uses DRY_RUN=true by default)
python src/main_pipeline.py

# Run with API calls (requires API keys)
DRY_RUN=false python src/main_pipeline.py

# Run via GitHub Actions (manually trigger)
# Go to Actions tab and run "Daily Geopolitical Newsletter" workflow
```

## Architecture Overview

### Pipeline Flow
1. **Collection Layer** (`src/collectors/`): Collects articles from 19 sources (14 RSS + 5 web scraping)
2. **Processing Layer** (`src/processors/`): Deduplicates, clusters, and scores articles
3. **AI Analysis Layer** (`src/ai/`): Uses Claude API to analyze and select top stories
4. **Newsletter Generation** (`src/newsletter/`): Generates professional HTML newsletters
5. **Publishing Layer**: Saves locally (Substack integration planned)

### Key Components

#### Data Collection
- **RSS Collector** (`src/collectors/rss_collector.py`): Handles RSS feeds from mainstream sources
- **Web Scraper** (`src/collectors/web_scraper.py`): Scrapes articles from sites without RSS
- **Main Collector** (`src/collectors/main_collector.py`): Orchestrates parallel collection

#### Data Processing
- **Deduplicator** (`src/processors/deduplicator.py`): Removes duplicate articles using title similarity
- **Main Processor** (`src/processors/main_processor.py`): Clusters articles and calculates relevance scores

#### AI Integration
- **Claude Analyzer** (`src/ai/claude_analyzer.py`): Integrates with Anthropic's Claude API
- Falls back to mock analysis when API unavailable or in DRY_RUN mode

#### Configuration
- **Config** (`src/config.py`): Centralized configuration management with environment variables
- **Sources** (`sources.json`): Configuration for all 19 news sources
- **Models** (`src/models.py`): Data classes for Article, NewsSource, AIAnalysis, etc.

### Important Patterns

#### Error Handling
- Graceful handling of failed sources (some RSS feeds may be down)
- Comprehensive retry logic with exponential backoff
- Mock analysis fallback when AI API fails
- Detailed logging for debugging

#### Testing Strategy
- Each component has dedicated test files
- Real data validation (collects actual articles)
- Performance benchmarks included
- Dry-run mode for testing without API calls

#### Environment Configuration
- Uses `.env` file for local development
- GitHub Secrets for production API keys
- `DRY_RUN=true` for testing without API calls
- Configurable AI provider (Anthropic/Gemini support)

## Development Notes

### Working with Sources
- Add new sources to `sources.json`
- RSS sources go in `tier1_sources`
- Web scraping sources go in `tier2_sources`
- Test new sources with `test_simple_collection.py`

### AI Integration
- Claude API key stored in `ANTHROPIC_API_KEY` environment variable
- Mock analysis automatically used when API unavailable
- AI prompts can be modified in `claude_analyzer.py`

### Newsletter Generation
- HTML templates in `templates/` directory
- Generated newsletters saved to `output/` directory
- Professional styling with impact score color coding

### GitHub Actions
- Daily automation at 6:00 UTC via `.github/workflows/daily_newsletter.yml`
- Manual trigger available with dry-run option
- Creates issues on repeated failures
- Saves artifacts (newsletters + logs) for 30 days

### Performance Metrics
- Collection: ~7 seconds for 481 articles from 19 sources
- Processing: ~27 seconds for deduplication and clustering
- Total pipeline: ~35 seconds end-to-end
- Success rate: ~98.5% (1.46% deduplication rate)