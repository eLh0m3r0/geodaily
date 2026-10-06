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

# Weekly digest (Sundays via weekly_digest.yml; DRY_RUN builds without sending)
python -m src.weekly_digest

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
1. **Collection Layer** (`src/collectors/`): Collects from 86 sources (84 RSS + 2 web scraping) across 14 global perspectives — 52 of the RSS feeds are non-Western
2. **Processing Layer** (`src/processors/`): Semantic event clustering (fastembed MiniLM + HDBSCAN in `embedding_clusterer.py`, then a conservative fragment repair: clusters with centroid cosine ≥0.85 merge, noise articles ≥0.75 from a centroid join it — so one event's Western and non-Western reports land in one grid; title-similarity fallback), dedup and scoring
3. **AI Analysis Layer** (`src/ai/`): Claude API with cost controls — one issue call (3 ranked stories + quick hits + big number, `simple_multi_stage_analyzer.py`; no sports/celebrity, quick hits deduped against story events by URL/cluster/title-overlap) plus one perspective-grid call (`perspective_analyzer.py`), with a Flesch-Kincaid readability gate (`readability.py`) whose single rewrite is ACCEPTED only if it lowers the grade without turning the copy choppy (avg sentence < 10.5 words or > 25% fragments) or dropping figures; post-generation guardrails in `src/ai/editorial.py` (sentence-case headlines by case evidence, no quick hit / big number rerun from the last issues unless it carries a new figure, big number must not repeat a figure already in the issue, quick hits relinked from state to non-state outlets of the same event; quick hits and the big number dropped when `is_off_brand` matches a domestic-crime/entertainment marker such as death row, botched execution, fraternity, lottery — Christa Pike ran 3 days as a 'follow-up', 2026-10-01..04); the prompt sees the last issues' stories, quick hits, big number and blindspot (`load_issue_history`)
4. **Newsletter Generation** (`src/newsletter/`): Hybrid issue format = THE BIG STORY (full treatment: 'How the World Covers It' perspective grid + signals) + MORE TOP STORIES (2 compact stories, each with a computed coverage mini-bar — no extra AI call) + DEVELOPING (max 3 one-line updates on RUNNING storylines — see Storylines below) + ALSO TODAY quick hits + THE BLINDSPOT (own section — by construction a DIFFERENT event than the stories, never rendered inside a story) + THE BIG NUMBER; story order is editorial (analyzer ranking, never re-sorted by score); web + email-safe renderers, named source links (`source_display.py`), machine-readable issue JSON (`issue_store.py`) including `meta` (provider, requested/served model, tokens, billed cost, readability before/after rewrite, grid cost) — check `meta` first when reviewing which model wrote an issue. Grid rows with no editorial angle (`wire_copy`) collapse into one 'Straight news, no distinct angle' line; coverage legends say 'N reports from M outlets'; the blindspot text never says who did/didn't cover it — the renderer adds 'Reported by … — no Western outlet we track' from `blindspot_outlets`. Blindspot candidates must have ≥2 outlets incl. a non-state one and must not overlap today's stories or the last 3 issues' stories/blindspots (the repeat screen compares content words minus `BLINDSPOT_FRAMING_WORDS` — the 'why it matters / security risks / global trade' boilerplate every blindspot shares once rejected an unrelated event, 2026-10-02). The grid call makes up to 3 attempts (the third only after a `stop_reason=length` budget cut-off) and `_parse_json_object` takes the first complete JSON object via `raw_decode`, so a doubled object or trailing prose no longer sinks the grid (2026-10-03). Polymarket signals (`src/enrichment/signals.py`) need a hit on a specific term — names in `_GENERIC_TERMS` (Trump, Russia, China, EU …) alone never select a market. Shared render helpers live in `src/perspectives.py` (web, email and Pages renderers all use them)
5. **AI Archive Layer** (`src/archiver/`): Comprehensive data archiving and retention management
6. **Unified Dashboard Layer** (`src/dashboard/`): Single streamlined dashboard for GitHub Pages
7. **Publishing Layer** (`src/publishers/`): GitHub Pages deployment and email notifications
8. **Metrics & Monitoring**: Performance tracking, cost monitoring, health checks

### Key Components

#### Data Collection
- **RSS Collector** (`src/collectors/rss_collector.py`): Handles the 84 tier1 RSS feeds with enhanced content extraction
- **Web Scraper** (`src/collectors/web_scraper.py`): Scrapes 2 tier2 sources with SSL bypass for certificate issues
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
- Configurable token limits (default: 16000 for Sonnet 5 — new tokenizer + adaptive thinking need headroom)
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
- **Sources** (`sources.json`): 86 news sources configuration
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
- `AI_MAX_TOKENS=16000` for Sonnet 5 production (new tokenizer uses ~30% more tokens; adaptive thinking spends from the same budget); the issue call uses `ANALYSIS_MAX_TOKENS=24000`, and an empty `finish=length` reply from OpenRouter is retried with a doubled budget (up to `AI_MAX_GROWN_TOKENS=32000` — a 64k retry ran past the 600 s request limit) instead of the same budget on another host
- `AI_MAX_COST_PER_MONTH=30.0` monthly budget cap for AI spend
- `ALLOW_OVERWRITE=true` to regenerate existing newsletters
- `NEWSLETTER_EDITOR_NAME` named human curator for the footer persona ("drafted with AI, curated by X") — set it only if someone really reviews issues before sending; without it the footer says plainly that the issue is written with AI and sent automatically (it used to promise a human review that never happened)
- `NEWSLETTER_TAGLINE` (default "The world's news from every side")
- `NEWSLETTER_TARGET_STORIES=3` hybrid default: big story (full treatment) + 2 compact stories; evergreen SEO story page is published for EVERY story (3 indexable topics/day)
- `READABILITY_MAX_GRADE=9.5` Flesch-Kincaid gate; denser copy triggers one simplify rewrite, kept only if it doesn't make the copy choppy (the 2026-09 rewrites turned ~13-word sentences into ~9-word telegrams)
- `NEWSLETTER_HISTORY_DAYS=2` how many previous issues the analyzer sees (stories, quick hits, big number, blindspot); the blindspot screen always looks back at least 3
- `BUTTONDOWN_WEEKLY_TAG=weekly` tag for Sunday-digest subscribers (excluded from daily sends)
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

### Storylines and DEVELOPING (anti-repetition)
- `src/ai/storylines.py` identifies an event across days by its DISTINCTIVE names (story `signal_terms`, capitalised names in quick hits): Tigray, Mekelle, flydubai, RAF Fairford. Generic actors/places (Russia, Trump, NATO, oil, big countries — `GENERIC_TERMS`) and title/month/furniture words never count; single names of 5+ letters also match short suffixes (Siberia/Siberian)
- The analyzer prompt only LISTS the stories the reader already followed (one sentence: fresh events first) — the DEVELOPING logic itself is enforced in code, because a prompt carrying the full storyline rules and a `developing` output field made DeepSeek reason past 32k tokens without answering (2026-10-06 shadow runs). Only the LEAD may continue a storyline that was a big story in the last 2 issues; a continuing story further down is demoted to DEVELOPING (an issue keeps >= 2 stories). Quick hits in a running storyline move to DEVELOPING (max 3, one per storyline, new facts only); quick hits restating today's stories are dropped. The analyzer asks for exactly the target number of stories and 6-8 quick hits (a reserve 4th story + 8-10 quick hits pushed reasoning past 32k tokens and the analysis to 18 minutes), so a demotion can leave 2 stories; at most 8 quick hits are published. Blindspot candidates are also screened against today's stories' headlines/clusters and the Western pool with stemmed word overlap (10-06: the Moscow drone strike was story #2 and the blindspot). Every editorial decision is recorded in `meta.editorial_actions`
- Blindspot candidates that share a distinctive name with today's stories or anything in the last 5 issues are skipped (2026-10-05 offered flydubai — the week's most-covered story — as a blindspot); a blindspot must be an EVENT, not a statement; candidates are ranked by distinct non-state outlets; a candidate whose title matches a Western outlet's title anywhere in the pool (event split across clusters) is skipped; the big number must contain a figure and must not continue a running storyline
- Grid members are focused on the story's distinctive names (no TASS-on-Donetsk row under a Kyiv-bridges story); quotes that date a past event in the future (source typos) are dropped
- Big number must describe today's event (a context naming an earlier year is dropped); Nobel science prizes are off-brand; headlines that state as fact what the body calls unconfirmed are flagged in `meta.quality_flags`
- `scripts/issue_quality_report.py` writes a checklist to the run summary and `::warning::` annotations for degraded sections (no grid angles, no blindspot, < 5 quick hits, choppy copy, flags) — it never fails the job

### Working with Sources
- Current configuration: 86 sources (84 RSS + 2 web); expanded 2026-09-08 with 33 vetted non-Western/European feeds (RT, CGTN China, Global Times, Haaretz, Ynetnews, El País, Folha, Hindustan Times, NDTV, Korea Times/Herald, Taipei Times, Bangkok Post, Nation, Punch, Africanews, Mail & Guardian, IPS, Le Monde, Der Spiegel, Euronews, ANSA, Ukrainska Pravda, Ukrinform, Novaya Gazeta Europe, Lowy …) after removing 8 dead feeds (Arab News, Asia Times, EUobserver, Kyiv Independent, Times of Israel, China Daily, Jerusalem Post, Brookings — its feed has an XML entity feedparser rejects, 0 entries since at least August). Feeds behind Cloudflare bot protection (Indian Express, Times of Israel, Arab News, Al Arabiya, Rest of World, Chatham House, Daily Sabah, Middle East Monitor) return 403 to the collector on datacenter IPs and cannot be used — a feed that passes `validate_sources.py` can still 403 in the pipeline, so confirm new feeds with a `ci.yml` dry run
- Each source carries `perspective` (one of 15 axes incl. `ukrainian`, see `src/perspectives.py`), `state_affiliated` (state media are cited as framing data with a visible label, never as sole source of fact) and `reliability_tier` (1-3); optional `site` (article domain when it differs from the feed domain) and `display` (clean outlet name)
- Each source carries a per-source `weight` (0.7–1.3) that scales relevance scoring, deduplication preference, and is passed to the AI as an editorial-quality signal
- Validate feeds with `python scripts/validate_sources.py` (add `--strict` in CI to fail on dead feeds); a weekly `source_health.yml` workflow runs it every Monday. To vet feeds before adding them, put them in `sources.candidates.json` and run the validator with `--file sources.candidates.json` (or dispatch `source_health.yml` with the `file` input on any branch — the sandbox cannot reach news sites, the Actions runner can)
- Freshness windows are per category: think_tank 72h, analysis 48h, everything else 24h (`RSSCollector.FRESHNESS_WINDOW_HOURS`)
- Feeds without publication dates (Sixth Tone, Nikkei Asia) are dated by first sighting, not by "now": `src/collectors/first_seen.py` persists url → first-seen in `docs/data/first_seen.json` (committed by the daily workflow with the rest of docs/), so an undated entry is fresh for exactly one issue; blindspot candidates are additionally capped at 36h (`PerspectiveAnalyzer.BLINDSPOT_MAX_AGE_HOURS`)
- The collector sends a full browser User-Agent (`USER_AGENT` in config) — Cloudflare-protected feeds return 403 to bot-style UAs
- Add new RSS sources to `tier1_sources` in `sources.json`
- Add web scraping sources to `tier2_sources` with CSS selectors
- Test new sources with `test_simple_collection.py`
- Validate with `src/processors/content_quality_validator.py`

### AI Integration
- AI provider is configurable: `AI_PROVIDER=openrouter` (default, DeepSeek V4.1 Flash) or `anthropic`
- Keys: `OPENROUTER_API_KEY` for OpenRouter, `ANTHROPIC_API_KEY` for Anthropic — the unused one can stay set, it is the rollback path
- All calls go through `src/ai/llm_client.py`, which mimics the Anthropic Messages API response shape so `api_utils` and the analyzers need no provider-specific code
- Switching providers is one env var; no code revert
- Cost controls via `src/ai/cost_controller.py`
- Token limit: 16000 for production with Sonnet 5 (configurable)
- Sampling params (temperature/top_p/top_k) are NOT sent — Sonnet 5 rejects non-default values with HTTP 400
- Responses are parsed via `src/ai/api_utils.extract_response_text()` — adaptive-thinking models may emit thinking blocks before the text block, so never read `response.content[0].text` directly
- Costs come from the provider's actually billed amount when it reports one (OpenRouter does); the `AI_INPUT_COST_PER_MTOK`/`AI_OUTPUT_COST_PER_MTOK` rates are only a fallback — for Anthropic they were 20x off the real OpenRouter charge
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
- Daily automation: cron 03:23 UTC with backups 04:47 and 06:11 (GitHub starts scheduled runs hours late under load — 09-17..09-29 the 6:17 slot ran 11:30-14:15); `repository_dispatch` type `publish-newsletter` lets an external scheduler trigger it on time (DEPLOYMENT.md). The precheck makes every non-manual run a no-op once today's issue is on `main`
- Manual `workflow_dispatch` runs are guarded by the same precheck (the daily issue is in practice started by a dispatch at ~08:21 UTC, the cron slots fire hours late); only `force=true` regenerates and RESENDS an existing issue, and only `force`/`dry_run` set ALLOW_OVERWRITE
- A manual `dry_run=true` run never emails, never commits docs/ and never deploys Pages (mock content)
- Email delivery is verified after publishing: a Buttondown rejection (e.g. its prohibited-keyword filter — 2026-09-18 was never sent over "Leroy Merlin") is retried once with the keyword neutralized in the email only; a final failure turns the job red and opens an issue, while the website still deploys
- LLM calls have a wall-clock limit `AI_REQUEST_TIMEOUT_S=600` (one retry, `AI_TIMEOUT_RETRIES=1`) and log provider, requested vs served model, latency and tokens per call
- Manual trigger with dry-run option
- No push trigger on the production workflow — pushes to `src/**` run `ci.yml` (dry-run validation, publishes nothing); code changes go live with the next scheduled run
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
- AI model is `deepseek/deepseek-v4.1-flash` via OpenRouter since 2026-09-15, chosen in a blind test over 11 production days (beat claude-sonnet-5 by 8.7 points at 1/15th the cost); rollback is `AI_PROVIDER=anthropic AI_MODEL=claude-sonnet-5`
- Do NOT set a `reasoning` cap for DeepSeek — limiting it measurably lowered quality in the test
- X.com threads generate CZECH and were never tested on DeepSeek; `X_THREADS_AI_PROVIDER`/`X_THREADS_MODEL` keep them on a separate model if needed. They use `X_THREADS_MAX_TOKENS=16000` (the old 4000 was eaten by Sonnet 5's adaptive thinking — 17 of 49 threads parsed in 09-12..09-29), a tolerant JSON parser with one retry, and their cost is recorded in the cost controller
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