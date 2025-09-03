"""
Debug Dashboard Generator - Creates comprehensive HTML dashboards for monitoring.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import math
from collections import defaultdict, Counter

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.io as pio
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)


class DebugDashboard:
    """Generate comprehensive debug dashboards with rich visualizations."""
    
    def __init__(self, archive_path: str = None):
        self.archive_path = Path(archive_path or getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive'))
        # Use config-specified dashboard output path, fallback to docs/dashboards
        default_dashboard_path = getattr(Config, 'DASHBOARD_OUTPUT_PATH', 'docs/dashboards')
        self.output_path = Path(default_dashboard_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
    def generate_dashboard(self, date: str = None) -> str:
        """Generate comprehensive HTML dashboard for a specific date."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"Generating debug dashboard for {date}")
        
        date_path = self.archive_path / date
        if not date_path.exists():
            return self._generate_empty_dashboard(date)
        
        # Collect all runs for the date
        runs = []
        for run_folder in sorted(date_path.iterdir()):
            if run_folder.is_dir() and run_folder.name.startswith("run_"):
                run_data = self._analyze_run(run_folder)
                if run_data:  # Only include runs with data
                    runs.append(run_data)
        
        if not runs:
            return self._generate_empty_dashboard(date)
        
        # Generate HTML dashboard
        html = self._build_comprehensive_dashboard_html(date, runs)
        
        # Save dashboard
        dashboard_path = self.output_path / f"dashboard_{date}.html"
        dashboard_path.write_text(html)
        
        logger.info(f"Dashboard generated: {dashboard_path}")
        return str(dashboard_path)
    
    def generate_summary_dashboard(self, days: int = 7) -> str:
        """Generate summary dashboard for multiple days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        
        logger.info(f"Generating summary dashboard for {days} days")
        
        all_runs = []
        date_summaries = {}
        
        # Collect data from all days
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            date_path = self.archive_path / date_str
            
            if date_path.exists():
                day_runs = []
                for run_folder in sorted(date_path.iterdir()):
                    if run_folder.is_dir() and run_folder.name.startswith("run_"):
                        run_data = self._analyze_run(run_folder)
                        if run_data:
                            run_data["date"] = date_str
                            day_runs.append(run_data)
                            all_runs.append(run_data)
                
                if day_runs:
                    date_summaries[date_str] = self._summarize_day_runs(day_runs)
            
            current_date += timedelta(days=1)
        
        # Generate summary HTML
        html = self._build_summary_dashboard_html(date_summaries, all_runs, days)
        
        # Save dashboard
        dashboard_path = self.output_path / f"summary_dashboard_{days}days.html"
        dashboard_path.write_text(html)
        
        logger.info(f"Summary dashboard generated: {dashboard_path}")
        return str(dashboard_path)
    
    def _analyze_run(self, run_path: Path) -> Optional[Dict]:
        """Analyze a single run comprehensively."""
        try:
            analysis = {
                "run_id": run_path.name,
                "run_path": str(run_path),
                "timestamp": None,
                "config": {},
                "articles_collected": 0,
                "sources_distribution": {},
                "sources_health": {},
                "clusters_created": 0,
                "ai_requests": 0,
                "ai_responses": 0,
                "ai_cost": 0.0,
                "ai_tokens": 0,
                "stories_selected": 0,
                "content_type_distribution": {},
                "impact_scores": [],
                "processing_time": 0,
                "errors": [],
                "success_rate": 0.0,
                "files_generated": []
            }
            
            # Read metadata
            metadata_file = run_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
                    analysis["timestamp"] = metadata.get("timestamp")
                    analysis["config"] = metadata.get("config", {})
            
            # Read collected articles
            articles_file = run_path / "collected_articles.json"
            if articles_file.exists():
                with open(articles_file) as f:
                    data = json.load(f)
                    analysis["articles_collected"] = data.get("total_articles", 0)
                    
                    # Analyze source health
                    articles = data.get("articles", [])
                    for article in articles:
                        source = article.get("source", "Unknown")
                        if source not in analysis["sources_health"]:
                            analysis["sources_health"][source] = {"count": 0, "has_summary": 0}
                        analysis["sources_health"][source]["count"] += 1
                        if article.get("summary"):
                            analysis["sources_health"][source]["has_summary"] += 1
            
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
                
                # Analyze request details
                for request_file in requests_dir.glob("*.json"):
                    with open(request_file) as f:
                        request_data = json.load(f)
                        analysis["ai_tokens"] += request_data.get("estimated_tokens", 0)
            
            if responses_dir.exists():
                analysis["ai_responses"] = len(list(responses_dir.glob("*.json")))
                
                # Analyze response details
                for response_file in responses_dir.glob("*.json"):
                    with open(response_file) as f:
                        response_data = json.load(f)
                        analysis["ai_cost"] += response_data.get("cost", 0)
                        analysis["ai_tokens"] += response_data.get("tokens_used", 0)
                        
                        parsed = response_data.get("parsed_analysis")
                        if parsed:
                            analysis["stories_selected"] += 1
                            
                            # Content type distribution
                            content_type = parsed.get("content_type", "unknown")
                            if content_type not in analysis["content_type_distribution"]:
                                analysis["content_type_distribution"][content_type] = 0
                            analysis["content_type_distribution"][content_type] += 1
                            
                            # Impact scores
                            impact_score = parsed.get("impact_score")
                            if impact_score is not None:
                                analysis["impact_scores"].append(impact_score)
            
            # Calculate success rate
            if analysis["ai_requests"] > 0:
                analysis["success_rate"] = analysis["stories_selected"] / analysis["ai_requests"]
            
            # List generated files
            for file_path in run_path.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(run_path)
                    analysis["files_generated"].append({
                        "path": str(relative_path),
                        "size_bytes": file_path.stat().st_size
                    })
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing run {run_path.name}: {e}")
            return None
    
    def _summarize_day_runs(self, runs: List[Dict]) -> Dict:
        """Summarize multiple runs for a single day."""
        if not runs:
            return {}
        
        summary = {
            "date": runs[0]["date"],
            "total_runs": len(runs),
            "total_articles": sum(r["articles_collected"] for r in runs),
            "total_clusters": sum(r["clusters_created"] for r in runs),
            "total_ai_cost": sum(r["ai_cost"] for r in runs),
            "total_stories": sum(r["stories_selected"] for r in runs),
            "avg_success_rate": sum(r["success_rate"] for r in runs) / len(runs),
            "sources_active": set(),
            "best_run": None,
            "worst_run": None
        }
        
        # Find best and worst runs
        best_run = max(runs, key=lambda r: r["stories_selected"])
        worst_run = min(runs, key=lambda r: r["stories_selected"])
        summary["best_run"] = best_run["run_id"]
        summary["worst_run"] = worst_run["run_id"]
        
        # Aggregate active sources
        for run in runs:
            summary["sources_active"].update(run["sources_distribution"].keys())
        summary["sources_active"] = len(summary["sources_active"])
        
        return summary
    
    def _build_comprehensive_dashboard_html(self, date: str, runs: List[Dict]) -> str:
        """Build comprehensive dashboard HTML with advanced visualizations."""
        
        # Create visualizations
        charts_html = ""
        if PLOTLY_AVAILABLE:
            charts_html = self._create_advanced_visualizations(runs)
        else:
            charts_html = "<p>📊 Plotly not available - install with: pip install plotly</p>"
        
        # Calculate aggregate metrics
        total_articles = sum(r['articles_collected'] for r in runs)
        total_cost = sum(r['ai_cost'] for r in runs)
        total_stories = sum(r['stories_selected'] for r in runs)
        avg_success_rate = sum(r['success_rate'] for r in runs) / len(runs) if runs else 0
        
        # Get all unique sources
        all_sources = set()
        for run in runs:
            all_sources.update(run['sources_distribution'].keys())
        
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>🔍 GeoPolitical Daily Debug Dashboard - {date}</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        {self._get_dashboard_css()}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 GeoPolitical Daily Debug Dashboard</h1>
        <div class="header-info">
            <span class="date-badge">📅 {date}</span>
            <span class="runs-badge">🔄 {len(runs)} runs</span>
            <span class="update-badge">🕐 Updated: {datetime.now().strftime('%H:%M:%S')}</span>
        </div>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card highlight">
            <div class="metric-value">{total_articles}</div>
            <div class="metric-label">📰 Articles Collected</div>
            <div class="metric-sublabel">Across {len(all_sources)} sources</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{total_stories}</div>
            <div class="metric-label">📝 Stories Selected</div>
            <div class="metric-sublabel">{avg_success_rate:.1%} success rate</div>
        </div>
        <div class="metric-card cost">
            <div class="metric-value">${total_cost:.4f}</div>
            <div class="metric-label">💰 AI Cost</div>
            <div class="metric-sublabel">Total for all runs</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{sum(r['clusters_created'] for r in runs)}</div>
            <div class="metric-label">🔗 Clusters Created</div>
            <div class="metric-sublabel">For AI analysis</div>
        </div>
    </div>
    
    <div class="dashboard-tabs">
        <button class="tab-button active" onclick="showTab('overview')">📊 Overview</button>
        <button class="tab-button" onclick="showTab('sources')">🌐 Sources</button>
        <button class="tab-button" onclick="showTab('ai-analysis')">🤖 AI Analysis</button>
        <button class="tab-button" onclick="showTab('runs')">🔄 Individual Runs</button>
    </div>
    
    <div id="overview" class="tab-content active">
        <h2>📈 Performance Overview</h2>
        {charts_html}
    </div>
    
    <div id="sources" class="tab-content">
        <h2>🌐 Source Analysis</h2>
        {self._generate_sources_analysis_html(runs)}
    </div>
    
    <div id="ai-analysis" class="tab-content">
        <h2>🤖 AI Analysis Details</h2>
        {self._generate_ai_analysis_html(runs)}
    </div>
    
    <div id="runs" class="tab-content">
        <h2>🔄 Individual Run Details</h2>
        {self._generate_individual_runs_html(runs)}
    </div>
    
    <div class="footer">
        <p>Dashboard auto-refreshes every 60 seconds | Generated by GeoPolitical Daily v2.0</p>
        <p>Archive location: {self.archive_path}</p>
    </div>
    
    <script>
        {self._get_dashboard_javascript()}
    </script>
</body>
</html>
'''
        return html
    
    def _create_advanced_visualizations(self, runs: List[Dict]) -> str:
        """Create advanced Plotly visualizations."""
        if not PLOTLY_AVAILABLE or not runs:
            return "<p>No data available for visualization</p>"
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Articles Collection Over Time', 'AI Cost vs Success Rate', 
                          'Content Type Distribution', 'Source Performance'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"type": "pie"}, {"type": "bar"}]]
        )
        
        # 1. Articles collection timeline
        timestamps = [r['timestamp'] for r in runs if r['timestamp']]
        articles = [r['articles_collected'] for r in runs if r['timestamp']]
        
        fig.add_trace(
            go.Scatter(x=timestamps, y=articles, mode='lines+markers', 
                      name='Articles Collected', line=dict(color='#3498db', width=3)),
            row=1, col=1
        )
        
        # 2. Cost vs Success Rate scatter
        costs = [r['ai_cost'] for r in runs]
        success_rates = [r['success_rate'] * 100 for r in runs]
        stories = [r['stories_selected'] for r in runs]
        
        fig.add_trace(
            go.Scatter(x=costs, y=success_rates, mode='markers',
                      marker=dict(size=[s*5+10 for s in stories], color='#e74c3c', opacity=0.7),
                      text=[f"Run: {r['run_id']}<br>Stories: {r['stories_selected']}" for r in runs],
                      name='Cost vs Success'),
            row=1, col=2
        )
        
        # 3. Content type distribution (pie chart)
        all_content_types = Counter()
        for run in runs:
            for ct, count in run['content_type_distribution'].items():
                all_content_types[ct] += count
        
        if all_content_types:
            fig.add_trace(
                go.Pie(labels=list(all_content_types.keys()), 
                       values=list(all_content_types.values()),
                       name="Content Types"),
                row=2, col=1
            )
        
        # 4. Source performance
        source_stats = defaultdict(lambda: {'articles': 0, 'runs': 0})
        for run in runs:
            for source, count in run['sources_distribution'].items():
                source_stats[source]['articles'] += count
                source_stats[source]['runs'] += 1
        
        # Top 10 sources
        top_sources = sorted(source_stats.items(), 
                           key=lambda x: x[1]['articles'], reverse=True)[:10]
        
        source_names = [s[0] for s in top_sources]
        source_articles = [s[1]['articles'] for s in top_sources]
        
        fig.add_trace(
            go.Bar(x=source_names, y=source_articles, 
                   marker_color='#27ae60', name='Articles per Source'),
            row=2, col=2
        )
        
        # Update layout
        fig.update_layout(
            height=800,
            title_text="📊 GeoPolitical Daily Analytics Dashboard",
            showlegend=True,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        fig.update_xaxes(title_text="Time", row=1, col=1)
        fig.update_yaxes(title_text="Articles", row=1, col=1)
        
        fig.update_xaxes(title_text="Cost ($)", row=1, col=2)
        fig.update_yaxes(title_text="Success Rate (%)", row=1, col=2)
        
        fig.update_xaxes(title_text="Source", row=2, col=2, tickangle=45)
        fig.update_yaxes(title_text="Articles", row=2, col=2)
        
        # Convert to HTML
        return pio.to_html(fig, include_plotlyjs=False, div_id="main-dashboard-charts")
    
    def _generate_sources_analysis_html(self, runs: List[Dict]) -> str:
        """Generate detailed source analysis HTML."""
        # Aggregate source data
        source_stats = defaultdict(lambda: {
            'total_articles': 0, 'runs_active': 0, 'health_score': 0,
            'avg_articles_per_run': 0, 'reliability': 0
        })
        
        total_runs = len(runs)
        
        for run in runs:
            active_sources = set(run['sources_distribution'].keys())
            for source, count in run['sources_distribution'].items():
                source_stats[source]['total_articles'] += count
                source_stats[source]['runs_active'] += 1
        
        # Calculate derived metrics
        for source, stats in source_stats.items():
            if stats['runs_active'] > 0:
                stats['avg_articles_per_run'] = stats['total_articles'] / stats['runs_active']
                stats['reliability'] = stats['runs_active'] / total_runs
                stats['health_score'] = (stats['reliability'] * 0.6 + 
                                       min(stats['avg_articles_per_run'] / 10, 1) * 0.4)
        
        # Sort by health score
        sorted_sources = sorted(source_stats.items(), 
                              key=lambda x: x[1]['health_score'], reverse=True)
        
        html = '''
        <div class="sources-grid">
        '''
        
        for source, stats in sorted_sources:
            health_class = "excellent" if stats['health_score'] > 0.8 else \
                          "good" if stats['health_score'] > 0.6 else \
                          "warning" if stats['health_score'] > 0.4 else "poor"
            
            html += f'''
            <div class="source-card {health_class}">
                <div class="source-header">
                    <h3>{source}</h3>
                    <div class="health-indicator {health_class}">
                        {stats['health_score']:.2f}
                    </div>
                </div>
                <div class="source-metrics">
                    <div class="metric">
                        <span class="metric-label">Articles:</span>
                        <span class="metric-value">{stats['total_articles']}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Active Runs:</span>
                        <span class="metric-value">{stats['runs_active']}/{total_runs}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Avg/Run:</span>
                        <span class="metric-value">{stats['avg_articles_per_run']:.1f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Reliability:</span>
                        <span class="metric-value">{stats['reliability']:.1%}</span>
                    </div>
                </div>
            </div>
            '''
        
        html += '''
        </div>
        '''
        
        return html
    
    def _generate_ai_analysis_html(self, runs: List[Dict]) -> str:
        """Generate AI analysis details HTML."""
        total_requests = sum(r['ai_requests'] for r in runs)
        total_responses = sum(r['ai_responses'] for r in runs)
        total_stories = sum(r['stories_selected'] for r in runs)
        total_cost = sum(r['ai_cost'] for r in runs)
        total_tokens = sum(r['ai_tokens'] for r in runs)
        
        # Content type analysis
        all_content_types = Counter()
        all_impact_scores = []
        
        for run in runs:
            for ct, count in run['content_type_distribution'].items():
                all_content_types[ct] += count
            all_impact_scores.extend(run['impact_scores'])
        
        avg_impact = sum(all_impact_scores) / len(all_impact_scores) if all_impact_scores else 0
        
        html = f'''
        <div class="ai-analysis-grid">
            <div class="ai-summary-card">
                <h3>🤖 AI Performance Summary</h3>
                <div class="ai-metrics">
                    <div class="ai-metric">
                        <span class="ai-metric-value">{total_requests}</span>
                        <span class="ai-metric-label">Requests Sent</span>
                    </div>
                    <div class="ai-metric">
                        <span class="ai-metric-value">{total_stories}</span>
                        <span class="ai-metric-label">Stories Generated</span>
                    </div>
                    <div class="ai-metric">
                        <span class="ai-metric-value">${total_cost:.4f}</span>
                        <span class="ai-metric-label">Total Cost</span>
                    </div>
                    <div class="ai-metric">
                        <span class="ai-metric-value">{total_tokens:,}</span>
                        <span class="ai-metric-label">Tokens Used</span>
                    </div>
                    <div class="ai-metric">
                        <span class="ai-metric-value">{avg_impact:.1f}/10</span>
                        <span class="ai-metric-label">Avg Impact Score</span>
                    </div>
                </div>
            </div>
            
            <div class="content-types-card">
                <h3>📊 Content Type Distribution</h3>
                <div class="content-types-list">
        '''
        
        for content_type, count in all_content_types.most_common():
            percentage = (count / total_stories * 100) if total_stories > 0 else 0
            html += f'''
                    <div class="content-type-item">
                        <div class="content-type-bar">
                            <div class="content-type-fill" style="width: {percentage}%"></div>
                        </div>
                        <span class="content-type-label">{content_type}</span>
                        <span class="content-type-count">{count} ({percentage:.1f}%)</span>
                    </div>
            '''
        
        html += '''
                </div>
            </div>
        </div>
        '''
        
        if all_impact_scores:
            # Impact score distribution
            score_dist = Counter([round(score) for score in all_impact_scores])
            html += '''
            <div class="impact-scores-card">
                <h3>🎯 Impact Score Distribution</h3>
                <div class="score-distribution">
            '''
            
            for score in range(1, 11):
                count = score_dist.get(score, 0)
                percentage = (count / len(all_impact_scores) * 100) if all_impact_scores else 0
                html += f'''
                    <div class="score-bar">
                        <span class="score-label">{score}</span>
                        <div class="score-bar-fill" style="width: {percentage}%; background-color: hsl({score*36}, 70%, 50%)"></div>
                        <span class="score-count">{count}</span>
                    </div>
                '''
            
            html += '''
                </div>
            </div>
            '''
        
        return html
    
    def _generate_individual_runs_html(self, runs: List[Dict]) -> str:
        """Generate individual runs details HTML."""
        html = '''
        <div class="runs-list">
        '''
        
        for run in runs:
            status_class = "success" if run['stories_selected'] >= 3 else \
                          "warning" if run['stories_selected'] >= 1 else "error"
            
            timestamp_str = run['timestamp'][:19].replace('T', ' ') if run['timestamp'] else 'Unknown'
            
            # Top sources for this run
            top_sources = sorted(run['sources_distribution'].items(), 
                               key=lambda x: x[1], reverse=True)[:5]
            sources_html = ' '.join([f'<span class="source-tag">{s[0]}: {s[1]}</span>' 
                                   for s in top_sources])
            
            html += f'''
            <div class="run-detail-card {status_class}">
                <div class="run-header">
                    <h3>{run['run_id']}</h3>
                    <div class="run-timestamp">{timestamp_str}</div>
                    <div class="run-status-badge {status_class}">
                        {run['stories_selected']} stories
                    </div>
                </div>
                
                <div class="run-metrics-row">
                    <div class="run-metric">
                        <span class="run-metric-label">📰 Articles:</span>
                        <span class="run-metric-value">{run['articles_collected']}</span>
                    </div>
                    <div class="run-metric">
                        <span class="run-metric-label">🔗 Clusters:</span>
                        <span class="run-metric-value">{run['clusters_created']}</span>
                    </div>
                    <div class="run-metric">
                        <span class="run-metric-label">🤖 AI Requests:</span>
                        <span class="run-metric-value">{run['ai_requests']}</span>
                    </div>
                    <div class="run-metric">
                        <span class="run-metric-label">💰 Cost:</span>
                        <span class="run-metric-value">${run['ai_cost']:.4f}</span>
                    </div>
                    <div class="run-metric">
                        <span class="run-metric-label">✅ Success:</span>
                        <span class="run-metric-value">{run['success_rate']:.1%}</span>
                    </div>
                </div>
                
                <div class="run-config">
                    <strong>Configuration:</strong>
                    AI Model: {run['config'].get('ai_model', 'Unknown')}, 
                    Tokens: {run['config'].get('ai_max_tokens', 'Unknown')}, 
                    Dry Run: {run['config'].get('dry_run', 'Unknown')}
                </div>
                
                <div class="run-sources">
                    <strong>Top Sources:</strong>
                    {sources_html}
                </div>
                
                <div class="run-files">
                    <strong>Files Generated:</strong> {len(run['files_generated'])} files
                </div>
            </div>
            '''
        
        html += '''
        </div>
        '''
        
        return html
    
    def _generate_empty_dashboard(self, date: str) -> str:
        """Generate dashboard for days with no data."""
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>🔍 GeoPolitical Daily Debug Dashboard - {date}</title>
    <meta charset="UTF-8">
    <style>
        {self._get_dashboard_css()}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 GeoPolitical Daily Debug Dashboard</h1>
        <div class="header-info">
            <span class="date-badge">📅 {date}</span>
            <span class="runs-badge">🔄 0 runs</span>
        </div>
    </div>
    
    <div class="empty-state">
        <div class="empty-icon">📭</div>
        <h2>No data available for {date}</h2>
        <p>No pipeline runs found in the archive for this date.</p>
        <p>Archive location: {self.archive_path}</p>
    </div>
    
    <script>
        setTimeout(() => location.reload(), 300000); // Refresh every 5 minutes
    </script>
</body>
</html>
'''
        dashboard_path = self.output_path / f"dashboard_{date}.html"
        dashboard_path.write_text(html)
        return str(dashboard_path)
    
    def _build_summary_dashboard_html(self, date_summaries: Dict, all_runs: List[Dict], days: int) -> str:
        """Build summary dashboard HTML for multiple days."""
        
        total_articles = sum(r['articles_collected'] for r in all_runs)
        total_cost = sum(r['ai_cost'] for r in all_runs)
        total_stories = sum(r['stories_selected'] for r in all_runs)
        
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>📊 GeoPolitical Daily Summary Dashboard - {days} Days</title>
    <meta charset="UTF-8">
    <style>{self._get_dashboard_css()}</style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="header">
        <h1>📊 GeoPolitical Daily Summary Dashboard</h1>
        <div class="header-info">
            <span class="date-badge">📅 Last {days} days</span>
            <span class="runs-badge">🔄 {len(all_runs)} total runs</span>
        </div>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card highlight">
            <div class="metric-value">{total_articles:,}</div>
            <div class="metric-label">📰 Total Articles</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{total_stories}</div>
            <div class="metric-label">📝 Total Stories</div>
        </div>
        <div class="metric-card cost">
            <div class="metric-value">${total_cost:.4f}</div>
            <div class="metric-label">💰 Total Cost</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{len(date_summaries)}</div>
            <div class="metric-label">📅 Active Days</div>
        </div>
    </div>
    
    <div class="summary-content">
        <h2>📈 Daily Summary</h2>
        <div class="days-grid">
        '''
        
        for date_str, summary in sorted(date_summaries.items(), reverse=True):
            status_class = "success" if summary['total_stories'] >= 3 else \
                          "warning" if summary['total_stories'] >= 1 else "error"
            
            html += f'''
            <div class="day-summary-card {status_class}">
                <div class="day-header">
                    <h3>{date_str}</h3>
                    <div class="day-badge {status_class}">{summary['total_runs']} runs</div>
                </div>
                <div class="day-metrics">
                    <div class="day-metric">
                        <span class="day-metric-value">{summary['total_articles']}</span>
                        <span class="day-metric-label">Articles</span>
                    </div>
                    <div class="day-metric">
                        <span class="day-metric-value">{summary['total_stories']}</span>
                        <span class="day-metric-label">Stories</span>
                    </div>
                    <div class="day-metric">
                        <span class="day-metric-value">${summary['total_ai_cost']:.3f}</span>
                        <span class="day-metric-label">Cost</span>
                    </div>
                    <div class="day-metric">
                        <span class="day-metric-value">{summary['avg_success_rate']:.0%}</span>
                        <span class="day-metric-label">Success</span>
                    </div>
                </div>
            </div>
            '''
        
        html += '''
        </div>
    </div>
</body>
</html>
'''
        
        return html
    
    def _get_dashboard_css(self) -> str:
        """Get comprehensive CSS styles for the dashboard."""
        return '''
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
            line-height: 1.6;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        }
        
        .header h1 {
            color: #2c3e50;
            font-size: 2.5rem;
            margin-bottom: 1rem;
            text-align: center;
        }
        
        .header-info {
            display: flex;
            justify-content: center;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .date-badge, .runs-badge, .update-badge {
            background: #3498db;
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 500;
        }
        
        .runs-badge {
            background: #27ae60;
        }
        
        .update-badge {
            background: #f39c12;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
            padding: 0 1rem;
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
        }
        
        .metric-card.highlight {
            border: 2px solid #3498db;
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
        }
        
        .metric-card.cost {
            border: 2px solid #e74c3c;
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
        }
        
        .metric-value {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .metric-label {
            font-size: 1.1rem;
            font-weight: 500;
            opacity: 0.9;
        }
        
        .metric-sublabel {
            font-size: 0.9rem;
            opacity: 0.7;
            margin-top: 0.25rem;
        }
        
        .dashboard-tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 2rem;
            padding: 0 1rem;
        }
        
        .tab-button {
            background: rgba(255, 255, 255, 0.9);
            border: none;
            padding: 1rem 2rem;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            border-radius: 10px 10px 0 0;
            margin-right: 5px;
            transition: all 0.3s ease;
        }
        
        .tab-button:hover {
            background: rgba(255, 255, 255, 1);
            transform: translateY(-2px);
        }
        
        .tab-button.active {
            background: #3498db;
            color: white;
            box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
        }
        
        .tab-content {
            display: none;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            margin: 0 1rem;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            min-height: 400px;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .tab-content h2 {
            color: #2c3e50;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid #3498db;
        }
        
        .sources-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
        }
        
        .source-card {
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 5px solid #bdc3c7;
        }
        
        .source-card.excellent {
            border-left-color: #27ae60;
            background: linear-gradient(135deg, #d5f4e6, #f0fdf4);
        }
        
        .source-card.good {
            border-left-color: #f39c12;
            background: linear-gradient(135deg, #fef9e7, #fffbf0);
        }
        
        .source-card.warning {
            border-left-color: #e67e22;
            background: linear-gradient(135deg, #fef2e7, #fff4f0);
        }
        
        .source-card.poor {
            border-left-color: #e74c3c;
            background: linear-gradient(135deg, #fee, #fdf0f0);
        }
        
        .source-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .source-header h3 {
            color: #2c3e50;
            font-size: 1.1rem;
        }
        
        .health-indicator {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            color: white;
        }
        
        .health-indicator.excellent { background: #27ae60; }
        .health-indicator.good { background: #f39c12; }
        .health-indicator.warning { background: #e67e22; }
        .health-indicator.poor { background: #e74c3c; }
        
        .source-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
        }
        
        .metric-label {
            font-weight: 500;
            color: #666;
        }
        
        .ai-analysis-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        .ai-summary-card, .content-types-card, .impact-scores-card {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            border: 1px solid #e9ecef;
        }
        
        .ai-metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
        }
        
        .ai-metric {
            text-align: center;
        }
        
        .ai-metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #3498db;
            display: block;
        }
        
        .ai-metric-label {
            font-size: 0.85rem;
            color: #666;
        }
        
        .content-types-list {
            space-y: 0.5rem;
        }
        
        .content-type-item {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }
        
        .content-type-bar {
            flex: 1;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .content-type-fill {
            height: 100%;
            background: linear-gradient(90deg, #3498db, #2980b9);
            transition: width 0.3s ease;
        }
        
        .content-type-label {
            font-weight: 500;
            min-width: 100px;
        }
        
        .content-type-count {
            font-size: 0.9rem;
            color: #666;
            min-width: 80px;
            text-align: right;
        }
        
        .runs-list {
            space-y: 1rem;
        }
        
        .run-detail-card {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            margin-bottom: 1rem;
            border-left: 5px solid #bdc3c7;
        }
        
        .run-detail-card.success {
            border-left-color: #27ae60;
            background: linear-gradient(135deg, #d5f4e6, #f0fdf4);
        }
        
        .run-detail-card.warning {
            border-left-color: #f39c12;
            background: linear-gradient(135deg, #fef9e7, #fffbf0);
        }
        
        .run-detail-card.error {
            border-left-color: #e74c3c;
            background: linear-gradient(135deg, #fee, #fdf0f0);
        }
        
        .run-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .run-header h3 {
            color: #2c3e50;
            font-size: 1.1rem;
        }
        
        .run-timestamp {
            color: #666;
            font-size: 0.9rem;
        }
        
        .run-status-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 15px;
            font-size: 0.85rem;
            font-weight: 600;
            color: white;
        }
        
        .run-status-badge.success { background: #27ae60; }
        .run-status-badge.warning { background: #f39c12; }
        .run-status-badge.error { background: #e74c3c; }
        
        .run-metrics-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .run-metric {
            text-align: center;
        }
        
        .run-metric-label {
            font-size: 0.85rem;
            color: #666;
            display: block;
        }
        
        .run-metric-value {
            font-size: 1.2rem;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .run-config, .run-sources, .run-files {
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
            color: #555;
        }
        
        .source-tag {
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            font-size: 0.8rem;
            margin: 0.2rem;
        }
        
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            margin: 2rem;
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .empty-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
        }
        
        .footer {
            text-align: center;
            padding: 2rem;
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9rem;
        }
        
        .days-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
        }
        
        .day-summary-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 5px solid #bdc3c7;
        }
        
        .day-summary-card.success {
            border-left-color: #27ae60;
        }
        
        .day-summary-card.warning {
            border-left-color: #f39c12;
        }
        
        .day-summary-card.error {
            border-left-color: #e74c3c;
        }
        
        .day-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .day-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: 500;
            color: white;
        }
        
        .day-badge.success { background: #27ae60; }
        .day-badge.warning { background: #f39c12; }
        .day-badge.error { background: #e74c3c; }
        
        .day-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        
        .day-metric {
            text-align: center;
        }
        
        .day-metric-value {
            font-size: 1.5rem;
            font-weight: 600;
            color: #2c3e50;
            display: block;
        }
        
        .day-metric-label {
            font-size: 0.8rem;
            color: #666;
        }
        
        .score-distribution {
            space-y: 0.5rem;
        }
        
        .score-bar {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .score-label {
            width: 20px;
            font-weight: 600;
        }
        
        .score-bar-fill {
            flex: 1;
            height: 20px;
            border-radius: 10px;
            transition: width 0.3s ease;
        }
        
        .score-count {
            width: 30px;
            text-align: right;
            font-size: 0.9rem;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .metrics-grid {
                grid-template-columns: 1fr;
            }
            
            .dashboard-tabs {
                flex-wrap: wrap;
            }
            
            .tab-button {
                flex: 1;
                min-width: 150px;
            }
            
            .ai-analysis-grid {
                grid-template-columns: 1fr;
            }
            
            .sources-grid {
                grid-template-columns: 1fr;
            }
            
            .run-metrics-row {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        '''
    
    def _get_dashboard_javascript(self) -> str:
        """Get JavaScript for dashboard interactivity."""
        return '''
        function showTab(tabName) {
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Remove active class from all buttons
            const tabButtons = document.querySelectorAll('.tab-button');
            tabButtons.forEach(button => button.classList.remove('active'));
            
            // Show selected tab
            const selectedTab = document.getElementById(tabName);
            if (selectedTab) {
                selectedTab.classList.add('active');
            }
            
            // Add active class to clicked button
            const clickedButton = event.target;
            if (clickedButton) {
                clickedButton.classList.add('active');
            }
        }
        
        // Auto-refresh functionality
        function startAutoRefresh() {
            setInterval(() => {
                location.reload();
            }, 60000); // Refresh every 60 seconds
        }
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            startAutoRefresh();
            
            // Add click handlers for tabs
            const tabButtons = document.querySelectorAll('.tab-button');
            tabButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const tabName = this.textContent.split(' ')[1].toLowerCase();
                    showTab(tabName);
                });
            });
        });
        
        // Performance monitoring
        window.addEventListener('load', function() {
            const loadTime = window.performance.timing.loadEventEnd - window.performance.timing.navigationStart;
            console.log(`Dashboard loaded in ${loadTime}ms`);
        });
        '''