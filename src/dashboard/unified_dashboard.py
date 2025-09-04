"""
Unified Dashboard Generator - Single streamlined dashboard for GeoPolitical Daily.
Replaces the multiple dashboard systems with one minimalist, functional dashboard.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import math
from collections import defaultdict, Counter

try:
    from ..config import Config
    from ..logger import get_logger
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import Config
    from logger import get_logger

logger = get_logger(__name__)


class UnifiedDashboard:
    """Generate single comprehensive dashboard for GitHub Pages."""
    
    def __init__(self, archive_path: str = None):
        self.archive_path = Path(archive_path or getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive'))
        self.output_path = Path("docs")  # GitHub Pages output
        
    def generate_dashboard(self) -> str:
        """Generate unified HTML dashboard for docs/dashboard.html"""
        logger.info("Generating unified dashboard")
        
        # Get latest data
        latest_data = self._get_latest_run_data()
        summary_data = self._get_summary_data(days=7)
        
        # Generate HTML
        html = self._build_dashboard_html(latest_data, summary_data)
        
        # Save to docs/dashboard.html (GitHub Pages)
        dashboard_path = self.output_path / "dashboard.html"
        dashboard_path.write_text(html)
        
        logger.info(f"Unified dashboard generated: {dashboard_path}")
        return str(dashboard_path)
    
    def _get_latest_run_data(self) -> Dict[str, Any]:
        """Get data from the most recent run."""
        # Find most recent date with data
        if not self.archive_path.exists():
            return self._empty_data()
            
        recent_dates = sorted([d.name for d in self.archive_path.iterdir() 
                              if d.is_dir() and len(d.name) == 10], reverse=True)
        
        for date_str in recent_dates[:3]:  # Check last 3 days
            date_path = self.archive_path / date_str
            runs = sorted([r for r in date_path.iterdir() 
                          if r.is_dir() and r.name.startswith("run_")], 
                         reverse=True)
            
            for run_path in runs[:2]:  # Check last 2 runs per day
                try:
                    run_data = self._analyze_run(run_path)
                    if run_data and run_data.get("articles_count", 0) > 0:
                        run_data["date"] = date_str
                        return run_data
                except Exception as e:
                    logger.warning(f"Error analyzing run {run_path}: {e}")
                    continue
        
        return self._empty_data()
    
    def _get_summary_data(self, days: int = 7) -> Dict[str, Any]:
        """Get summary statistics for recent days."""
        if not self.archive_path.exists():
            return {"total_runs": 0, "successful_runs": 0, "total_cost": 0, "avg_articles": 0}
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)
        
        all_runs = []
        current_date = start_date
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            date_path = self.archive_path / date_str
            
            if date_path.exists():
                for run_folder in date_path.iterdir():
                    if run_folder.is_dir() and run_folder.name.startswith("run_"):
                        try:
                            run_data = self._analyze_run(run_folder)
                            if run_data:
                                all_runs.append(run_data)
                        except Exception:
                            continue
            
            current_date += timedelta(days=1)
        
        if not all_runs:
            return {"total_runs": 0, "successful_runs": 0, "total_cost": 0, "avg_articles": 0}
        
        successful_runs = [r for r in all_runs if r.get("articles_count", 0) > 0]
        total_cost = sum(r.get("total_cost", 0) for r in all_runs)
        avg_articles = sum(r.get("articles_count", 0) for r in successful_runs) / max(len(successful_runs), 1)
        
        return {
            "total_runs": len(all_runs),
            "successful_runs": len(successful_runs),
            "total_cost": total_cost,
            "avg_articles": int(avg_articles),
            "success_rate": len(successful_runs) / len(all_runs) * 100 if all_runs else 0
        }
    
    def _analyze_run(self, run_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a single run folder for key metrics."""
        try:
            # Check for final results
            final_results_path = run_path / "final_results.json"
            if final_results_path.exists():
                with open(final_results_path) as f:
                    final_data = json.load(f)
                    
                return {
                    "run_id": run_path.name,
                    "articles_count": final_data.get("total_articles", 0),
                    "stories_selected": final_data.get("final_stories", 0),
                    "total_cost": final_data.get("total_cost", 0),
                    "processing_time": final_data.get("total_processing_time", 0),
                    "success": final_data.get("success", False)
                }
            
            # Fallback: count from individual files
            articles_count = 0
            ai_files = list(run_path.glob("ai_*.json"))
            if ai_files:
                # Estimate from AI request files
                articles_count = len([f for f in run_path.glob("*.json") if "article" in f.name])
            
            return {
                "run_id": run_path.name,
                "articles_count": articles_count,
                "stories_selected": min(4, articles_count),  # Typical selection
                "total_cost": 0.05,  # Estimate
                "processing_time": 0,
                "success": articles_count > 0
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing run {run_path}: {e}")
            return None
    
    def _empty_data(self) -> Dict[str, Any]:
        """Return empty data structure."""
        return {
            "run_id": "none",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "articles_count": 0,
            "stories_selected": 0,
            "total_cost": 0,
            "processing_time": 0,
            "success": False
        }
    
    def _build_dashboard_html(self, latest_data: Dict, summary_data: Dict) -> str:
        """Build comprehensive dashboard HTML."""
        template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Geopolitical Daily</title>
    <meta name="description" content="Real-time metrics and analytics for the Geopolitical Daily newsletter pipeline">
    <link rel="stylesheet" href="assets/style.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .dashboard-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #3182ce;
            text-align: center;
        }}
        
        .metric-title {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 4px;
        }}
        
        .metric-subtitle {{
            font-size: 12px;
            color: #999;
        }}
        
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }}
        
        .status-success {{
            background: #48bb78;
            color: white;
        }}
        
        .status-error {{
            background: #f56565;
            color: white;
        }}
        
        .nav {{
            margin-bottom: 20px;
        }}
        
        .nav a {{
            margin-right: 15px;
            color: #3182ce;
            text-decoration: none;
        }}
        
        .nav a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <nav class="nav">
            <a href="index.html">Home</a>
            <a href="archive.html">Archive</a>
            <a href="about.html">About</a>
            <strong>Dashboard</strong>
            <a href="feed.xml">RSS</a>
        </nav>
        
        <header style="text-align: center; margin-bottom: 30px;">
            <h1>GeoPolitical Daily Dashboard</h1>
            <p>Pipeline metrics and performance monitoring</p>
            <p style="color: #666; font-size: 14px;">
                Last Updated: {update_time}
                <span class="status-badge {status_class}">{status_text}</span>
            </p>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">Articles Processed</div>
                <div class="metric-value">{articles_count}</div>
                <div class="metric-subtitle">Latest run</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Stories Selected</div>
                <div class="metric-value">{stories_selected}</div>
                <div class="metric-subtitle">AI analysis output</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Processing Cost</div>
                <div class="metric-value">${cost:.4f}</div>
                <div class="metric-subtitle">Latest run</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Success Rate</div>
                <div class="metric-value">{success_rate:.1f}%</div>
                <div class="metric-subtitle">Last 7 days</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Total Runs</div>
                <div class="metric-value">{total_runs}</div>
                <div class="metric-subtitle">Last 7 days</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Avg Articles</div>
                <div class="metric-value">{avg_articles}</div>
                <div class="metric-subtitle">Per successful run</div>
            </div>
        </div>

        <div class="chart-container">
            <h3>Pipeline Overview</h3>
            <p style="color: #666; margin-bottom: 20px;">
                Latest run: <strong>{run_id}</strong> on {date}
                {processing_info}
            </p>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="text-align: center; padding: 15px; background: #f7fafc; border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: bold; color: #3182ce;">{articles_count}</div>
                    <div style="font-size: 12px; color: #666;">Articles Collected</div>
                </div>
                <div style="text-align: center; padding: 15px; background: #f7fafc; border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: bold; color: #38a169;">{stories_selected}</div>
                    <div style="font-size: 12px; color: #666;">Stories Selected</div>
                </div>
                <div style="text-align: center; padding: 15px; background: #f7fafc; border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: bold; color: #e53e3e;">${cost:.4f}</div>
                    <div style="font-size: 12px; color: #666;">Processing Cost</div>
                </div>
            </div>
        </div>

        <footer style="text-align: center; margin-top: 30px; color: #666; font-size: 14px;">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p><a href="index.html">Latest Newsletter</a> | <a href="feed.xml">RSS Feed</a></p>
        </footer>
    </div>
</body>
</html>'''

        # Format the template
        status_class = "status-success" if latest_data["success"] else "status-error"
        status_text = "Operational" if latest_data["success"] else "Issues Detected"
        
        processing_info = ""
        if latest_data["processing_time"] > 0:
            processing_info = f" • Processing time: {latest_data['processing_time']:.1f}s"
        
        return template.format(
            update_time=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            status_class=status_class,
            status_text=status_text,
            articles_count=latest_data["articles_count"],
            stories_selected=latest_data["stories_selected"],
            cost=latest_data["total_cost"],
            success_rate=summary_data["success_rate"],
            total_runs=summary_data["total_runs"],
            avg_articles=summary_data["avg_articles"],
            run_id=latest_data["run_id"],
            date=latest_data["date"],
            processing_info=processing_info
        )