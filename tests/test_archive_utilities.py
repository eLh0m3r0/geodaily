"""
Tests for archive utility scripts (cleanup and dashboard generation).
"""

import pytest
import json
import tempfile
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestArchiveCleanup:
    """Test archive cleanup functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = Path(self.temp_dir) / "test_archive"
        self.archive_path.mkdir(parents=True)
        
        # Import cleanup module after setting up paths
        from cleanup_archives import ArchiveCleanup
        self.cleanup = ArchiveCleanup(archive_path=str(self.archive_path), dry_run=True)
        
        # Create test archive structure
        self._create_test_archive_structure()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_test_archive_structure(self):
        """Create test archive directory structure."""
        # Create date directories with different ages
        dates = [
            datetime.now() - timedelta(days=1),   # Recent - should not be removed
            datetime.now() - timedelta(days=15),  # Medium age
            datetime.now() - timedelta(days=35),  # Old - should be removed
            datetime.now() - timedelta(days=60),  # Very old - should be removed
        ]
        
        for i, date in enumerate(dates):
            date_str = date.strftime("%Y-%m-%d")
            date_dir = self.archive_path / date_str
            date_dir.mkdir()
            
            # Create successful run
            successful_run = date_dir / f"run_success_{i}"
            successful_run.mkdir()
            
            # Add files to make it look successful
            (successful_run / "final_newsletter.json").write_text('{"stories_count": 3}')
            (successful_run / "run_summary.json").write_text('{"status": "completed"}')
            (successful_run / "collected_articles.json").write_text('{"articles": []}')
            
            # Create failed run (missing success indicators)
            failed_run = date_dir / f"run_failed_{i}"
            failed_run.mkdir()
            (failed_run / "collected_articles.json").write_text('{"articles": []}')
            # Deliberately missing final_newsletter.json and run_summary.json
        
        # Create invalid directory name (should be ignored)
        invalid_dir = self.archive_path / "not_a_date"
        invalid_dir.mkdir()
    
    def test_cleanup_initialization(self):
        """Test that cleanup initializes correctly."""
        assert self.cleanup is not None
        assert self.cleanup.archive_path == self.archive_path
        assert self.cleanup.dry_run == True
        assert isinstance(self.cleanup.stats, dict)
    
    def test_find_date_directories(self):
        """Test finding valid date directories."""
        date_dirs = self.cleanup._find_date_directories()
        
        assert len(date_dirs) == 4  # Should find 4 valid date directories
        
        # Verify directories are sorted
        date_strings = [d.name for d in date_dirs]
        assert date_strings == sorted(date_strings)
    
    def test_is_valid_date_dir(self):
        """Test date directory validation."""
        assert self.cleanup._is_valid_date_dir("2024-01-01") == True
        assert self.cleanup._is_valid_date_dir("2024-12-31") == True
        assert self.cleanup._is_valid_date_dir("not_a_date") == False
        assert self.cleanup._is_valid_date_dir("2024-13-01") == False  # Invalid month
        assert self.cleanup._is_valid_date_dir("2024-01-32") == False  # Invalid day
    
    def test_find_failed_runs(self):
        """Test finding failed runs in a directory."""
        # Get a test date directory
        date_dirs = self.cleanup._find_date_directories()
        test_date_dir = date_dirs[0]
        
        failed_runs = self.cleanup._find_failed_runs(test_date_dir)
        
        # Should find 1 failed run (the one missing success indicators)
        assert len(failed_runs) == 1
        assert "run_failed_" in failed_runs[0].name
    
    def test_get_directory_size(self):
        """Test calculating directory size."""
        date_dirs = self.cleanup._find_date_directories()
        test_dir = date_dirs[0]
        
        size = self.cleanup._get_directory_size(test_dir)
        
        assert size > 0  # Should have some size from the test files
        assert isinstance(size, int)
    
    def test_count_files_in_directory(self):
        """Test counting files in directory."""
        date_dirs = self.cleanup._find_date_directories()
        test_dir = date_dirs[0]
        
        file_count = self.cleanup._count_files_in_directory(test_dir)
        
        assert file_count > 0  # Should have test files
        assert isinstance(file_count, int)
    
    def test_format_bytes(self):
        """Test byte formatting."""
        assert self.cleanup._format_bytes(1024) == "1.0 KB"
        assert self.cleanup._format_bytes(1048576) == "1.0 MB"
        assert self.cleanup._format_bytes(1073741824) == "1.0 GB"
        assert self.cleanup._format_bytes(512) == "512.0 B"
    
    def test_run_cleanup_dry_run(self):
        """Test cleanup in dry-run mode."""
        stats = self.cleanup.run_cleanup(retention_days=30, force=True)
        
        assert isinstance(stats, dict)
        assert 'directories_removed' in stats
        assert 'files_removed' in stats
        assert 'space_freed_bytes' in stats
        
        # In dry run, no files should actually be removed
        assert stats['directories_removed'] == 0
        assert stats['files_removed'] == 0
        assert stats['space_freed_bytes'] == 0
        
        # But directories should still exist
        date_dirs = self.cleanup._find_date_directories()
        assert len(date_dirs) == 4
    
    def test_run_cleanup_real_mode(self):
        """Test cleanup in real mode."""
        # Create non-dry-run cleanup
        from cleanup_archives import ArchiveCleanup
        real_cleanup = ArchiveCleanup(archive_path=str(self.archive_path), dry_run=False)
        
        stats = real_cleanup.run_cleanup(retention_days=30, force=True)
        
        assert isinstance(stats, dict)
        
        # Should have removed old directories (35 and 60 days old)
        assert stats['directories_removed'] >= 2
        assert stats['files_removed'] > 0
        assert stats['space_freed_bytes'] > 0
        
        # Verify old directories are gone
        remaining_dirs = real_cleanup._find_date_directories()
        assert len(remaining_dirs) <= 2  # Should keep recent ones
    
    def test_deep_clean_mode(self):
        """Test deep clean functionality."""
        stats = self.cleanup.run_cleanup(
            retention_days=30,
            deep_clean=True,
            force=True
        )
        
        # Deep clean should identify failed runs for partial cleanup
        assert isinstance(stats, dict)
    
    @patch('builtins.input', return_value='n')
    def test_confirm_cleanup_no(self, mock_input):
        """Test cleanup confirmation - user says no."""
        non_dry_cleanup = self.cleanup.__class__(archive_path=str(self.archive_path), dry_run=False)
        
        stats = non_dry_cleanup.run_cleanup(retention_days=30, force=False)
        
        # Should not proceed with cleanup
        assert stats['directories_removed'] == 0
    
    @patch('builtins.input', return_value='y')
    def test_confirm_cleanup_yes(self, mock_input):
        """Test cleanup confirmation - user says yes."""
        non_dry_cleanup = self.cleanup.__class__(archive_path=str(self.archive_path), dry_run=False)
        
        stats = non_dry_cleanup.run_cleanup(retention_days=30, force=False)
        
        # Should proceed with cleanup
        assert isinstance(stats, dict)


class TestDashboardGenerator:
    """Test dashboard generation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = Path(self.temp_dir) / "test_archive"
        self.output_path = Path(self.temp_dir) / "dashboards"
        
        # Create test archive structure
        self._create_test_archive_structure()
        
        # Import after setting up paths
        sys.path.insert(0, str(Path(__file__).parent.parent))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_test_archive_structure(self):
        """Create test archive directory structure for dashboard testing."""
        # Create multiple date directories
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        
        for date_str in dates:
            date_dir = self.archive_path / date_str
            date_dir.mkdir(parents=True)
            
            # Create test run
            run_dir = date_dir / f"run_test_{date_str.replace('-', '')}"
            run_dir.mkdir()
            
            # Create test data files
            self._create_test_run_data(run_dir, date_str)
    
    def _create_test_run_data(self, run_dir, date_str):
        """Create test run data files."""
        # Collected articles
        collected_articles = {
            "timestamp": f"{date_str}T12:00:00",
            "articles": [
                {
                    "title": f"Test Article {date_str}",
                    "source": "Test Source",
                    "url": f"https://example.com/{date_str}",
                    "category": "mainstream"
                }
            ],
            "collection_stats": {
                "total_sources": 5,
                "successful_sources": 4,
                "total_articles": 10
            }
        }
        
        # AI requests
        ai_requests = {
            "requests": [
                {
                    "request_id": f"req-{date_str}",
                    "timestamp": f"{date_str}T12:01:00",
                    "prompt": f"Test prompt for {date_str}",
                    "cluster_index": 0
                }
            ]
        }
        
        # AI responses
        ai_responses = {
            "responses": [
                {
                    "request_id": f"req-{date_str}",
                    "timestamp": f"{date_str}T12:01:30",
                    "cost": 0.05,
                    "processing_time": 2.5,
                    "model": "claude-3-haiku-20240307"
                }
            ]
        }
        
        # Run summary
        run_summary = {
            "run_id": f"test-{date_str.replace('-', '')}",
            "start_time": f"{date_str}T12:00:00",
            "end_time": f"{date_str}T12:05:00",
            "duration_seconds": 300,
            "status": "completed",
            "statistics": {
                "total_articles_collected": 10,
                "total_ai_requests": 1,
                "total_cost": 0.05
            }
        }
        
        # Write files
        with open(run_dir / "collected_articles.json", 'w') as f:
            json.dump(collected_articles, f)
        
        with open(run_dir / "ai_requests.json", 'w') as f:
            json.dump(ai_requests, f)
        
        with open(run_dir / "ai_responses.json", 'w') as f:
            json.dump(ai_responses, f)
        
        with open(run_dir / "run_summary.json", 'w') as f:
            json.dump(run_summary, f)
    
    @patch('sys.argv', ['generate_dashboard.py', '--archive-path'])
    def test_dashboard_generator_main_function(self):
        """Test the main dashboard generator function."""
        # Import generate_dashboard module
        try:
            import generate_dashboard
            # Test that module can be imported without errors
            assert hasattr(generate_dashboard, 'main')
        except ImportError as e:
            # If import fails, it's likely due to path issues in test environment
            pytest.skip(f"Could not import generate_dashboard module: {e}")
    
    def test_generate_dashboard_index(self):
        """Test generating dashboard index HTML."""
        # Create test dashboard files
        dashboard_files = [
            str(self.output_path / "dashboard_2024-01-01.html"),
            str(self.output_path / "dashboard_2024-01-02.html"),
            str(self.output_path / "summary_7days.html")
        ]
        
        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Create dummy dashboard files
        for file_path in dashboard_files:
            Path(file_path).write_text("<html><body>Test Dashboard</body></html>")
        
        # Import and test index generation
        try:
            import generate_dashboard
            index_path = generate_dashboard.generate_dashboard_index(dashboard_files, self.output_path)
            
            assert Path(index_path).exists()
            assert Path(index_path).name == "index.html"
            
            # Check index content
            with open(index_path) as f:
                html_content = f.read()
            
            assert "GeoPolitical Daily Dashboards" in html_content
            assert "dashboard_2024-01-01.html" in html_content
            assert "summary_7days.html" in html_content
        except ImportError:
            pytest.skip("Could not import generate_dashboard module")


class TestUtilityScriptsIntegration:
    """Integration tests for utility scripts."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = Path(self.temp_dir) / "integration_archive"
        
        # Create realistic archive structure
        self._create_realistic_archive_structure()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_realistic_archive_structure(self):
        """Create a realistic archive structure for integration testing."""
        # Create archives for last 45 days
        for days_ago in range(45):
            date = datetime.now() - timedelta(days=days_ago)
            date_str = date.strftime("%Y-%m-%d")
            
            date_dir = self.archive_path / date_str
            date_dir.mkdir(parents=True)
            
            # Create 1-3 runs per day
            num_runs = 1 if days_ago < 30 else 2  # More runs for older days
            
            for run_num in range(num_runs):
                run_id = f"run_{date_str.replace('-', '')}_{run_num}"
                run_dir = date_dir / run_id
                run_dir.mkdir()
                
                # Create files with realistic sizes
                self._create_realistic_run_data(run_dir, date_str, run_num)
    
    def _create_realistic_run_data(self, run_dir, date_str, run_num):
        """Create realistic run data for testing."""
        # Large collected articles file
        articles = []
        for i in range(100):  # 100 articles per run
            articles.append({
                "title": f"Article {i} for {date_str}",
                "url": f"https://example.com/article_{i}_{date_str}",
                "content": "Lorem ipsum " * 100,  # Make content larger
                "source": f"Source {i % 10}",
                "category": "mainstream"
            })
        
        collected_articles = {
            "timestamp": f"{date_str}T12:00:00",
            "articles": articles,
            "collection_stats": {
                "total_sources": 20,
                "successful_sources": 18,
                "total_articles": len(articles)
            }
        }
        
        # Multiple AI requests and responses
        requests = []
        responses = []
        total_cost = 0
        
        for i in range(5):  # 5 AI requests per run
            request_id = f"req-{date_str}-{run_num}-{i}"
            cost = 0.02 + (i * 0.01)  # Varying costs
            total_cost += cost
            
            requests.append({
                "request_id": request_id,
                "timestamp": f"{date_str}T12:{i:02d}:00",
                "prompt": f"Analyze cluster {i} for {date_str}" + " very long prompt " * 50,
                "cluster_index": i,
                "articles_summary": "Long summary " * 100
            })
            
            responses.append({
                "request_id": request_id,
                "timestamp": f"{date_str}T12:{i:02d}:30",
                "response": f"Analysis result {i}" + " detailed response " * 200,
                "cost": cost,
                "processing_time": 2.5 + i,
                "model": "claude-3-haiku-20240307"
            })
        
        # Run summary
        run_summary = {
            "run_id": f"test-{date_str.replace('-', '')}-{run_num}",
            "start_time": f"{date_str}T12:00:00",
            "end_time": f"{date_str}T12:30:00",
            "duration_seconds": 1800,
            "status": "completed",
            "statistics": {
                "total_articles_collected": len(articles),
                "total_ai_requests": len(requests),
                "total_cost": total_cost
            }
        }
        
        # Newsletter data
        newsletter_data = {
            "title": f"Newsletter for {date_str}",
            "date": date_str,
            "stories": [f"Story {i}" for i in range(5)],
            "stories_count": 5
        }
        
        newsletter_html = f"""
        <html>
        <head><title>Newsletter {date_str}</title></head>
        <body>
        <h1>Newsletter for {date_str}</h1>
        {'<p>Newsletter content paragraph</p>' * 50}
        </body>
        </html>
        """
        
        # Write all files
        files_to_write = [
            ("collected_articles.json", collected_articles),
            ("ai_requests.json", {"requests": requests}),
            ("ai_responses.json", {"responses": responses}),
            ("run_summary.json", run_summary),
            ("final_newsletter.json", newsletter_data)
        ]
        
        for filename, data in files_to_write:
            with open(run_dir / filename, 'w') as f:
                json.dump(data, f, indent=2)
        
        # Write HTML file separately
        with open(run_dir / "final_newsletter.html", 'w') as f:
            f.write(newsletter_html)
    
    def test_cleanup_and_dashboard_workflow(self):
        """Test complete cleanup and dashboard generation workflow."""
        # Test cleanup - dry run first
        from cleanup_archives import ArchiveCleanup
        cleanup = ArchiveCleanup(archive_path=str(self.archive_path), dry_run=True)
        
        dry_run_stats = cleanup.run_cleanup(retention_days=30, force=True)
        
        # Verify dry run identified items for cleanup
        assert dry_run_stats['directories_removed'] == 0  # Dry run doesn't actually remove
        
        # Check that archive has expected structure
        date_dirs = cleanup._find_date_directories()
        assert len(date_dirs) == 45  # Should find all 45 date directories
        
        # Test that old directories would be identified for removal
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)
        old_dirs = [d for d in date_dirs if datetime.strptime(d.name, "%Y-%m-%d") < cutoff_date]
        assert len(old_dirs) == 15  # Days 30-44 (15 days)
        
        # Test dashboard generation on this data
        from src.dashboard.debug_dashboard import DebugDashboard
        dashboard_output = Path(self.temp_dir) / "test_dashboards"
        dashboard = DebugDashboard(
            archive_path=str(self.archive_path),
            output_path=dashboard_output
        )
        
        # Generate dashboard for recent date
        recent_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        dashboard_path = dashboard.generate_dashboard(recent_date)
        
        assert Path(dashboard_path).exists()
        
        # Verify dashboard contains expected data
        with open(dashboard_path) as f:
            html_content = f.read()
        
        assert recent_date in html_content
        assert "Article" in html_content  # Should contain our test articles
        assert "claude-3-haiku" in html_content  # Should show AI model used
        
        # Generate summary dashboard
        summary_path = dashboard.generate_summary_dashboard(days=7)
        
        assert Path(summary_path).exists()
        
        # Verify summary dashboard
        with open(summary_path) as f:
            summary_html = f.read()
        
        assert "Summary Dashboard" in summary_html
        assert "Last 7 days" in summary_html
    
    def test_archive_size_reporting(self):
        """Test that utilities correctly report archive sizes."""
        from cleanup_archives import ArchiveCleanup
        cleanup = ArchiveCleanup(archive_path=str(self.archive_path), dry_run=True)
        
        # Get total archive size
        total_size = cleanup._get_directory_size(self.archive_path)
        assert total_size > 1024 * 1024  # Should be > 1MB with all our test data
        
        # Test size formatting
        formatted_size = cleanup._format_bytes(total_size)
        assert any(unit in formatted_size for unit in ['KB', 'MB', 'GB'])
        
        # Test archive statistics from dashboard
        from src.dashboard.debug_dashboard import DebugDashboard
        dashboard = DebugDashboard(archive_path=str(self.archive_path))
        
        stats = dashboard._get_archive_summary(days=45)
        
        assert stats['total_runs'] == 60  # 45 days * avg 1.33 runs per day  
        assert stats['total_articles'] > 1000  # Should have thousands of test articles
        assert stats['total_cost'] > 0.1  # Should have accumulated some cost
        assert 'oldest_run_date' in stats
        assert 'newest_run_date' in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])