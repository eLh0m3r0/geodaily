# Production Setup Guide

This guide will help you deploy the Geopolitical Daily newsletter system to production in **under 10 minutes**.

## 🚀 Quick Start (5 Minutes)

### Step 1: Fork & Enable Actions
1. Fork this repository to your GitHub account
2. Go to **Settings → Actions → General**
3. Enable "Allow all actions and reusable workflows"

### Step 2: Configure GitHub Pages
1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** 
4. Folder: **/ (root)**

### Step 3: Add Required Secrets
Go to **Settings → Secrets and Variables → Actions** and add:

**Required:**
```
ANTHROPIC_API_KEY=your_claude_api_key_here
```

**Optional (for email notifications):**
```
ADMIN_EMAIL=your@email.com
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=your_app_password
```

### Step 4: Test Run
1. Go to **Actions → Daily Geopolitical Newsletter**
2. Click **Run workflow**
3. Set **dry_run** to `true`
4. Click **Run workflow**

**✅ If successful, your newsletter site will be live at: `https://elh0m3r0.github.io/geodaily`**

---

## 🔧 Advanced Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | - | Claude AI API key |
| `AI_MODEL` | ❌ | `claude-sonnet-5` | AI model to use |
| `AI_MAX_TOKENS` | ❌ | `16000` | Max tokens per analysis |
| `AI_MAX_COST_PER_DAY` | ❌ | `2.0` | Daily cost limit ($) |
| `AI_MAX_COST_PER_MONTH` | ❌ | `30.0` | Monthly cost limit ($) |
| `ADMIN_EMAIL` | ❌ | - | Email for notifications |
| `SMTP_SERVER` | ❌ | - | SMTP server for emails |
| `DRY_RUN` | ❌ | `false` | Skip AI calls (testing) |

### Cost Control

The system is configured for ~$25-35/month cost:
- **AI Analysis**: ~$15-25/month (Claude Haiku)
- **Email Notifications**: ~$0-5/month
- **GitHub Actions**: Free (2000 minutes)

### Daily Workflow

1. **6:00 UTC**: GitHub Actions automatically runs
2. **6:02 UTC**: Newsletter published to GitHub Pages
3. **6:03 UTC**: Email notification sent

---


## 🛠️ Customization

### Adding News Sources
Edit `sources.json`:
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

### Changing Newsletter Style
- Edit CSS in `src/publishers/github_pages_publisher.py`
- Modify HTML templates in the same file
- Update branding/colors as needed

### Email Notifications
Configure SMTP settings in GitHub Secrets for automatic notifications when newsletters are ready.

---

## 🐛 Troubleshooting

### Common Issues

**❌ "No ANTHROPIC_API_KEY found"**
- Add your Claude API key to GitHub Secrets
- Get API key at: https://console.anthropic.com/

**❌ "GitHub Pages not deploying"**
- Check Settings → Pages is configured correctly
- Ensure Actions have write permissions
- Check Actions logs for deployment errors

**❌ "Pipeline failing in production"**
- Run with `dry_run: true` to test without API calls
- Check specific error messages in Actions logs
- Verify all news sources are accessible

**❌ "High API costs"**
- Reduce `AI_MAX_TOKENS` (default: 2000)
- Switch to cheaper model if needed
- Set lower `AI_MAX_COST_PER_DAY` limit

### Debug Mode
Set these environment variables for debugging:
```
DEBUG=true
LOG_LEVEL=DEBUG
```

### Testing Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Test collection only
python test_simple_collection.py

# Test full pipeline (dry run)
DRY_RUN=true python test_complete_pipeline.py
```

---

## 📈 Performance Metrics

**Expected Performance:**
- **Collection**: 400-500 articles in ~7 seconds
- **Processing**: ~20 seconds for deduplication/clustering
- **Total Pipeline**: ~30 seconds end-to-end
- **Success Rate**: >95% uptime

**Resource Usage:**
- **Memory**: <500MB peak usage
- **CPU**: <2 minutes compute time
- **Storage**: ~50MB per month (including archives)

---

## 🔒 Security Best Practices

1. **Never commit API keys** - Always use GitHub Secrets
2. **Review sources regularly** - Remove broken/suspicious feeds
3. **Monitor costs** - Set up Claude API spending alerts
4. **Check logs** - Review Actions logs for anomalies
5. **Update dependencies** - Keep packages current

---

## 📞 Support

**Getting Help:**
- Create an issue in this repository
- Check Actions logs for detailed error messages
- Review generated newsletters in `docs/` directory

**Contributing:**
- Fork and submit pull requests
- Add new news sources via `sources.json`
- Improve AI prompts in `src/ai/claude_analyzer.py`

---

## ✅ Production Checklist

Before going live:

- [ ] Fork repository to your account
- [ ] Add `ANTHROPIC_API_KEY` to Secrets
- [ ] Enable GitHub Pages
- [ ] Test with `dry_run: true`
- [ ] Configure email notifications (optional)
- [ ] Customize branding/styling
- [ ] Test complete workflow end-to-end

**🎉 Ready for Production!**

Your automated geopolitical newsletter will run daily at 6:00 UTC, generating professional analysis of underreported strategic developments.