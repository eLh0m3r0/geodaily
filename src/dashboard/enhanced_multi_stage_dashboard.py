"""
Enhanced Multi-Stage Dashboard for Complete Pipeline Transparency.

This module creates comprehensive interactive dashboards that visualize every stage
of the multi-stage AI analysis pipeline, providing complete transparency into
the decision-making process.
"""

import json
import html
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class EnhancedMultiStageDashboard:
    """Enhanced dashboard with multi-stage pipeline visualization."""
    
    def __init__(self, archive_path: str = None, output_path: str = None):
        from ..config import Config
        
        self.archive_path = Path(archive_path or getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive'))
        self.output_path = Path(output_path or getattr(Config, 'DASHBOARD_OUTPUT_PATH', 'dashboards'))
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML to prevent XSS vulnerabilities."""
        return html.escape(str(text), quote=True)

    def generate_dashboard_for_date(self, date) -> Path:
        """Generate dashboard for a specific date (compatibility method)."""
        from datetime import datetime
        
        if isinstance(date, datetime):
            target_date = date
        else:
            # Assume it's a date object
            target_date = datetime.combine(date, datetime.min.time())
        
        dashboard_file = self.generate_comprehensive_dashboard(target_date)
        return Path(dashboard_file) if dashboard_file else None

    def generate_comprehensive_dashboard(self, date: datetime = None) -> str:
        """Generate comprehensive multi-stage analysis dashboard."""
        if not date:
            date = datetime.now()
        
        date_str = date.strftime("%Y-%m-%d")
        print(f"📊 Generating enhanced multi-stage dashboard for {date_str}")
        
        # Load all available run data for the date
        runs_data = self._load_runs_data(date)
        
        if not runs_data:
            logger.warning(f"No run data found for {date_str}")
            return self._generate_no_data_dashboard(date_str)
        
        # Generate comprehensive dashboard
        dashboard_html = self._create_multi_stage_dashboard_html(runs_data, date_str)
        
        # Save dashboard
        filename = f"enhanced_dashboard_{date_str}.html"
        dashboard_path = self.output_path / filename
        
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_html)
        
        print(f"✅ Enhanced dashboard generated: {dashboard_path}")
        return str(dashboard_path)

    def _load_runs_data(self, date: datetime) -> List[Dict]:
        """Load all pipeline run data for a specific date."""
        date_folder = self.archive_path / date.strftime("%Y-%m-%d")
        
        if not date_folder.exists():
            return []
        
        runs_data = []
        for run_folder in date_folder.iterdir():
            if run_folder.is_dir() and run_folder.name.startswith("run_"):
                run_data = self._load_single_run_data(run_folder)
                if run_data:
                    runs_data.append(run_data)
        
        return sorted(runs_data, key=lambda x: x.get('timestamp', ''), reverse=True)

    def _load_single_run_data(self, run_folder: Path) -> Optional[Dict]:
        """Load data for a single pipeline run."""
        try:
            run_data = {
                'run_id': run_folder.name,
                'run_path': str(run_folder)
            }
            
            # Load metadata
            metadata_file = run_folder / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    run_data['metadata'] = json.load(f)
                    run_data['timestamp'] = run_data['metadata'].get('timestamp', '')
            
            # Load pipeline transparency data
            transparency_file = run_folder / "pipeline_transparency.json"
            if transparency_file.exists():
                with open(transparency_file, 'r') as f:
                    run_data['pipeline_transparency'] = json.load(f)
            
            # Load content extraction results
            extraction_file = run_folder / "content_extraction_results.json"
            if extraction_file.exists():
                with open(extraction_file, 'r') as f:
                    run_data['content_extraction'] = json.load(f)
            
            # Load individual stage data
            run_data['stages'] = {}
            for stage_file in run_folder.glob("stage_*.json"):
                stage_name = stage_file.stem.replace("stage_", "")
                with open(stage_file, 'r') as f:
                    run_data['stages'][stage_name] = json.load(f)
            
            # Load collected articles data
            articles_file = run_folder / "collected_articles.json"
            if articles_file.exists():
                with open(articles_file, 'r') as f:
                    articles_data = json.load(f)
                    run_data['collected_articles'] = articles_data.get('articles', [])
            
            return run_data
            
        except Exception as e:
            logger.error(f"Failed to load run data from {run_folder}: {e}")
            return None

    def _create_multi_stage_dashboard_html(self, runs_data: List[Dict], date_str: str) -> str:
        """Create comprehensive multi-stage dashboard HTML."""
        
        # Select the most recent run for detailed analysis
        latest_run = runs_data[0] if runs_data else {}
        
        # Generate visualizations
        pipeline_flow_chart = self._create_pipeline_flow_visualization(latest_run)
        stage_details_charts = self._create_stage_details_visualizations(latest_run)
        content_extraction_chart = self._create_content_extraction_visualization(latest_run)
        decision_audit_trail = self._create_decision_audit_trail(latest_run)
        source_analysis_chart = self._create_source_analysis_visualization(latest_run)
        cost_breakdown_chart = self._create_cost_breakdown_visualization(latest_run)
        
        # Generate summary statistics
        summary_stats = self._generate_summary_statistics(latest_run)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Multi-Stage Analysis Dashboard - {date_str}</title>
    <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        {self._get_enhanced_dashboard_styles()}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header class="dashboard-header">
            <div class="header-content">
                <h1><i class="fas fa-microscope"></i> Enhanced Multi-Stage Analysis Dashboard</h1>
                <div class="header-info">
                    <span class="date-badge">{date_str}</span>
                    <span class="run-badge">Run: {latest_run.get('run_id', 'N/A')}</span>
                    <span class="status-badge status-success">Complete Transparency</span>
                </div>
            </div>
        </header>

        <nav class="dashboard-nav">
            <button class="nav-btn active" onclick="showTab('overview')">
                <i class="fas fa-chart-pie"></i> Overview
            </button>
            <button class="nav-btn" onclick="showTab('pipeline')">
                <i class="fas fa-sitemap"></i> Pipeline Flow
            </button>
            <button class="nav-btn" onclick="showTab('stages')">
                <i class="fas fa-layer-group"></i> Stage Details
            </button>
            <button class="nav-btn" onclick="showTab('content')">
                <i class="fas fa-file-text"></i> Content Analysis
            </button>
            <button class="nav-btn" onclick="showTab('decisions')">
                <i class="fas fa-gavel"></i> Decision Audit
            </button>
            <button class="nav-btn" onclick="showTab('sources')">
                <i class="fas fa-globe"></i> Source Analysis
            </button>
        </nav>

        <main class="dashboard-main">
            <!-- Overview Tab -->
            <div id="overview" class="tab-content active">
                <div class="summary-grid">
                    {summary_stats}
                </div>
                <div class="chart-grid">
                    <div class="chart-card">
                        <h3><i class="fas fa-funnel-dollar"></i> Pipeline Funnel</h3>
                        <div id="pipeline-funnel"></div>
                    </div>
                    <div class="chart-card">
                        <h3><i class="fas fa-dollar-sign"></i> Cost Breakdown</h3>
                        <div id="cost-breakdown"></div>
                    </div>
                </div>
            </div>

            <!-- Pipeline Flow Tab -->
            <div id="pipeline" class="tab-content">
                <div class="chart-card full-width">
                    <h3><i class="fas fa-sitemap"></i> Complete Pipeline Flow</h3>
                    <div id="pipeline-flow"></div>
                </div>
            </div>

            <!-- Stage Details Tab -->
            <div id="stages" class="tab-content">
                <div class="stage-grid">
                    {stage_details_charts}
                </div>
            </div>

            <!-- Content Analysis Tab -->
            <div id="content" class="tab-content">
                <div class="chart-card full-width">
                    <h3><i class="fas fa-file-text"></i> Content Extraction Analysis</h3>
                    <div id="content-extraction"></div>
                </div>
            </div>

            <!-- Decision Audit Tab -->
            <div id="decisions" class="tab-content">
                <div class="audit-trail">
                    <h3><i class="fas fa-gavel"></i> Complete Decision Audit Trail</h3>
                    {decision_audit_trail}
                </div>
            </div>

            <!-- Source Analysis Tab -->
            <div id="sources" class="tab-content">
                <div class="chart-card full-width">
                    <h3><i class="fas fa-globe"></i> Source Performance Analysis</h3>
                    <div id="source-analysis"></div>
                </div>
            </div>
        </main>

        <footer class="dashboard-footer">
            <p><i class="fas fa-clock"></i> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p><i class="fas fa-brain"></i> Enhanced Multi-Stage AI Analysis Pipeline</p>
        </footer>
    </div>

    <script>
        {self._get_enhanced_dashboard_javascript()}
        
        // Initialize charts
        {pipeline_flow_chart}
        {cost_breakdown_chart}
        {content_extraction_chart}
        {source_analysis_chart}
        
        console.log('Enhanced Multi-Stage Dashboard initialized');
    </script>
</body>
</html>
        """
        
        return html_content

    def _create_pipeline_flow_visualization(self, run_data: Dict) -> str:
        """Create pipeline flow visualization."""
        if not run_data.get('pipeline_transparency'):
            return "// No pipeline data available"
        
        transparency = run_data['pipeline_transparency']
        stages = transparency.get('stage_breakdown', [])
        
        if not stages:
            return "// No stage data available"
        
        # Create funnel chart data
        stage_names = []
        article_counts = []
        colors = ['#e74c3c', '#f39c12', '#f1c40f', '#27ae60']
        
        for i, stage in enumerate(stages):
            stage_names.append(stage.get('stage', f'Stage {i+1}').replace('_', ' ').title())
            article_counts.append(stage.get('output_count', 0))
        
        return f"""
        // Pipeline Flow Funnel Chart
        const pipelineFunnelData = [{{
            type: 'funnel',
            y: {json.dumps(stage_names)},
            x: {json.dumps(article_counts)},
            textinfo: "value+percent initial",
            marker: {{
                color: {json.dumps(colors[:len(stages)])},
            }},
            connector: {{
                line: {{
                    color: "royalblue",
                    dash: "dot",
                    width: 3
                }}
            }}
        }}];
        
        const pipelineFunnelLayout = {{
            title: 'Article Flow Through Analysis Stages',
            margin: {{t: 50, b: 50, l: 100, r: 100}},
            height: 500
        }};
        
        Plotly.newPlot('pipeline-funnel', pipelineFunnelData, pipelineFunnelLayout, {{responsive: true}});
        """

    def _create_cost_breakdown_visualization(self, run_data: Dict) -> str:
        """Create cost breakdown visualization."""
        if not run_data.get('pipeline_transparency'):
            return "// No cost data available"
        
        transparency = run_data['pipeline_transparency']
        stages = transparency.get('stage_breakdown', [])
        
        if not stages:
            return "// No stage cost data available"
        
        stage_names = []
        stage_costs = []
        
        for stage in stages:
            stage_names.append(stage.get('stage', 'Unknown').replace('_', ' ').title())
            stage_costs.append(stage.get('cost', 0))
        
        return f"""
        // Cost Breakdown Chart
        const costBreakdownData = [{{
            type: 'pie',
            labels: {json.dumps(stage_names)},
            values: {json.dumps(stage_costs)},
            hole: 0.4,
            marker: {{
                colors: ['#3498db', '#9b59b6', '#e67e22', '#2ecc71']
            }}
        }}];
        
        const costBreakdownLayout = {{
            title: 'Cost Distribution by Stage',
            showlegend: true,
            height: 400
        }};
        
        Plotly.newPlot('cost-breakdown', costBreakdownData, costBreakdownLayout, {{responsive: true}});
        """

    def _create_content_extraction_visualization(self, run_data: Dict) -> str:
        """Create content extraction results visualization."""
        if not run_data.get('content_extraction'):
            return "// No content extraction data available"
        
        extraction = run_data['content_extraction']
        summary = extraction.get('extraction_summary', {})
        
        return f"""
        // Content Extraction Analysis
        const extractionData = [{{
            type: 'bar',
            x: ['Successful', 'Fallback Used', 'Failed'],
            y: [{summary.get('successful_extractions', 0)}, 
                {summary.get('fallback_used', 0)}, 
                {extraction.get('total_articles', 0) - summary.get('successful_extractions', 0) - summary.get('fallback_used', 0)}],
            marker: {{
                color: ['#27ae60', '#f39c12', '#e74c3c']
            }}
        }}];
        
        const extractionLayout = {{
            title: 'Content Extraction Results',
            xaxis: {{title: 'Extraction Method'}},
            yaxis: {{title: 'Number of Articles'}},
            height: 400
        }};
        
        Plotly.newPlot('content-extraction', extractionData, extractionLayout, {{responsive: true}});
        """

    def _create_source_analysis_visualization(self, run_data: Dict) -> str:
        """Create source analysis visualization."""
        if not run_data.get('collected_articles'):
            return "// No source data available"
        
        articles = run_data['collected_articles']
        source_counts = {}
        
        for article in articles:
            source = article.get('source', 'Unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Get top 10 sources
        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        source_names = [item[0] for item in top_sources]
        source_values = [item[1] for item in top_sources]
        
        return f"""
        // Source Analysis Chart
        const sourceData = [{{
            type: 'bar',
            x: {json.dumps(source_values)},
            y: {json.dumps(source_names)},
            orientation: 'h',
            marker: {{
                color: '#3498db'
            }}
        }}];
        
        const sourceLayout = {{
            title: 'Top Sources by Article Count',
            xaxis: {{title: 'Number of Articles'}},
            yaxis: {{title: 'Source', automargin: true}},
            height: 600,
            margin: {{l: 200}}
        }};
        
        Plotly.newPlot('source-analysis', sourceData, sourceLayout, {{responsive: true}});
        """

    def _create_stage_details_visualizations(self, run_data: Dict) -> str:
        """Create detailed stage visualizations."""
        if not run_data.get('stages'):
            return "<p>No detailed stage data available</p>"
        
        stages_html = ""
        for stage_name, stage_data in run_data['stages'].items():
            stats = stage_data.get('statistics', {})
            
            stages_html += f"""
            <div class="stage-card">
                <h4><i class="fas fa-cog"></i> {stage_name.replace('_', ' ').title()}</h4>
                <div class="stage-stats">
                    <div class="stat-item">
                        <span class="stat-label">Input Articles:</span>
                        <span class="stat-value">{stats.get('input_articles', 0)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Output Articles:</span>
                        <span class="stat-value">{stats.get('output_articles', 0)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Advancement Rate:</span>
                        <span class="stat-value">{stats.get('advancement_rate', 0):.1%}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Average Score:</span>
                        <span class="stat-value">{stats.get('average_score', 0):.2f}</span>
                    </div>
                </div>
                <div class="stage-reasoning">
                    <strong>Reasoning:</strong> {stage_data.get('reasoning', 'No reasoning provided')}
                </div>
            </div>
            """
        
        return stages_html

    def _create_decision_audit_trail(self, run_data: Dict) -> str:
        """Create decision audit trail."""
        if not run_data.get('pipeline_transparency'):
            return "<p>No decision audit data available</p>"
        
        transparency = run_data['pipeline_transparency']
        audit_trail = transparency.get('decision_audit_trail', [])
        
        if not audit_trail:
            return "<p>No audit trail data available</p>"
        
        trail_html = ""
        for i, decision in enumerate(audit_trail):
            trail_html += f"""
            <div class="audit-item">
                <div class="audit-header">
                    <span class="audit-stage">Stage {i+1}: {decision.get('stage', 'Unknown').replace('_', ' ').title()}</span>
                    <span class="audit-confidence">Confidence: {decision.get('confidence', 0):.1%}</span>
                </div>
                <div class="audit-content">
                    <p><strong>Decision:</strong> {decision.get('articles_advanced', 0)} articles advanced</p>
                    <p><strong>Reasoning:</strong> {decision.get('decision_reasoning', 'No reasoning provided')}</p>
                </div>
            </div>
            """
        
        return trail_html

    def _generate_summary_statistics(self, run_data: Dict) -> str:
        """Generate summary statistics cards."""
        transparency = run_data.get('pipeline_transparency', {})
        summary = transparency.get('pipeline_summary', {})
        
        total_articles = summary.get('total_articles_processed', 0)
        final_stories = summary.get('final_stories_selected', 0)
        total_cost = transparency.get('total_cost', 0)
        total_time = transparency.get('total_execution_time', 0)
        advancement_rate = summary.get('overall_advancement_rate', 0)
        cost_per_story = summary.get('cost_per_story', 0)
        
        return f"""
        <div class="summary-card">
            <div class="summary-icon">
                <i class="fas fa-newspaper"></i>
            </div>
            <div class="summary-content">
                <h3>{total_articles:,}</h3>
                <p>Articles Processed</p>
            </div>
        </div>
        
        <div class="summary-card">
            <div class="summary-icon">
                <i class="fas fa-star"></i>
            </div>
            <div class="summary-content">
                <h3>{final_stories}</h3>
                <p>Stories Selected</p>
            </div>
        </div>
        
        <div class="summary-card">
            <div class="summary-icon">
                <i class="fas fa-dollar-sign"></i>
            </div>
            <div class="summary-content">
                <h3>${total_cost:.4f}</h3>
                <p>Total Cost</p>
            </div>
        </div>
        
        <div class="summary-card">
            <div class="summary-icon">
                <i class="fas fa-clock"></i>
            </div>
            <div class="summary-content">
                <h3>{total_time:.1f}s</h3>
                <p>Processing Time</p>
            </div>
        </div>
        
        <div class="summary-card">
            <div class="summary-icon">
                <i class="fas fa-filter"></i>
            </div>
            <div class="summary-content">
                <h3>{advancement_rate:.1%}</h3>
                <p>Advancement Rate</p>
            </div>
        </div>
        
        <div class="summary-card">
            <div class="summary-icon">
                <i class="fas fa-calculator"></i>
            </div>
            <div class="summary-content">
                <h3>${cost_per_story:.4f}</h3>
                <p>Cost per Story</p>
            </div>
        </div>
        """

    def _get_enhanced_dashboard_styles(self) -> str:
        """Get enhanced CSS styles for multi-stage dashboard."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .dashboard-container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            min-height: 100vh;
            box-shadow: 0 0 30px rgba(0,0,0,0.1);
        }
        
        .dashboard-header {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 2rem 0;
            text-align: center;
        }
        
        .header-content h1 {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header-info {
            display: flex;
            justify-content: center;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .date-badge, .run-badge, .status-badge {
            background: rgba(255,255,255,0.2);
            padding: 0.5rem 1rem;
            border-radius: 25px;
            font-size: 0.9rem;
            backdrop-filter: blur(10px);
        }
        
        .status-success {
            background: rgba(46, 204, 113, 0.8);
        }
        
        .dashboard-nav {
            background: #34495e;
            display: flex;
            justify-content: center;
            padding: 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .nav-btn {
            background: none;
            border: none;
            color: white;
            padding: 1rem 1.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 1rem;
        }
        
        .nav-btn:hover, .nav-btn.active {
            background: #2c3e50;
            transform: translateY(-2px);
        }
        
        .dashboard-main {
            padding: 2rem;
            min-height: 600px;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s ease-in;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 15px;
            display: flex;
            align-items: center;
            gap: 1rem;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
            transition: transform 0.3s ease;
        }
        
        .summary-card:hover {
            transform: translateY(-5px);
        }
        
        .summary-icon {
            font-size: 2.5rem;
            opacity: 0.8;
        }
        
        .summary-content h3 {
            font-size: 1.8rem;
            margin-bottom: 0.5rem;
        }
        
        .summary-content p {
            opacity: 0.9;
            font-size: 0.9rem;
        }
        
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 2rem;
        }
        
        .chart-card {
            background: white;
            border-radius: 15px;
            padding: 1.5rem;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
        }
        
        .chart-card.full-width {
            grid-column: 1 / -1;
        }
        
        .chart-card h3 {
            color: #2c3e50;
            margin-bottom: 1rem;
            font-size: 1.3rem;
            border-bottom: 2px solid #3498db;
            padding-bottom: 0.5rem;
        }
        
        .stage-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
        }
        
        .stage-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 1.5rem;
            border-left: 5px solid #3498db;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .stage-card h4 {
            color: #2c3e50;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }
        
        .stage-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem;
            background: white;
            border-radius: 5px;
            border: 1px solid #e0e0e0;
        }
        
        .stat-label {
            font-weight: 500;
            color: #555;
        }
        
        .stat-value {
            font-weight: bold;
            color: #3498db;
        }
        
        .stage-reasoning {
            background: #e8f5e8;
            padding: 1rem;
            border-radius: 5px;
            font-size: 0.9rem;
            border-left: 3px solid #27ae60;
        }
        
        .audit-trail {
            max-width: 1000px;
            margin: 0 auto;
        }
        
        .audit-item {
            background: white;
            border-radius: 10px;
            margin-bottom: 1rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border-left: 5px solid #e67e22;
        }
        
        .audit-header {
            background: #f8f9fa;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 10px 10px 0 0;
        }
        
        .audit-stage {
            font-weight: bold;
            color: #2c3e50;
        }
        
        .audit-confidence {
            background: #27ae60;
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
        }
        
        .audit-content {
            padding: 1rem;
        }
        
        .audit-content p {
            margin-bottom: 0.5rem;
            line-height: 1.6;
        }
        
        .dashboard-footer {
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 1rem;
            font-size: 0.9rem;
        }
        
        .dashboard-footer p {
            margin-bottom: 0.5rem;
        }
        
        @media (max-width: 768px) {
            .dashboard-nav {
                flex-direction: column;
            }
            
            .nav-btn {
                text-align: left;
                padding: 0.8rem 1rem;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }
            
            .summary-grid {
                grid-template-columns: 1fr;
            }
            
            .chart-grid {
                grid-template-columns: 1fr;
            }
            
            .stage-grid {
                grid-template-columns: 1fr;
            }
        }
        """

    def _get_enhanced_dashboard_javascript(self) -> str:
        """Get enhanced JavaScript for dashboard interactivity."""
        return """
        function showTab(tabName) {
            // Hide all tab contents
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all nav buttons
            const buttons = document.querySelectorAll('.nav-btn');
            buttons.forEach(button => {
                button.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked button
            event.target.classList.add('active');
        }
        
        // Auto-refresh functionality
        function initAutoRefresh() {
            setInterval(() => {
                const timestamp = new Date().toLocaleString();
                console.log(`Dashboard refreshed at ${timestamp}`);
            }, 300000); // Refresh every 5 minutes
        }
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            initAutoRefresh();
            
            // Set default active tab
            showTab('overview');
        });
        """

    def _generate_no_data_dashboard(self, date_str: str) -> str:
        """Generate dashboard when no data is available."""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Enhanced Dashboard - {date_str} (No Data)</title>
        </head>
        <body>
            <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
                <h1>Enhanced Multi-Stage Dashboard</h1>
                <p>No pipeline run data available for {date_str}</p>
                <p>Please run the pipeline to generate analysis data.</p>
            </div>
        </body>
        </html>
        """