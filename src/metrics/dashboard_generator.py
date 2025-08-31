"""
Dashboard generator for the newsletter metrics system.
Creates HTML/JS dashboard with Chart.js visualizations.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

try:
    from .collector import MetricsCollector
    from ..config import Config
    from ..logger import get_logger
except ImportError:
    # Fallback for standalone execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from metrics.collector import MetricsCollector
    from config import Config
    from logger import get_logger

logger = get_logger(__name__)

class DashboardGenerator:
    """Generates HTML dashboard with Chart.js visualizations."""

    def __init__(self, db_path: str = "data/metrics.db"):
        """Initialize dashboard generator."""
        self.collector = MetricsCollector(db_path)
        self.output_dir = Path("docs")  # Same as GitHub Pages output

    def generate_dashboard(self, output_path: str = "docs/dashboard.html") -> str:
        """
        Generate the complete dashboard HTML file.

        Args:
            output_path: Path where to save the dashboard

        Returns:
            Path to the generated dashboard
        """
        logger.info("Generating metrics dashboard...")

        # Get comprehensive stats
        stats = self.collector.get_comprehensive_stats(days=30)

        # Generate HTML content
        html_content = self._generate_html(stats)

        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Dashboard generated: {output_file}")
        return str(output_file)

    def _generate_html(self, stats: Dict[str, Any]) -> str:
        """Generate the complete HTML dashboard."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Metrics Dashboard - Geopolitical Daily</title>
    <meta name="description" content="Real-time metrics and analytics for the Geopolitical Daily newsletter pipeline">
    <link rel="stylesheet" href="assets/style.css">

    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/date-fns@2.29.3/index.min.js"></script>

    <style>
        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .metric-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #3182ce;
        }}

        .metric-title {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 4px;
        }}

        .metric-change {{
            font-size: 12px;
            color: #38a169;
        }}

        .metric-change.negative {{
            color: #e53e3e;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .chart-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #2d3748;
        }}

        .chart-wrapper {{
            position: relative;
            height: 300px;
        }}

        .data-table {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}

        .data-table table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .data-table th {{
            background: #f7fafc;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
        }}

        .data-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}

        .data-table tr:hover {{
            background: #f7fafc;
        }}

        .status-indicator {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }}

        .status-success {{ background: #38a169; }}
        .status-warning {{ background: #dd6b20; }}
        .status-error {{ background: #e53e3e; }}

        .last-updated {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 20px;
        }}

        @media (max-width: 768px) {{
            .dashboard-container {{
                padding: 10px;
            }}

            .metrics-grid {{
                grid-template-columns: 1fr;
            }}

            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">Newsletter Metrics Dashboard</p>
            <nav class="nav">
                <a href="index.html">Home</a>
                <a href="archive.html">Archive</a>
                <a href="about.html">About</a>
                <a href="dashboard.html">Dashboard</a>
                <a href="feed.xml">RSS</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="dashboard-container">
            <h1>Newsletter Pipeline Metrics</h1>
            <p class="dashboard-intro">Real-time analytics and performance metrics for the Geopolitical Daily newsletter generation pipeline.</p>

            {self._generate_metrics_cards(stats)}

            {self._generate_charts_section(stats)}

            {self._generate_tables_section(stats)}

            <div class="last-updated">
                Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
            </div>
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p>
                <a href="feed.xml">RSS Feed</a> |
                <a href="archive.html">Archive</a> |
                <a href="https://github.com/yourusername/geodaily">Source Code</a>
            </p>
        </div>
    </footer>

    <script>
        {self._generate_chart_scripts(stats)}
    </script>
</body>
</html>"""

    def _generate_metrics_cards(self, stats: Dict[str, Any]) -> str:
        """Generate the metrics cards section."""
        daily_stats = stats.get('daily_stats', {}).get('daily_stats', [])
        ai_stats = stats.get('ai_usage', {}).get('ai_stats', [])
        source_stats = stats.get('source_performance', {}).get('source_stats', [])

        # Calculate totals
        total_runs = sum(day['runs_count'] for day in daily_stats) if daily_stats else 0
        total_articles = sum(day['avg_articles'] * day['runs_count'] for day in daily_stats) if daily_stats else 0
        avg_articles = total_articles / total_runs if total_runs > 0 else 0

        total_cost = sum(day['total_cost'] for day in daily_stats) if daily_stats else 0
        total_tokens = sum(day['total_tokens'] for day in daily_stats) if daily_stats else 0

        # Source success rate
        avg_success_rate = sum(s['success_rate'] for s in source_stats) / len(source_stats) if source_stats else 0

        return f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">Total Articles Collected</div>
                <div class="metric-value">{int(avg_articles)}</div>
                <div class="metric-change">Last 30 days average</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Pipeline Runs</div>
                <div class="metric-value">{total_runs}</div>
                <div class="metric-change">Last 30 days</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">AI Cost</div>
                <div class="metric-value">${total_cost:.2f}</div>
                <div class="metric-change">Last 30 days total</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Source Success Rate</div>
                <div class="metric-value">{avg_success_rate:.1f}%</div>
                <div class="metric-change">Average across all sources</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">AI Tokens Used</div>
                <div class="metric-value">{int(total_tokens):,}</div>
                <div class="metric-change">Last 30 days total</div>
            </div>

            <div class="metric-card">
                <div class="metric-title">Active Sources</div>
                <div class="metric-value">{len(source_stats)}</div>
                <div class="metric-change">Currently monitored</div>
            </div>
        </div>"""

    def _generate_charts_section(self, stats: Dict[str, Any]) -> str:
        """Generate the charts section."""
        return """
        <div class="charts-grid">
            <div class="chart-container">
                <div class="chart-title">Daily Articles Collected</div>
                <div class="chart-wrapper">
                    <canvas id="articlesChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <div class="chart-title">AI Usage & Cost</div>
                <div class="chart-wrapper">
                    <canvas id="aiUsageChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <div class="chart-title">Source Performance</div>
                <div class="chart-wrapper">
                    <canvas id="sourcePerformanceChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <div class="chart-title">Processing Time Trends</div>
                <div class="chart-wrapper">
                    <canvas id="processingTimeChart"></canvas>
                </div>
            </div>
        </div>"""

    def _generate_tables_section(self, stats: Dict[str, Any]) -> str:
        """Generate the data tables section."""
        recent_runs = stats.get('recent_runs', [])
        source_stats = stats.get('source_performance', {}).get('source_stats', [])

        # Recent runs table
        runs_table = """
        <div class="data-table">
            <h3 style="margin: 0 0 15px 0; color: #2d3748;">Recent Pipeline Runs</h3>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Status</th>
                        <th>Articles</th>
                        <th>Stories</th>
                        <th>AI Cost</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>"""

        for run in recent_runs[:10]:
            status_class = "success" if run['status'] == "completed" else "error"
            runs_table += f"""
                    <tr>
                        <td>{run['run_date']}</td>
                        <td><span class="status-indicator status-{status_class}"></span>{run['status']}</td>
                        <td>{run['total_articles_collected']}</td>
                        <td>{run['stories_selected']}</td>
                        <td>${run['ai_cost']:.3f}</td>
                        <td>{run['processing_time_seconds']:.1f}s</td>
                    </tr>"""

        runs_table += """
                </tbody>
            </table>
        </div>"""

        # Source performance table
        source_table = """
        <div class="data-table">
            <h3 style="margin: 0 0 15px 0; color: #2d3748;">Source Performance (Last 30 Days)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Category</th>
                        <th>Articles</th>
                        <th>Success Rate</th>
                        <th>Avg Collection Time</th>
                    </tr>
                </thead>
                <tbody>"""

        for source in source_stats[:15]:
            success_class = "success" if source['success_rate'] >= 80 else ("warning" if source['success_rate'] >= 50 else "error")
            source_table += f"""
                    <tr>
                        <td>{source['source_name']}</td>
                        <td>{source['source_category']}</td>
                        <td>{source['total_articles']}</td>
                        <td><span class="status-indicator status-{success_class}"></span>{source['success_rate']:.1f}%</td>
                        <td>{source['avg_collection_time']:.2f}s</td>
                    </tr>"""

        source_table += """
                </tbody>
            </table>
        </div>"""

        return runs_table + source_table

    def _generate_chart_scripts(self, stats: Dict[str, Any]) -> str:
        """Generate JavaScript for Chart.js visualizations."""
        daily_stats = stats.get('daily_stats', {}).get('daily_stats', [])
        ai_stats = stats.get('ai_usage', {}).get('ai_stats', [])
        source_stats = stats.get('source_performance', {}).get('source_stats', [])

        # Prepare data for charts
        dates = [day['date'] for day in daily_stats]
        articles_data = [day['avg_articles'] for day in daily_stats]
        cost_data = [day['avg_ai_cost'] for day in daily_stats]
        processing_times = [day['avg_processing_time'] for day in daily_stats]

        source_names = [s['source_name'][:15] + '...' if len(s['source_name']) > 15 else s['source_name'] for s in source_stats[:10]]
        source_success_rates = [s['success_rate'] for s in source_stats[:10]]

        return f"""
        // Daily Articles Chart
        const articlesCtx = document.getElementById('articlesChart').getContext('2d');
        new Chart(articlesCtx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [{{
                    label: 'Articles Collected',
                    data: {json.dumps(articles_data)},
                    borderColor: '#3182ce',
                    backgroundColor: 'rgba(49, 130, 206, 0.1)',
                    tension: 0.4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Articles'
                        }}
                    }}
                }}
            }}
        }});

        // AI Usage Chart
        const aiUsageCtx = document.getElementById('aiUsageChart').getContext('2d');
        new Chart(aiUsageCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [{{
                    label: 'AI Cost ($)',
                    data: {json.dumps(cost_data)},
                    backgroundColor: '#38a169',
                    borderColor: '#2f855a',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Cost ($)'
                        }}
                    }}
                }}
            }}
        }});

        // Source Performance Chart
        const sourcePerformanceCtx = document.getElementById('sourcePerformanceChart').getContext('2d');
        new Chart(sourcePerformanceCtx, {{
            type: 'horizontalBar',
            data: {{
                labels: {json.dumps(source_names)},
                datasets: [{{
                    label: 'Success Rate (%)',
                    data: {json.dumps(source_success_rates)},
                    backgroundColor: '#dd6b20',
                    borderColor: '#c05621',
                    borderWidth: 1
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Success Rate (%)'
                        }}
                    }}
                }}
            }}
        }});

        // Processing Time Chart
        const processingTimeCtx = document.getElementById('processingTimeChart').getContext('2d');
        new Chart(processingTimeCtx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [{{
                    label: 'Processing Time (s)',
                    data: {json.dumps(processing_times)},
                    borderColor: '#805ad5',
                    backgroundColor: 'rgba(128, 90, 213, 0.1)',
                    tension: 0.4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Time (seconds)'
                        }}
                    }}
                }}
            }}
        }});
        """

    def update_dashboard(self):
        """Update the dashboard with latest data."""
        self.generate_dashboard()
        logger.info("Dashboard updated with latest metrics")