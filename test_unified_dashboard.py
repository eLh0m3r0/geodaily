#!/usr/bin/env python3
"""
Test the unified dashboard data retrieval independently.
"""
import json
import os
from pathlib import Path
from datetime import datetime

def test_dashboard_data():
    """Test dashboard data retrieval without imports."""
    print("Testing unified dashboard data retrieval...")
    
    # Check AI archive path
    archive_path = Path("ai_archive")
    if not archive_path.exists():
        print("❌ No ai_archive directory found")
        return
    
    # Find most recent run
    recent_dates = sorted([d.name for d in archive_path.iterdir() 
                          if d.is_dir() and len(d.name) == 10], reverse=True)
    
    print(f"Found dates: {recent_dates}")
    
    for date_str in recent_dates[:3]:
        date_path = archive_path / date_str
        runs = sorted([r for r in date_path.iterdir() 
                      if r.is_dir() and r.name.startswith("run_")], 
                     reverse=True)
        
        print(f"Date {date_str}: {len(runs)} runs")
        
        for run_path in runs[:2]:
            print(f"  Checking run: {run_path.name}")
            
            # Check run summary
            summary_path = run_path / "run_summary.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    summary_data = json.load(f)
                    
                articles_count = summary_data.get("statistics", {}).get("total_articles_collected", 0)
                print(f"    ✅ Found {articles_count} articles collected")
                
                if articles_count > 0:
                    print(f"    📊 Run {run_path.name} has valid data")
                    return {
                        "run_id": run_path.name,
                        "date": date_str,
                        "articles_count": articles_count,
                        "stories_selected": 4,  # Typical selection
                        "total_cost": 0.05,  # Estimate
                        "success": True
                    }
            else:
                print(f"    ⚠️  No run_summary.json in {run_path.name}")
    
    print("❌ No valid run data found")
    return None

if __name__ == "__main__":
    result = test_dashboard_data()
    if result:
        print(f"\n✅ Dashboard should show:")
        print(f"   Articles: {result['articles_count']}")
        print(f"   Stories: {result['stories_selected']}")
        print(f"   Cost: ${result['total_cost']:.4f}")
        print(f"   Date: {result['date']}")
    else:
        print("\n❌ No data available for dashboard")