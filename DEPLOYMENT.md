# Deployment Guide

## Production Deployment Steps

### 1. Repository Setup
1. Fork or clone the repository
2. Ensure all dependencies are installed: `pip install -r requirements.txt`

### 2. API Keys Configuration
Add the following secrets to your GitHub repository:

**Required for AI Analysis:**
- `ANTHROPIC_API_KEY`: Your Claude API key from Anthropic

**Required for Publishing:**
- `SUBSTACK_API_KEY`: Your Substack API key
- `SUBSTACK_PUBLICATION_ID`: Your Substack publication ID

### 3. GitHub Actions Setup
1. Go to repository Settings → Actions → General
2. Enable "Allow all actions and reusable workflows"
3. The workflow will run automatically daily at 6:00 UTC

### 4. Manual Testing
Before production, test the system:

```bash
# Test data collection
python test_simple_collection.py

# Test complete pipeline (dry run)
python test_complete_pipeline.py

# Test with real API keys (set DRY_RUN=false in .env)
python src/main_pipeline.py
```

### 5. Monitoring
- Check GitHub Actions tab for daily execution status
- Review artifacts for generated newsletters and logs
- Monitor for automatically created issues on failures

## Performance Expectations

- **Collection**: 400-500 articles in 5-10 seconds
- **Processing**: 400+ articles processed in 20-30 seconds
- **Total Runtime**: 30-45 seconds end-to-end
- **Success Rate**: 95%+ with graceful error handling

## Troubleshooting

### Common Issues
1. **Source failures**: Some RSS feeds may be temporarily unavailable - this is normal
2. **Network timeouts**: Retry logic handles temporary network issues
3. **API rate limits**: Built-in retry with exponential backoff

### Logs Location
- GitHub Actions: Check workflow artifacts
- Local testing: `logs/` directory

## Scaling Considerations

- Current setup handles 19 sources efficiently
- Can be extended to 50+ sources with minimal changes
- Consider rate limiting for larger source lists
- Monitor API usage for Claude and Substack
