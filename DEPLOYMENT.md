# Deployment Guide

## Production Deployment Steps

### 1. Repository Setup
1. Fork or clone the repository
2. Ensure all dependencies are installed: `pip install -r requirements.txt`

### 2. Environment Configuration

#### For Local Development
1. Copy `.env.example` to `.env`
2. Configure the following environment variables in `.env`:

**Required for AI Analysis:**
- `ANTHROPIC_API_KEY`: Your Claude API key from Anthropic
- `GEMINI_API_KEY`: Your Gemini API key (optional fallback)

**Required for Publishing:**
- `SUBSTACK_API_KEY`: Your Substack API key
- `SUBSTACK_PUBLICATION_ID`: Your Substack publication ID

**Newsletter Configuration:**
- `NEWSLETTER_TITLE`: Your newsletter title
- `NEWSLETTER_AUTHOR`: Your name
- `NEWSLETTER_FROM_EMAIL`: Your email for notifications

**Development Settings:**
- `DRY_RUN=true`: Enable dry run mode for testing
- `DEBUG=true`: Enable debug logging
- `LOG_LEVEL=DEBUG`: Set debug log level

#### For Production (GitHub Pages/GitHub Actions)
Instead of using `.env` file, configure GitHub Secrets in your repository:

1. Go to your GitHub repository → Settings → Secrets and variables → Actions
2. Add the following secrets:

**Required Secrets:**
- `ANTHROPIC_API_KEY`: Your Claude API key
- `SUBSTACK_API_KEY`: Your Substack API key
- `SUBSTACK_PUBLICATION_ID`: Your Substack publication ID

**Optional Secrets:**
- `GEMINI_API_KEY`: Your Gemini API key (fallback)
- `NEWSLETTER_TITLE`: Your newsletter title
- `NEWSLETTER_AUTHOR`: Your name
- `NEWSLETTER_FROM_EMAIL`: Your email for notifications
- `ADMIN_EMAIL`: Admin email for notifications
- `SMTP_SERVER`: SMTP server for email notifications
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_USERNAME`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `SMTP_FROM_EMAIL`: From email for SMTP

**Production Settings (configure as repository variables or in workflow):**
- `DRY_RUN=false`: Enable actual publishing
- `DEBUG=false`: Disable debug logging
- `LOG_LEVEL=INFO`: Set appropriate log level

**Security Note:** Never commit `.env` files containing real API keys to version control. The `.env` file is now in `.gitignore` to prevent accidental commits.

### 3. Automated Scheduling Setup
The system is configured to run automatically using cron:

```bash
# Verify cron job is set (runs daily at 6:00 UTC)
crontab -l

# Expected output:
# 0 6 * * * TZ=UTC cd /Users/vaclav/Documents/augment-projects/geodaily && PYTHONPATH=src python3 src/main_pipeline.py
```

If not set, configure it manually:
```bash
echo "0 6 * * * TZ=UTC cd /path/to/project && PYTHONPATH=src python3 src/main_pipeline.py" | crontab -
```

### 4. Manual Testing
Before production, test the system:

```bash
# Test all improvements
PYTHONPATH=src python3 test_improvements.py

# Test data collection
PYTHONPATH=src python3 test_simple_collection.py

# Test complete pipeline (dry run)
PYTHONPATH=src python3 test_complete_pipeline.py

# Test with real API keys (set DRY_RUN=false in .env)
PYTHONPATH=src python3 src/main_pipeline.py
```

### 5. Monitoring and Health Checks
- **Logs**: Check `logs/` directory for structured logs
- **Metrics**: Database metrics in `data/metrics.db`
- **Health Monitoring**: Automatic source health tracking
- **Cost Control**: AI usage monitoring and budget alerts
- **Performance**: Connection pooling and optimization metrics

## System Improvements

### Latest Features
- **AI Cost Control**: Automatic budget monitoring and usage optimization
- **Content Quality Validation**: Advanced filtering for high-quality articles
- **Source Health Monitoring**: Automatic detection of failing sources
- **Performance Optimizations**: Connection pooling and batch processing
- **Resilience Framework**: Circuit breakers, retry mechanisms, graceful degradation
- **Personalization Engine**: User-specific content recommendations
- **Enhanced Logging**: Structured logging with metrics integration

### Performance Expectations
- **Collection**: 400-500 articles in 5-10 seconds
- **Processing**: 400+ articles processed in 20-30 seconds with quality validation
- **AI Analysis**: 4 stories selected with cost optimization
- **Total Runtime**: 45-60 seconds end-to-end
- **Success Rate**: 98%+ with comprehensive error handling

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure `PYTHONPATH=src` is set when running scripts
2. **Source Failures**: Automatic health monitoring handles unavailable feeds
3. **Network Timeouts**: Enhanced retry logic with exponential backoff
4. **API Rate Limits**: Built-in rate limiting and cost control
5. **Memory Issues**: Connection pooling prevents resource exhaustion

### Logs Location
- Local execution: `logs/` directory with structured JSON logs
- Database metrics: `data/metrics.db`
- Newsletter outputs: `docs/newsletters/` directory

### Health Monitoring
- Source health scores tracked automatically
- Circuit breakers prevent cascade failures
- Graceful degradation maintains partial functionality
- Recovery procedures for system restoration

## Scaling Considerations

- Current setup handles 19+ sources efficiently
- Can be extended to 100+ sources with connection pooling
- AI cost optimization prevents budget overruns
- Performance monitoring identifies bottlenecks
- Modular architecture supports easy extension

## Production Checklist

- [ ] Environment variables configured with real API keys
- [ ] DRY_RUN=false in production
- [ ] Cron job scheduled for 6:00 UTC daily
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Test suite passes: `PYTHONPATH=src python3 test_improvements.py`
- [ ] Log directory permissions set correctly
- [ ] Database initialized: `data/metrics.db`
- [ ] Newsletter directory exists: `docs/newsletters/`
