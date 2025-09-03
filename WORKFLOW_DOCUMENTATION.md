# 📊 GeoPolitical Daily - Komplexní Workflow Dokumentace

## 🎯 Přehled Systému
Automatizovaný pipeline pro generování denního geopolitického newsletteru z 26 zpravodajských zdrojů s AI analýzou a multi-platform publikováním.

---

## 🔄 HLAVNÍ WORKFLOW PIPELINE

### 📍 **SPOUŠTĚNÍ** (Trigger Points)

#### 1. **GitHub Actions Schedule** (`daily_newsletter.yml`)
- ⏰ **Denně v 6:00 UTC** (8:00 CET)
- Automatický trigger přes cron: `0 6 * * *`

#### 2. **Manuální Spuštění**
- GitHub Actions: Workflow dispatch s DRY_RUN volbou
- CLI: `python src/main_pipeline.py`
- Test: `python test_complete_pipeline.py`

#### 3. **Push Trigger**
- Při změnách v `src/**`, `requirements.txt`, workflow souborech
- Ignoruje změny v `docs/**` (generovaný obsah)

---

## 🏗️ PIPELINE ARCHITEKTURA

### 📝 **HLAVNÍ ORCHESTRÁTOR** (`src/main_pipeline.py`)

```
run_complete_pipeline()
    ├── Step 0: Duplicate Check (line 64-80)
    ├── Step 1: Config Validation (line 83-129)
    ├── Step 2: Article Collection (line 131-202)
    ├── Step 2.5: Quality Validation (line 204-251)
    ├── Step 3: Processing & Clustering (line 253-312)
    ├── Step 4: AI Analysis (line 314-413)
    ├── Step 5: Newsletter Generation (line 415-468)
    ├── Step 6: Publishing (line 470-523)
    ├── Step 7: Email Notification (line 525-560)
    ├── Step 8: Summary Report (line 562-657)
    └── Step 9: Cleanup (line 617-657)
```

---

## 📊 DETAILNÍ WORKFLOW KROKY

### **STEP 0: DUPLICATE CHECK** 🔍
**Cíl**: Zabránit duplicitním newsletterům
```python
# Kontroluje existenci: docs/newsletters/newsletter-{YYYY-MM-DD}.html
if newsletter_path.exists():
    logger.warning("Newsletter already exists")
    return True  # Úspěšný exit bez zpracování
```

### **STEP 1: CONFIGURATION & RESILIENCE** ⚙️
**Komponenty**:
1. **Config Validation** (`Config.validate_config()`)
   - Kontrola API klíčů
   - Ověření sources.json
   - Environment variables

2. **Resilience Infrastructure**:
   ```python
   degradation_manager.register_component("collection_system")
   degradation_manager.register_component("ai_analyzer")
   degradation_manager.register_component("newsletter_generator")
   degradation_manager.register_component("publishing_system")
   health_monitor.start_monitoring()
   ```

### **STEP 2: DATA COLLECTION** 📰
**Orchestrace**: `MainCollector.collect_all_articles()`

#### Paralelní Sběr Dat:
```python
ThreadPoolExecutor(max_workers=10):
    ├── RSS Collector (20 zdrojů)
    │   ├── BBC, CNN, Reuters...
    │   └── Failover groups by category
    └── Web Scraper (6 zdrojů)
        ├── CSS selektory
        └── SSL verify=False (line 121)
```

#### Health Monitoring:
- `source_health_monitor.register_source()`
- Automatický failover při selhání
- Circuit breakers pro každý zdroj

**Výstup**: ~400-500 raw articles

### **STEP 2.5: CONTENT QUALITY VALIDATION** ✅
**Komponenta**: `content_quality_validator.validate_articles()`

```python
Validační kritéria:
- Minimální délka titulku: 10 znaků
- Minimální délka summary: 50 znaků
- Validní URL
- Datum publikace (max 7 dní staré)
- Duplikátní obsah check
```

**Výstup**: Filtrováno na high-quality articles

### **STEP 3: PROCESSING & CLUSTERING** 🔧
**Komponenta**: `MainProcessor.process_articles()`

#### Sub-kroky:
1. **Deduplication** (`ArticleDeduplicator`)
   - Title similarity (difflib.SequenceMatcher)
   - Threshold: 0.85 podobnost
   - Výsledek: ~1.5% dedup rate

2. **Basic Scoring**:
   ```python
   high_priority_keywords = ['china', 'russia', 'ukraine', 'nato'...]
   source_weights = {'think_tank': 1.3, 'analysis': 1.1...}
   ```

3. **Clustering** (`cluster_articles()`)
   - Seskupení podobných článků
   - Main article selection
   - Cluster scoring

**Výstup**: ~50-100 clusters

### **STEP 4: AI ANALYSIS** 🤖
**Komponenta**: `ClaudeAnalyzer.analyze_clusters()`

#### Cost Control Flow:
```python
1. estimate_cost() → Check budget
2. ai_cost_controller.check_budget_allowance()
3. If over budget → Mock fallback
4. Else → Claude API call
```

#### Claude API Integration:
- Model: `claude-3-haiku-20240307`
- Max tokens: 8000 (production)
- Temperature: 0.7
- Cost tracking per call

#### Fallback Mechanism:
```python
if Config.DRY_RUN or !API_KEY or budget_exceeded:
    return create_mock_analyses()
```

**Výstup**: 4 top stories s AI analýzou

### **STEP 5: NEWSLETTER GENERATION** 📧
**Komponenta**: `NewsletterGenerator.generate_newsletter()`

#### Content Balancing:
```python
target_breaking = 25%  # Breaking news
remaining = 75%        # Analysis + Trends
```

#### HTML Generation:
- Template-based rendering
- Impact score color coding
- Professional styling
- Mobile responsive

**Výstup**: HTML newsletter + metadata

### **STEP 6: MULTI-PLATFORM PUBLISHING** 🚀
**Komponenta**: `GitHubPagesPublisher.publish_newsletter()`

#### Publishing Targets:
1. **GitHub Pages** (`docs/`)
   - Newsletter: `docs/newsletters/newsletter-{date}.html`
   - Index: `docs/index.html`
   - Dashboard: `docs/dashboard.html`
   - Sitemap: `docs/sitemap.xml`

2. **Legacy File** (`output/`)
   - Backup: `output/newsletter_{timestamp}.html`

### **STEP 7: EMAIL NOTIFICATION** 📬
**Komponenta**: `EmailNotifier.notify_newsletter_ready()`

```python
if Config.SMTP_SERVER and Config.ADMIN_EMAIL:
    send_email_notification()
else:
    logger.info("Email not configured")
```

### **STEP 8: METRICS & REPORTING** 📈
**Komponenty**:
- `MetricsCollector`: SQLite databáze
- `ai_cost_controller.get_cost_report()`
- `pipeline_tracker.track_pipeline_success()`

#### Metriky:
- Articles collected/processed
- Deduplication rate
- AI costs (daily/monthly)
- Processing time
- Error rates

### **STEP 9: CLEANUP** 🧹
**Komponenta**: `CleanupManager.run_full_cleanup()`

- Retention: 30 dní
- Čistí: logs, output, old newsletters
- Database pruning
- Pouze v production mode

---

## 🛡️ ERROR HANDLING & RESILIENCE

### **Circuit Breakers**
```python
CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=3
)
```

### **Retry Logic**
```python
@retry_on_error(
    max_retries=3,
    backoff_factor=2.0,
    jitter=True
)
```

### **Graceful Degradation**
```python
if degradation_manager.should_skip_operation():
    use_fallback_or_skip()
```

### **Health Monitoring**
- Continuous health checks
- Auto-recovery attempts
- Alert generation on failures

---

## 📊 PERFORMANCE CHARAKTERISTIKY

### **Typické Časy Běhu**:
- Collection: ~7-10 sekund
- Processing: ~25-30 sekund
- AI Analysis: ~5-15 sekund
- Publishing: ~2-5 sekund
- **CELKEM: ~45-60 sekund**

### **Resource Usage**:
- Memory: ~200-300 MB
- CPU: 1-2 cores během collection
- Network: ~10-20 MB download
- AI tokens: ~8000-15000 per run

### **Success Rates**:
- Pipeline success: ~98.5%
- Source availability: ~95%
- AI fallback rate: ~5%

---

## 🔐 SECURITY & COMPLIANCE

### **API Key Management**:
- GitHub Secrets pro production
- .env file pro development
- Žádné klíče v kódu

### **SSL/TLS**:
⚠️ **KNOWN ISSUE**: Web scraper má `CERT_NONE` (line 121)
- Důvod: Některé zdroje mají expired certs
- Risk: MITM attacks (nízké pro trusted sources)
- TODO: Implementovat per-source SSL config

### **Data Privacy**:
- Žádné osobní údaje
- Pouze veřejné zpravodajské články
- 30denní retention policy

---

## 🚨 MONITORING & ALERTING

### **GitHub Actions**:
- Issue creation on failure
- Artifact retention: 30 dní
- Email notifications (pokud nakonfigurováno)

### **Logging**:
```python
Structured logging s:
- Correlation IDs
- Pipeline stages
- Error categories
- Performance metrics
```

### **Dashboard** (`docs/dashboard.html`):
- Collection statistics
- Processing metrics
- AI cost tracking
- Error trends

---

## 🔧 TROUBLESHOOTING GUIDE

### **Časté Problémy**:

1. **"Insufficient articles collected"**
   - Check source health
   - Verify network connectivity
   - Review RSS feed availability

2. **"AI budget exceeded"**
   - Check daily/monthly limits
   - Review cost_controller logs
   - Consider mock mode

3. **"Newsletter already exists"**
   - Normal behavior (duplicate prevention)
   - Check if manual cleanup needed

4. **SSL Certificate Errors**
   - Known issue with some sources
   - Currently bypassed with CERT_NONE
   - Monitor for security updates

---

## 📚 DEPENDENCIES & INTEGRATIONS

### **External Services**:
- Anthropic Claude API
- GitHub Pages hosting
- SMTP server (optional)
- 26 news sources (RSS/Web)

### **Key Libraries**:
- `anthropic`: Claude AI client
- `beautifulsoup4`: Web scraping
- `feedparser`: RSS parsing
- `requests`: HTTP client
- `sqlite3`: Metrics storage

---

## 🎯 CONFIGURATION MATRIX

| Variable | Production | Development | Test |
|----------|------------|-------------|------|
| DRY_RUN | false | true | true |
| AI_MAX_TOKENS | 8000 | 4000 | 1000 |
| CLEANUP_ENABLED | true | false | false |
| LOG_LEVEL | INFO | DEBUG | DEBUG |
| MAX_RETRIES | 3 | 2 | 1 |

---

## 📈 FUTURE IMPROVEMENTS

### **Plánované**:
- [ ] Substack integration
- [ ] Per-source SSL configuration
- [ ] Real-time monitoring dashboard
- [ ] A/B testing for AI prompts
- [ ] User personalization

### **V Úvaze**:
- [ ] Multiple AI providers (Gemini backup)
- [ ] Semantic deduplication
- [ ] Sentiment analysis
- [ ] Multi-language support
- [ ] API endpoint pro external consumers

---

**Poslední aktualizace**: 2025-09-03
**Verze dokumentace**: 1.0.0