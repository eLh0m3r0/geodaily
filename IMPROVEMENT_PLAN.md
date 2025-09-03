# 🚀 GeoPolitical Daily - Komplexní plán vylepšení

## 🔴 KRITICKÉ PROBLÉMY K OKAMŽITÉ OPRAVĚ

### 1. Connection Pool Logger Bug
**Problém**: `name 'logger' is not defined` v `src/performance/connection_pool.py:166`
- Chyba způsobuje selhání VŠECH HTTPS zdrojů kromě BBC
- Pouze BBC funguje protože používá HTTP (ne HTTPS)

**Řešení**:
```python
# Řádek 166 - změnit z:
logger.debug("Making HTTPS request via connection pool",
# Na:
self.logger.debug("Making HTTPS request via connection pool",
```

### 2. Chybějící perzistence AI dat
**Problém**: Neukládají se data odeslaná do AI, nelze sledovat co AI dostává

**Řešení**: Implementovat AI Data Archive systém (viz níže)

---

## 📊 KOMPLEXNÍ SYSTÉM PRO SLEDOVÁNÍ AI DAT

### AI Data Archive System

#### 1. Struktura ukládání dat
```
geodaily/
├── ai_archive/
│   ├── {date}/
│   │   ├── run_{timestamp}/
│   │   │   ├── metadata.json         # Metadata o běhu
│   │   │   ├── collected_articles.json # Všechny sebrané články
│   │   │   ├── clusters/             # Clustery před AI
│   │   │   │   ├── cluster_001.json
│   │   │   │   └── cluster_002.json
│   │   │   ├── ai_requests/          # Co šlo do AI
│   │   │   │   ├── request_001.json
│   │   │   │   └── request_002.json
│   │   │   ├── ai_responses/         # Odpovědi z AI
│   │   │   │   ├── response_001.json
│   │   │   │   └── response_002.json
│   │   │   └── final_newsletter.json # Finální newsletter
```

#### 2. Implementace - nový soubor `src/archiver/ai_data_archiver.py`
```python
"""
AI Data Archiver - Comprehensive data persistence for AI analysis tracking.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from ..models import Article, ArticleCluster, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)


class AIDataArchiver:
    """Archives all data flowing through the AI analysis pipeline."""
    
    def __init__(self):
        self.archive_base = Path(Config.AI_ARCHIVE_PATH or "ai_archive")
        self.current_run_id = None
        self.current_run_path = None
        
    def start_new_run(self) -> str:
        """Initialize a new archive run."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_folder = datetime.now().strftime("%Y-%m-%d")
        
        self.current_run_id = f"run_{timestamp}"
        self.current_run_path = self.archive_base / date_folder / self.current_run_id
        self.current_run_path.mkdir(parents=True, exist_ok=True)
        
        # Create metadata
        metadata = {
            "run_id": self.current_run_id,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "ai_provider": Config.AI_PROVIDER,
                "ai_model": Config.AI_MODEL,
                "ai_max_tokens": Config.AI_MAX_TOKENS,
                "dry_run": Config.DRY_RUN
            },
            "environment": {
                "github_action": os.getenv("GITHUB_ACTION"),
                "github_run_id": os.getenv("GITHUB_RUN_ID"),
                "github_sha": os.getenv("GITHUB_SHA")
            }
        }
        
        self._save_json("metadata.json", metadata)
        logger.info(f"Archive run started: {self.current_run_id}")
        return self.current_run_id
    
    def archive_collected_articles(self, articles: List[Article]):
        """Archive all collected articles."""
        articles_data = []
        for article in articles:
            articles_data.append({
                "source": article.source,
                "source_category": article.source_category.value,
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "published_date": article.published_date.isoformat() if article.published_date else None,
                "author": article.author,
                "relevance_score": getattr(article, 'relevance_score', None)
            })
        
        self._save_json("collected_articles.json", {
            "total_articles": len(articles),
            "timestamp": datetime.now().isoformat(),
            "articles": articles_data
        })
        
        # Create source distribution summary
        source_dist = {}
        for article in articles:
            source = article.source
            if source not in source_dist:
                source_dist[source] = 0
            source_dist[source] += 1
        
        self._save_json("source_distribution.json", source_dist)
        logger.info(f"Archived {len(articles)} collected articles")
    
    def archive_cluster(self, cluster: ArticleCluster, cluster_index: int):
        """Archive a cluster before AI analysis."""
        cluster_data = {
            "cluster_index": cluster_index,
            "cluster_score": cluster.cluster_score,
            "main_article": {
                "title": cluster.main_article.title,
                "source": cluster.main_article.source,
                "url": cluster.main_article.url,
                "summary": cluster.main_article.summary[:500]  # First 500 chars
            },
            "articles_count": len(cluster.articles),
            "articles": [
                {
                    "title": art.title,
                    "source": art.source,
                    "url": art.url
                }
                for art in cluster.articles[:10]  # First 10 articles
            ]
        }
        
        clusters_dir = self.current_run_path / "clusters"
        clusters_dir.mkdir(exist_ok=True)
        
        self._save_json(f"clusters/cluster_{cluster_index:03d}.json", cluster_data)
    
    def archive_ai_request(self, prompt: str, articles_summary: str, 
                          cluster_index: int, main_article_title: str):
        """Archive what's being sent to AI."""
        request_data = {
            "cluster_index": cluster_index,
            "timestamp": datetime.now().isoformat(),
            "main_article_title": main_article_title,
            "prompt_template": prompt[:500],  # First 500 chars of template
            "articles_summary": articles_summary,
            "full_prompt": prompt,
            "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_length": len(prompt),
            "estimated_tokens": len(prompt.split()) * 1.3
        }
        
        requests_dir = self.current_run_path / "ai_requests"
        requests_dir.mkdir(exist_ok=True)
        
        filename = f"ai_requests/request_{cluster_index:03d}.json"
        self._save_json(filename, request_data)
        
        logger.info(f"Archived AI request for cluster {cluster_index}")
        return filename
    
    def archive_ai_response(self, response_text: str, analysis: Optional[AIAnalysis], 
                           cluster_index: int, cost: float, tokens: int):
        """Archive AI response."""
        response_data = {
            "cluster_index": cluster_index,
            "timestamp": datetime.now().isoformat(),
            "raw_response": response_text,
            "response_length": len(response_text),
            "tokens_used": tokens,
            "cost": cost,
            "parsed_analysis": None
        }
        
        if analysis:
            response_data["parsed_analysis"] = {
                "story_title": analysis.story_title,
                "content_type": analysis.content_type.value,
                "why_important": analysis.why_important,
                "what_overlooked": analysis.what_overlooked,
                "prediction": analysis.prediction,
                "impact_score": analysis.impact_score,
                "urgency_score": analysis.urgency_score,
                "scope_score": analysis.scope_score,
                "novelty_score": analysis.novelty_score,
                "credibility_score": analysis.credibility_score,
                "confidence": analysis.confidence
            }
        
        responses_dir = self.current_run_path / "ai_responses"
        responses_dir.mkdir(exist_ok=True)
        
        self._save_json(f"ai_responses/response_{cluster_index:03d}.json", response_data)
        logger.info(f"Archived AI response for cluster {cluster_index}")
    
    def archive_final_newsletter(self, newsletter_html: str, analyses: List[AIAnalysis]):
        """Archive the final newsletter."""
        newsletter_data = {
            "timestamp": datetime.now().isoformat(),
            "stories_count": len(analyses),
            "stories": [
                {
                    "title": analysis.story_title,
                    "content_type": analysis.content_type.value,
                    "impact_score": analysis.impact_score,
                    "sources_count": len(analysis.sources)
                }
                for analysis in analyses
            ],
            "html_length": len(newsletter_html)
        }
        
        self._save_json("final_newsletter.json", newsletter_data)
        
        # Also save HTML
        html_path = self.current_run_path / "final_newsletter.html"
        html_path.write_text(newsletter_html)
        
        logger.info("Archived final newsletter")
    
    def create_run_summary(self):
        """Create a summary of the entire run."""
        summary = {
            "run_id": self.current_run_id,
            "timestamp": datetime.now().isoformat(),
            "files_created": [],
            "statistics": {}
        }
        
        # List all created files
        for file_path in self.current_run_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(self.current_run_path)
                summary["files_created"].append({
                    "path": str(relative_path),
                    "size_bytes": file_path.stat().st_size
                })
        
        # Calculate statistics
        collected_file = self.current_run_path / "collected_articles.json"
        if collected_file.exists():
            with open(collected_file) as f:
                data = json.load(f)
                summary["statistics"]["total_articles_collected"] = data.get("total_articles", 0)
        
        clusters_dir = self.current_run_path / "clusters"
        if clusters_dir.exists():
            summary["statistics"]["total_clusters"] = len(list(clusters_dir.glob("*.json")))
        
        ai_requests_dir = self.current_run_path / "ai_requests"
        if ai_requests_dir.exists():
            summary["statistics"]["ai_requests_made"] = len(list(ai_requests_dir.glob("*.json")))
            
            # Calculate total cost
            total_cost = 0
            responses_dir = self.current_run_path / "ai_responses"
            if responses_dir.exists():
                for response_file in responses_dir.glob("*.json"):
                    with open(response_file) as f:
                        response_data = json.load(f)
                        total_cost += response_data.get("cost", 0)
            summary["statistics"]["total_ai_cost"] = total_cost
        
        self._save_json("run_summary.json", summary)
        logger.info("Created run summary")
        
        return summary
    
    def _save_json(self, filename: str, data: Any):
        """Save data as JSON file."""
        file_path = self.current_run_path / filename
        file_path.parent.mkdir(exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def cleanup_old_archives(self, days_to_keep: int = 30):
        """Clean up old archive folders."""
        import shutil
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for date_folder in self.archive_base.iterdir():
            if date_folder.is_dir():
                try:
                    folder_date = datetime.strptime(date_folder.name, "%Y-%m-%d")
                    if folder_date < cutoff_date:
                        shutil.rmtree(date_folder)
                        logger.info(f"Deleted old archive: {date_folder.name}")
                except ValueError:
                    # Not a date folder, skip
                    continue


# Global instance
ai_archiver = AIDataArchiver()
```

---

## 📈 MONITORING & DASHBOARD SYSTEM

### 1. Real-time Debug Dashboard - `src/dashboard/debug_dashboard.py`
```python
"""
Debug Dashboard Generator - Creates HTML dashboard for monitoring.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class DebugDashboard:
    """Generate comprehensive debug dashboard."""
    
    def __init__(self, archive_path: str = "ai_archive"):
        self.archive_path = Path(archive_path)
        
    def generate_dashboard(self, date: str = None) -> str:
        """Generate HTML dashboard for a specific date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        date_path = self.archive_path / date
        if not date_path.exists():
            return self._generate_empty_dashboard(date)
        
        # Collect all runs for the date
        runs = []
        for run_folder in sorted(date_path.iterdir()):
            if run_folder.is_dir() and run_folder.name.startswith("run_"):
                run_data = self._analyze_run(run_folder)
                runs.append(run_data)
        
        # Generate HTML
        html = self._build_dashboard_html(date, runs)
        
        # Save dashboard
        dashboard_path = Path("docs") / "dashboards" / f"dashboard_{date}.html"
        dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        dashboard_path.write_text(html)
        
        return str(dashboard_path)
    
    def _analyze_run(self, run_path: Path) -> Dict:
        """Analyze a single run."""
        analysis = {
            "run_id": run_path.name,
            "timestamp": None,
            "articles_collected": 0,
            "sources_distribution": {},
            "clusters_created": 0,
            "ai_requests": 0,
            "ai_cost": 0,
            "stories_selected": 0,
            "errors": []
        }
        
        # Read metadata
        metadata_file = run_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                analysis["timestamp"] = metadata.get("timestamp")
        
        # Read collected articles
        articles_file = run_path / "collected_articles.json"
        if articles_file.exists():
            with open(articles_file) as f:
                data = json.load(f)
                analysis["articles_collected"] = data.get("total_articles", 0)
        
        # Read source distribution
        dist_file = run_path / "source_distribution.json"
        if dist_file.exists():
            with open(dist_file) as f:
                analysis["sources_distribution"] = json.load(f)
        
        # Count clusters
        clusters_dir = run_path / "clusters"
        if clusters_dir.exists():
            analysis["clusters_created"] = len(list(clusters_dir.glob("*.json")))
        
        # Analyze AI requests and responses
        requests_dir = run_path / "ai_requests"
        responses_dir = run_path / "ai_responses"
        
        if requests_dir.exists():
            analysis["ai_requests"] = len(list(requests_dir.glob("*.json")))
        
        if responses_dir.exists():
            for response_file in responses_dir.glob("*.json"):
                with open(response_file) as f:
                    response = json.load(f)
                    analysis["ai_cost"] += response.get("cost", 0)
                    if response.get("parsed_analysis"):
                        analysis["stories_selected"] += 1
        
        return analysis
    
    def _build_dashboard_html(self, date: str, runs: List[Dict]) -> str:
        """Build the dashboard HTML."""
        # Create visualizations
        figures_html = self._create_visualizations(runs)
        
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>GeoPolitical Daily Debug Dashboard - {date}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .header {{
            background: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .metric-label {{
            color: #7f8c8d;
            margin-top: 5px;
        }}
        .run-details {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .source-badge {{
            display: inline-block;
            padding: 5px 10px;
            margin: 3px;
            background: #3498db;
            color: white;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        .error-box {{
            background: #fee;
            border-left: 4px solid #f44;
            padding: 10px;
            margin: 10px 0;
        }}
        .success-indicator {{
            color: #27ae60;
            font-weight: bold;
        }}
        .warning-indicator {{
            color: #f39c12;
            font-weight: bold;
        }}
        .error-indicator {{
            color: #e74c3c;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 GeoPolitical Daily Debug Dashboard</h1>
        <p>Date: {date} | Runs: {len(runs)}</p>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-value">{sum(r['articles_collected'] for r in runs)}</div>
            <div class="metric-label">Total Articles Collected</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{sum(r['clusters_created'] for r in runs)}</div>
            <div class="metric-label">Total Clusters Created</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{sum(r['ai_requests'] for r in runs)}</div>
            <div class="metric-label">AI Requests Made</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${sum(r['ai_cost'] for r in runs):.4f}</div>
            <div class="metric-label">Total AI Cost</div>
        </div>
    </div>
    
    {figures_html}
    
    <h2>📊 Individual Run Details</h2>
    {self._generate_run_details_html(runs)}
    
    <script>
        // Auto-refresh every 60 seconds
        setTimeout(() => location.reload(), 60000);
    </script>
</body>
</html>
'''
        return html
    
    def _create_visualizations(self, runs: List[Dict]) -> str:
        """Create Plotly visualizations."""
        if not runs:
            return "<p>No data to visualize</p>"
        
        # Aggregate source distribution
        all_sources = {}
        for run in runs:
            for source, count in run['sources_distribution'].items():
                all_sources[source] = all_sources.get(source, 0) + count
        
        # Sort by count
        sorted_sources = sorted(all_sources.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Create bar chart
        fig = go.Figure([go.Bar(
            x=[s[0] for s in sorted_sources],
            y=[s[1] for s in sorted_sources],
            marker_color='#3498db'
        )])
        
        fig.update_layout(
            title="Top 20 News Sources",
            xaxis_title="Source",
            yaxis_title="Articles",
            height=400,
            showlegend=False
        )
        
        # Convert to HTML
        import plotly.io as pio
        chart_html = pio.to_html(fig, include_plotlyjs=False, div_id="sources-chart")
        
        return f'<div class="run-details">{chart_html}</div>'
    
    def _generate_run_details_html(self, runs: List[Dict]) -> str:
        """Generate HTML for individual run details."""
        html = ""
        
        for run in runs:
            status_class = "success-indicator" if run['stories_selected'] >= 3 else "warning-indicator"
            
            sources_html = ""
            for source, count in sorted(run['sources_distribution'].items(), 
                                       key=lambda x: x[1], reverse=True)[:10]:
                sources_html += f'<span class="source-badge">{source}: {count}</span>'
            
            html += f'''
            <div class="run-details">
                <h3>Run: {run['run_id']}</h3>
                <p>Timestamp: {run['timestamp']}</p>
                <p class="{status_class}">
                    Status: {run['stories_selected']} stories selected
                </p>
                <p>
                    Articles: {run['articles_collected']} | 
                    Clusters: {run['clusters_created']} | 
                    AI Cost: ${run['ai_cost']:.4f}
                </p>
                <p><strong>Top Sources:</strong></p>
                <div>{sources_html}</div>
            </div>
            '''
        
        return html
```

---

## 🔧 INTEGRACE DO PIPELINE

### Úpravy v `src/main_pipeline.py`

```python
# Přidat na začátek importů:
from .archiver.ai_data_archiver import ai_archiver
from .dashboard.debug_dashboard import DebugDashboard

# V run_complete_pipeline(), hned po start_time:
# Inicializace archiveru
ai_archiver.start_new_run()

# Po Step 2 (Collection):
# Archive collected articles
ai_archiver.archive_collected_articles(raw_articles)

# V Step 4 (AI Analysis), upravit ClaudeAnalyzer:
```

### Úpravy v `src/ai/claude_analyzer.py`

```python
# Přidat import
from ..archiver.ai_data_archiver import ai_archiver

# V metodě analyze_clusters, před voláním API:
for i, cluster in enumerate(clusters[:target_stories]):
    # Archive cluster
    ai_archiver.archive_cluster(cluster, i)
    
    # ... existing code ...

# V metodě _analyze_single_cluster_with_api, před voláním API:
# Archive the request
ai_archiver.archive_ai_request(
    prompt=prompt,
    articles_summary=articles_summary,
    cluster_index=cluster_index,  # Need to pass this in
    main_article_title=main_article.title
)

# Po obdržení odpovědi:
# Archive the response
ai_archiver.archive_ai_response(
    response_text=analysis_text,
    analysis=analysis,  # After parsing
    cluster_index=cluster_index,
    cost=total_cost,
    tokens=total_tokens
)
```

---

## 🚀 GITHUB ACTIONS ÚPRAVY

### Upravit `.github/workflows/daily_newsletter.yml`

```yaml
# Přidat environment variable pro archivaci
- name: Set environment variables
  run: |
    # ... existing variables ...
    echo "AI_ARCHIVE_ENABLED=true" >> $GITHUB_ENV
    echo "AI_ARCHIVE_PATH=ai_archive" >> $GITHUB_ENV
    echo "DEBUG_DASHBOARD=true" >> $GITHUB_ENV

# Přidat krok pro generování dashboardu
- name: Generate Debug Dashboard
  if: success()
  run: |
    python -c "
    from src.dashboard.debug_dashboard import DebugDashboard
    dashboard = DebugDashboard()
    path = dashboard.generate_dashboard()
    print(f'Dashboard generated: {path}')
    "

# Upravit artifact upload - přidat ai_archive
- name: Upload newsletter artifacts
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: newsletter-${{ github.run_number }}
    path: |
      output/*.html
      docs/**/*
      logs/*.log
      ai_archive/**/*    # Přidat archiv
    retention-days: 30
```

---

## 📝 CONFIG ÚPRAVY

### Přidat do `src/config.py`:

```python
# AI Archive Configuration
AI_ARCHIVE_ENABLED = os.getenv("AI_ARCHIVE_ENABLED", "true").lower() == "true"
AI_ARCHIVE_PATH = os.getenv("AI_ARCHIVE_PATH", "ai_archive")
AI_ARCHIVE_RETENTION_DAYS = int(os.getenv("AI_ARCHIVE_RETENTION_DAYS", "30"))

# Debug Dashboard
DEBUG_DASHBOARD_ENABLED = os.getenv("DEBUG_DASHBOARD", "true").lower() == "true"
```

---

## 🎯 RYCHLÉ OPRAVY (HOTFIX)

### 1. Connection Pool - okamžitá oprava
```bash
# File: src/performance/connection_pool.py
# Line 166 - změnit:
logger.debug  ->  self.logger.debug
```

### 2. Přidat debug logging do produkce
```yaml
# .github/workflows/daily_newsletter.yml
# Změnit LOG_LEVEL na DEBUG pro detailní logy:
echo "LOG_LEVEL=DEBUG" >> $GITHUB_ENV
```

---

## 📊 VÝHODY TOHOTO ŘEŠENÍ

1. **Kompletní trasovatelnost** - vidíš přesně co šlo do AI
2. **Debug dashboard** - vizuální přehled všech běhů
3. **Automatická archivace** - vše se ukládá pro pozdější analýzu
4. **Cost tracking** - přesné sledování nákladů
5. **Source distribution** - vidíš které zdroje fungují/nefungují
6. **Error tracking** - všechny chyby jsou zaznamenány
7. **Performance metrics** - měření výkonu jednotlivých částí

---

## 🚦 PRIORITIZACE IMPLEMENTACE

1. **OKAMŽITĚ**: Opravit connection pool bug (1 řádek)
2. **VYSOKÁ**: Implementovat AI Data Archiver
3. **STŘEDNÍ**: Vytvořit Debug Dashboard
4. **NÍZKÁ**: Další vylepšení a optimalizace

---

## 📈 MONITORING METRICS

Po implementaci budeš mít přehled o:
- Kolik článků se sbírá z každého zdroje
- Které zdroje selhávají a proč
- Co přesně jde do AI (kompletní prompty)
- Jak AI odpovídá (surové odpovědi)
- Kolik to stojí (přesné náklady)
- Trendy v čase (historická data)

Tento systém ti dá **kompletní kontrolu** nad celým pipeline!