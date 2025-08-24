# Geopolitical Daily 📰

> Automated geopolitical newsletter system powered by AI analysis

An intelligent newsletter system that collects news from diverse sources, analyzes underreported geopolitical developments using Claude AI, and publishes professional newsletters across multiple platforms.

## 🚀 Quick Start

**Get your newsletter running in 5 minutes:**

1. **Fork this repository**
2. **Add your Claude API key** to GitHub Secrets (`ANTHROPIC_API_KEY`)
3. **Enable GitHub Pages** in repository settings
4. **Run the workflow** with `dry_run: true` to test

**→ [Complete Setup Guide](SETUP.md)**

## ✨ Features

- **🤖 AI-Powered Analysis**: Claude AI identifies underreported stories with strategic significance
- **📊 Multi-Source Collection**: Aggregates from think tanks, regional outlets, and specialized publications
- **🌐 Multi-Platform Publishing**: GitHub Pages + Substack-ready exports
- **📧 Smart Notifications**: Email alerts when newsletters are ready
- **💰 Cost Control**: Built-in spending limits (~$25-35/month)
- **⚡ Fast Processing**: 400+ articles analyzed in ~30 seconds

## 📖 What It Does

Every day at 6:00 UTC, the system:

1. **Collects** 400-500 articles from curated news sources
2. **Analyzes** content using Claude AI for strategic significance
3. **Generates** professional newsletters in multiple formats
4. **Publishes** to GitHub Pages automatically
5. **Exports** Substack-ready content for manual publishing
6. **Notifies** you via email when everything is ready

## 🎯 Target Audience

- Policy analysts and decision-makers
- Intelligence professionals
- Academic researchers
- Strategic consultants
- Anyone needing deep geopolitical insights

## 📰 Newsletter Format

Each daily edition contains 3-4 carefully selected stories with:

- **Why This Matters** (60-80 words): Strategic significance and implications
- **What Others Are Missing** (30-40 words): Overlooked angles and dimensions  
- **What to Watch** (20-30 words): Predicted developments and indicators
- **Impact Score** (1-10): Relative importance for decision-makers
- **Sources**: Links to original reporting

## 🏗️ Architecture

```
News Sources → Collection → AI Analysis → Publishing
     ↓              ↓           ↓           ↓
  RSS Feeds    Deduplication  Claude AI   GitHub Pages
  Web Scraping   Clustering   Analysis    Substack Export
     ↓              ↓           ↓           ↓
   476 articles → 4-8 stories → Newsletter → Email Alert
```

## 📊 Performance

- **Collection**: 476 articles in ~7 seconds
- **Processing**: ~20 seconds total pipeline
- **Success Rate**: >95% uptime
- **Cost**: ~$25-35/month (AI + email)
- **Memory**: <500MB peak usage

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | - | Claude AI API key |
| `AI_MODEL` | ❌ | `claude-3-haiku-20240307` | AI model |
| `AI_MAX_COST_PER_DAY` | ❌ | `2.0` | Daily cost limit ($) |
| `ADMIN_EMAIL` | ❌ | - | Notification email |
| `DRY_RUN` | ❌ | `false` | Test mode (no API calls) |

### News Sources

Edit `sources.json` to customize news sources:

```json
{
  "tier1_sources": [
    {
      "name": "Your RSS Source",
      "url": "https://example.com/rss",
      "category": "mainstream",
      "weight": 0.8
    }
  ]
}
```

## 📝 Sample Output

**Today's Newsletter:**
- **4 strategic stories** analyzed
- **Average impact score**: 8.0/10
- **Focus areas**: China-US relations, Indo-Pacific strategy, Middle East dynamics
- **Formats**: HTML newsletter, Markdown export, RSS feed

[→ View Live Example](https://yourusername.github.io/geodaily)

## 🚀 Deployment

### GitHub Actions (Recommended)
- Zero-maintenance deployment
- Runs daily automatically
- Built-in error handling
- Free hosting via GitHub Pages

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Test collection
python test_simple_collection.py

# Test full pipeline (dry run)
DRY_RUN=true python test_complete_pipeline.py
```

## 📧 Publishing Workflow

1. **Automated**: Newsletter published to GitHub Pages
2. **Semi-automated**: Substack exports generated automatically
3. **Manual**: Copy-paste to Substack (2 minutes)
4. **Notification**: Email alert with publishing instructions

## 🔒 Security

- **API keys** stored in GitHub Secrets
- **Cost controls** prevent overspending
- **Source validation** ensures feed reliability
- **Error handling** prevents system failures

## 🐛 Troubleshooting

**Common Issues:**

- **"No ANTHROPIC_API_KEY found"** → Add API key to GitHub Secrets
- **"Pipeline failing"** → Run with `dry_run: true` to test
- **"High costs"** → Reduce `AI_MAX_TOKENS` or `AI_MAX_COST_PER_DAY`

[→ Full Troubleshooting Guide](SETUP.md#troubleshooting)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Test with `dry_run: true`
5. Submit a pull request

## 📁 Project Structure

```
geodaily/
├── src/                    # Core application code
│   ├── collectors/         # News collection (RSS, web scraping)
│   ├── ai/                # Claude AI analysis
│   ├── publishers/        # GitHub Pages, Substack exports
│   ├── notifications/     # Email alerts
│   └── utils/             # Shared utilities
├── docs/                  # GitHub Pages website
├── substack_exports/      # Ready-to-publish Substack content
├── output/               # Generated newsletters
├── sources.json          # News source configuration
└── .github/workflows/    # Automation workflows
```

## 🛠️ Technology Stack

- **Python 3.9+** - Core application
- **Claude AI (Anthropic)** - Content analysis
- **GitHub Actions** - Automation & deployment
- **GitHub Pages** - Website hosting
- **RSS/Web Scraping** - News collection
- **SMTP** - Email notifications

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🆘 Support

- **Issues**: Create a GitHub issue
- **Documentation**: See [SETUP.md](SETUP.md)
- **Examples**: Check `docs/` directory

---

**🎯 Ready to launch your geopolitical intelligence newsletter?**

[**→ Start Setup Now**](SETUP.md) | [**→ View Live Demo**](https://yourusername.github.io/geodaily)
