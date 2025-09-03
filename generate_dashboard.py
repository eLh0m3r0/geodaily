#!/usr/bin/env python3
"""
Dashboard Generator Utility Script
Generates comprehensive debug dashboards for GeoPolitical Daily pipeline monitoring.

Usage:
    python generate_dashboard.py                    # Generate today's dashboard
    python generate_dashboard.py --date 2025-09-03  # Generate for specific date
    python generate_dashboard.py --summary --days 7 # Generate 7-day summary
    python generate_dashboard.py --all             # Generate all available dashboards
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.dashboard.debug_dashboard import DebugDashboard
from src.config import Config
from src.logger import get_logger

logger = get_logger("dashboard_generator")


def main():
    parser = argparse.ArgumentParser(description="Generate GeoPolitical Daily debug dashboards")
    parser.add_argument("--date", type=str, help="Generate dashboard for specific date (YYYY-MM-DD)")
    parser.add_argument("--summary", action="store_true", help="Generate summary dashboard")
    parser.add_argument("--days", type=int, default=7, help="Number of days for summary (default: 7)")
    parser.add_argument("--all", action="store_true", help="Generate dashboards for all available dates")
    parser.add_argument("--archive-path", type=str, help="Custom path to AI archive")
    parser.add_argument("--output-path", type=str, help="Custom output path for dashboards")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize dashboard generator
    archive_path = args.archive_path or getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive')
    dashboard = DebugDashboard(archive_path)
    
    if args.output_path:
        dashboard.output_path = Path(args.output_path)
        dashboard.output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("🚀 Starting Dashboard Generation")
    logger.info(f"Archive path: {dashboard.archive_path}")
    logger.info(f"Output path: {dashboard.output_path}")
    
    generated_files = []
    
    try:
        if args.summary:
            logger.info(f"📊 Generating {args.days}-day summary dashboard...")
            dashboard_path = dashboard.generate_summary_dashboard(days=args.days)
            generated_files.append(dashboard_path)
            logger.info(f"✅ Summary dashboard generated: {dashboard_path}")
        
        elif args.all:
            logger.info("📚 Generating dashboards for all available dates...")
            archive_base = Path(archive_path)
            
            if not archive_base.exists():
                logger.error(f"❌ Archive path does not exist: {archive_base}")
                return 1
            
            # Find all date directories
            date_dirs = [d for d in archive_base.iterdir() 
                        if d.is_dir() and len(d.name) == 10 and d.name.count('-') == 2]
            
            if not date_dirs:
                logger.warning("⚠️ No date directories found in archive")
                return 0
            
            logger.info(f"Found {len(date_dirs)} date directories")
            
            for date_dir in sorted(date_dirs):
                date_str = date_dir.name
                logger.info(f"Generating dashboard for {date_str}...")
                
                try:
                    dashboard_path = dashboard.generate_dashboard(date_str)
                    generated_files.append(dashboard_path)
                    logger.info(f"✅ Generated: {dashboard_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to generate dashboard for {date_str}: {e}")
            
            # Also generate summary
            logger.info("Generating summary dashboard...")
            summary_path = dashboard.generate_summary_dashboard(days=30)
            generated_files.append(summary_path)
        
        else:
            # Generate for specific date or today
            target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
            
            logger.info(f"📅 Generating dashboard for {target_date}...")
            dashboard_path = dashboard.generate_dashboard(target_date)
            generated_files.append(dashboard_path)
            logger.info(f"✅ Dashboard generated: {dashboard_path}")
        
        # Summary of generated files
        logger.info(f"🎉 Dashboard generation complete!")
        logger.info(f"📁 Generated {len(generated_files)} dashboard(s):")
        
        for file_path in generated_files:
            file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
            logger.info(f"   • {file_path} ({file_size:,} bytes)")
        
        # Generate index file linking to all dashboards
        if len(generated_files) > 1:
            index_path = generate_dashboard_index(generated_files, dashboard.output_path)
            logger.info(f"📋 Index file generated: {index_path}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("⚠️ Dashboard generation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Dashboard generation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def generate_dashboard_index(dashboard_files, output_path):
    """Generate an index HTML file linking to all dashboards."""
    
    index_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>📊 GeoPolitical Daily Dashboards Index</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            margin: 0;
            padding: 2rem;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 2rem;
        }
        .dashboards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
        }
        .dashboard-card {
            background: #f8f9fa;
            padding: 1.5rem;
            border-radius: 10px;
            border: 1px solid #e9ecef;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .dashboard-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        .dashboard-card h3 {
            color: #2c3e50;
            margin-bottom: 1rem;
        }
        .dashboard-link {
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 0.5rem 1rem;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.2s ease;
        }
        .dashboard-link:hover {
            background: #2980b9;
        }
        .meta-info {
            margin-top: 0.5rem;
            font-size: 0.9rem;
            color: #666;
        }
        .summary-section {
            background: #e8f4fd;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            text-align: center;
        }
        .last-updated {
            text-align: center;
            color: #666;
            font-size: 0.9rem;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e9ecef;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 GeoPolitical Daily Dashboards</h1>
        
        <div class="summary-section">
            <h2>📋 Available Dashboards</h2>
            <p>Total dashboards generated: <strong>{total_dashboards}</strong></p>
            <p>Last updated: <strong>{last_updated}</strong></p>
        </div>
        
        <div class="dashboards-grid">
    '''.format(
        total_dashboards=len(dashboard_files),
        last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    # Sort files by type - summaries first, then daily dashboards
    summary_files = [f for f in dashboard_files if 'summary' in Path(f).name]
    daily_files = [f for f in dashboard_files if 'summary' not in Path(f).name]
    sorted_files = summary_files + sorted(daily_files, reverse=True)
    
    for dashboard_file in sorted_files:
        file_path = Path(dashboard_file)
        filename = file_path.name
        relative_path = file_path.name  # Since we're in the same directory
        
        # Determine dashboard type and title
        if 'summary' in filename:
            days_match = filename.split('_')
            if len(days_match) >= 2:
                title = f"📈 Summary Dashboard ({days_match[1].replace('.html', '')})"
            else:
                title = "📈 Summary Dashboard"
            description = "Multi-day overview with trends and aggregated metrics"
        else:
            # Extract date from filename
            date_part = filename.replace('dashboard_', '').replace('.html', '')
            title = f"📅 Daily Dashboard - {date_part}"
            description = f"Detailed analysis for {date_part}"
        
        # Get file size and modification time
        file_size = file_path.stat().st_size if file_path.exists() else 0
        file_size_mb = file_size / 1024 / 1024
        
        index_html += f'''
            <div class="dashboard-card">
                <h3>{title}</h3>
                <p>{description}</p>
                <a href="{relative_path}" class="dashboard-link">📊 Open Dashboard</a>
                <div class="meta-info">
                    Size: {file_size_mb:.2f} MB
                </div>
            </div>
        '''
    
    index_html += '''
        </div>
        
        <div class="last-updated">
            <p>🔄 Dashboards auto-refresh every 60 seconds</p>
            <p>🏠 Return to <a href="../index.html">main site</a></p>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(() => location.reload(), 300000);
    </script>
</body>
</html>
    '''
    
    index_path = output_path / "index.html"
    index_path.write_text(index_html)
    return str(index_path)


if __name__ == "__main__":
    exit(main())