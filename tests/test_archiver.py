"""
Tests for AI data archiver and dashboard functionality.
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.models import Article, AIAnalysis, SourceCategory, SourceTier
from src.archiver.ai_data_archiver import AIDataArchiver
from src.dashboard.debug_dashboard import DebugDashboard

class TestAIDataArchiver:
    """Test AI data archiving functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = Path(self.temp_dir) / "test_archive"
        self.archiver = AIDataArchiver(archive_path=str(self.archive_path))
        
        # Create test articles
        self.test_articles = [
            Article(
                title="Test Article 1",
                url="https://example.com/article1",
                summary="Test summary 1",
                content="Test content 1",
                source="Test Source 1",
                published_date=datetime.now(),
                category=SourceCategory.MAINSTREAM,
                tier=SourceTier.TIER1_RSS
            ),
            Article(
                title="Test Article 2", 
                url="https://example.com/article2",
                summary="Test summary 2",
                content="Test content 2",
                source="Test Source 2",
                published_date=datetime.now(),
                category=SourceCategory.ANALYSIS,
                tier=SourceTier.TIER2_SCRAPING
            )
        ]
        
        # Create test AI analysis
        self.test_analysis = AIAnalysis(
            selected_stories=[],
            total_cost=0.05,
            model_used="claude-3-haiku-20240307",
            processing_time=2.5,
            stories_found=3,
            relevance_scores=[0.8, 0.6, 0.4],
            content_types=["breaking_news", "analysis", "trend"]
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_archiver_initialization(self):
        """Test that archiver initializes correctly."""
        assert self.archiver is not None
        assert self.archiver.archive_path == self.archive_path
        assert self.archiver.run_id is None
        assert isinstance(self.archiver.stats, dict)
    
    def test_start_new_run(self):
        """Test starting a new archiving run."""
        run_id = self.archiver.start_new_run()
        
        assert run_id is not None
        assert self.archiver.run_id == run_id
        assert len(run_id) == 36  # UUID format
        
        # Check that run directory was created
        run_dir = self.archive_path / datetime.now().strftime("%Y-%m-%d") / f"run_{run_id}"
        assert run_dir.exists()
    
    def test_archive_collected_articles(self):
        """Test archiving collected articles."""
        # Start a run first
        self.archiver.start_new_run()
        
        # Archive articles
        self.archiver.archive_collected_articles(self.test_articles, {"test_stat": 1})
        
        # Check that articles were archived
        run_dir = self._get_current_run_dir()
        articles_file = run_dir / "collected_articles.json"
        
        assert articles_file.exists()
        
        with open(articles_file) as f:
            archived_data = json.load(f)
        
        assert len(archived_data["articles"]) == 2
        assert archived_data["collection_stats"]["test_stat"] == 1
        assert archived_data["articles"][0]["title"] == "Test Article 1"
    
    def test_archive_clusters(self):
        """Test archiving article clusters."""
        self.archiver.start_new_run()
        
        test_clusters = [
            {
                "main_article": self.test_articles[0].to_dict(),
                "related_articles": [self.test_articles[1].to_dict()],
                "cluster_score": 0.8,
                "topic": "Test Topic"
            }
        ]
        
        self.archiver.archive_clusters(test_clusters)
        
        # Check that clusters were archived
        run_dir = self._get_current_run_dir()
        clusters_file = run_dir / "clusters.json"
        
        assert clusters_file.exists()
        
        with open(clusters_file) as f:
            archived_clusters = json.load(f)
        
        assert len(archived_clusters["clusters"]) == 1
        assert archived_clusters["clusters"][0]["topic"] == "Test Topic"
    
    def test_archive_ai_request(self):
        """Test archiving AI requests."""
        self.archiver.start_new_run()
        
        request_id = self.archiver.archive_ai_request(
            prompt="Test prompt",
            articles_summary="Test articles summary",
            cluster_index=0,
            main_article_title="Test Main Article"
        )
        
        assert request_id is not None
        
        # Check that request was archived
        run_dir = self._get_current_run_dir()
        requests_file = run_dir / "ai_requests.json"
        
        assert requests_file.exists()
        
        with open(requests_file) as f:
            archived_requests = json.load(f)
        
        assert len(archived_requests["requests"]) == 1
        assert archived_requests["requests"][0]["prompt"] == "Test prompt"
        assert archived_requests["requests"][0]["request_id"] == request_id
    
    def test_archive_ai_response(self):
        """Test archiving AI responses."""
        self.archiver.start_new_run()
        
        # First create a request
        request_id = self.archiver.archive_ai_request(
            prompt="Test prompt",
            articles_summary="Test summary", 
            cluster_index=0,
            main_article_title="Test Article"
        )
        
        # Then archive response
        self.archiver.archive_ai_response(
            request_id=request_id,
            response="Test response",
            analysis=self.test_analysis,
            cost=0.05,
            processing_time=2.5
        )
        
        # Check that response was archived
        run_dir = self._get_current_run_dir()
        responses_file = run_dir / "ai_responses.json"
        
        assert responses_file.exists()
        
        with open(responses_file) as f:
            archived_responses = json.load(f)
        
        assert len(archived_responses["responses"]) == 1
        assert archived_responses["responses"][0]["request_id"] == request_id
        assert archived_responses["responses"][0]["response"] == "Test response"
        assert archived_responses["responses"][0]["cost"] == 0.05
    
    def test_archive_final_newsletter(self):
        """Test archiving final newsletter."""
        self.archiver.start_new_run()
        
        newsletter_data = {
            "title": "Test Newsletter",
            "date": "2024-01-01",
            "stories": ["Story 1", "Story 2"],
            "stories_count": 2
        }
        
        newsletter_html = "<html><body>Test Newsletter</body></html>"
        
        self.archiver.archive_final_newsletter(newsletter_data, newsletter_html)
        
        # Check that newsletter was archived
        run_dir = self._get_current_run_dir()
        newsletter_json = run_dir / "final_newsletter.json"
        newsletter_html_file = run_dir / "final_newsletter.html"
        
        assert newsletter_json.exists()
        assert newsletter_html_file.exists()
        
        with open(newsletter_json) as f:
            archived_newsletter = json.load(f)
        
        assert archived_newsletter["title"] == "Test Newsletter"
        assert archived_newsletter["stories_count"] == 2
        
        with open(newsletter_html_file) as f:
            html_content = f.read()
        
        assert "Test Newsletter" in html_content
    
    def test_create_run_summary(self):
        """Test creating run summary."""
        self.archiver.start_new_run()
        
        # Add some test data
        self.archiver.stats['total_articles_collected'] = 100
        self.archiver.stats['total_ai_requests'] = 5
        self.archiver.stats['total_cost'] = 0.25
        
        summary = self.archiver.create_run_summary()
        
        assert summary is not None
        assert summary['run_id'] == self.archiver.run_id
        assert summary['statistics']['total_articles_collected'] == 100
        assert summary['statistics']['total_ai_requests'] == 5
        assert summary['statistics']['total_cost'] == 0.25
        
        # Check that summary was saved
        run_dir = self._get_current_run_dir()
        summary_file = run_dir / "run_summary.json"
        
        assert summary_file.exists()
    
    def test_get_archive_statistics(self):
        """Test getting archive statistics."""
        # Create some test data
        self.archiver.start_new_run()
        self.archiver.archive_collected_articles(self.test_articles, {})
        
        stats = self.archiver.get_archive_statistics()
        
        assert stats is not None
        assert 'total_runs' in stats
        assert 'total_size_mb' in stats
        assert 'oldest_run_date' in stats
        assert 'newest_run_date' in stats
    
    def _get_current_run_dir(self):
        """Helper method to get current run directory."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.archive_path / date_str / f"run_{self.archiver.run_id}"


class TestDebugDashboard:
    """Test debug dashboard functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = Path(self.temp_dir) / "test_archive"
        self.output_path = Path(self.temp_dir) / "dashboards"
        
        # Create test archive structure
        self._create_test_archive_data()
        
        self.dashboard = DebugDashboard(
            archive_path=str(self.archive_path),
            output_path=self.output_path
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_test_archive_data(self):
        """Create test archive data structure."""
        # Create date directory
        date_dir = self.archive_path / "2024-01-01"
        date_dir.mkdir(parents=True)
        
        # Create run directory
        run_dir = date_dir / "run_test-123"
        run_dir.mkdir()
        
        # Create test data files
        collected_articles = {
            "timestamp": "2024-01-01T12:00:00",
            "articles": [
                {
                    "title": "Test Article",
                    "source": "Test Source",
                    "url": "https://example.com/test",
                    "category": "mainstream"
                }
            ],
            "collection_stats": {
                "total_sources": 1,
                "successful_sources": 1,
                "total_articles": 1
            }
        }
        
        ai_requests = {
            "requests": [
                {
                    "request_id": "req-123",
                    "timestamp": "2024-01-01T12:01:00",
                    "prompt": "Test prompt",
                    "cluster_index": 0
                }
            ]
        }
        
        ai_responses = {
            "responses": [
                {
                    "request_id": "req-123",
                    "timestamp": "2024-01-01T12:01:30",
                    "cost": 0.05,
                    "processing_time": 2.5,
                    "model": "claude-3-haiku-20240307"
                }
            ]
        }
        
        run_summary = {
            "run_id": "test-123",
            "start_time": "2024-01-01T12:00:00",
            "end_time": "2024-01-01T12:05:00",
            "duration_seconds": 300,
            "status": "completed",
            "statistics": {
                "total_articles_collected": 1,
                "total_ai_requests": 1,
                "total_cost": 0.05
            }
        }
        
        # Write test data files
        with open(run_dir / "collected_articles.json", 'w') as f:
            json.dump(collected_articles, f)
        
        with open(run_dir / "ai_requests.json", 'w') as f:
            json.dump(ai_requests, f)
        
        with open(run_dir / "ai_responses.json", 'w') as f:
            json.dump(ai_responses, f)
        
        with open(run_dir / "run_summary.json", 'w') as f:
            json.dump(run_summary, f)
    
    def test_dashboard_initialization(self):
        """Test that dashboard initializes correctly."""
        assert self.dashboard is not None
        assert self.dashboard.archive_path == self.archive_path
        assert self.dashboard.output_path == self.output_path
    
    def test_load_run_data(self):
        """Test loading run data."""
        run_data = self.dashboard._load_run_data("2024-01-01", "run_test-123")
        
        assert run_data is not None
        assert 'collected_articles' in run_data
        assert 'ai_requests' in run_data
        assert 'ai_responses' in run_data  
        assert 'run_summary' in run_data
        
        # Check data content
        assert len(run_data['collected_articles']['articles']) == 1
        assert len(run_data['ai_requests']['requests']) == 1
        assert len(run_data['ai_responses']['responses']) == 1
        assert run_data['run_summary']['run_id'] == "test-123"
    
    def test_generate_dashboard(self):
        """Test generating dashboard HTML."""
        dashboard_path = self.dashboard.generate_dashboard("2024-01-01")
        
        assert dashboard_path is not None
        assert Path(dashboard_path).exists()
        assert Path(dashboard_path).suffix == '.html'
        
        # Check that HTML contains expected content
        with open(dashboard_path) as f:
            html_content = f.read()
        
        assert "GeoPolitical Daily Debug Dashboard" in html_content
        assert "2024-01-01" in html_content
        assert "Test Article" in html_content
    
    def test_generate_summary_dashboard(self):
        """Test generating summary dashboard."""
        dashboard_path = self.dashboard.generate_summary_dashboard(days=7)
        
        assert dashboard_path is not None
        assert Path(dashboard_path).exists()
        assert "summary" in Path(dashboard_path).name.lower()
        
        # Check that HTML contains expected content
        with open(dashboard_path) as f:
            html_content = f.read()
        
        assert "Summary Dashboard" in html_content
        assert "Last 7 days" in html_content
    
    @patch('plotly.graph_objects.Figure.to_html')
    def test_create_source_performance_chart(self, mock_to_html):
        """Test creating source performance chart."""
        mock_to_html.return_value = "<div>Mock chart</div>"
        
        run_data = self.dashboard._load_run_data("2024-01-01", "run_test-123")
        chart_html = self.dashboard._create_source_performance_chart(run_data)
        
        assert chart_html is not None
        assert "Mock chart" in chart_html
        mock_to_html.assert_called_once()
    
    @patch('plotly.graph_objects.Figure.to_html')  
    def test_create_ai_cost_chart(self, mock_to_html):
        """Test creating AI cost chart."""
        mock_to_html.return_value = "<div>Mock cost chart</div>"
        
        run_data = self.dashboard._load_run_data("2024-01-01", "run_test-123")
        chart_html = self.dashboard._create_ai_cost_chart(run_data)
        
        assert chart_html is not None
        assert "Mock cost chart" in chart_html
        mock_to_html.assert_called_once()
    
    def test_find_available_dates(self):
        """Test finding available dates in archive."""
        dates = self.dashboard._find_available_dates()
        
        assert len(dates) == 1
        assert "2024-01-01" in dates
    
    def test_get_archive_summary(self):
        """Test getting archive summary statistics."""
        summary = self.dashboard._get_archive_summary(days=30)
        
        assert summary is not None
        assert 'total_runs' in summary
        assert 'date_range' in summary
        assert 'total_articles' in summary
        assert 'total_cost' in summary
        
        assert summary['total_runs'] == 1
        assert summary['total_articles'] == 1
        assert summary['total_cost'] == 0.05

class TestArchiverIntegration:
    """Integration tests for archiver with other components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.archive_path = Path(self.temp_dir) / "integration_archive"
        self.archiver = AIDataArchiver(archive_path=str(self.archive_path))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    @patch('src.config.Config.AI_ARCHIVE_ENABLED', True)
    def test_archiver_config_integration(self):
        """Test that archiver respects configuration settings."""
        from src.config import Config
        
        # Test that config validation includes archive settings
        with patch('src.config.Config.AI_ARCHIVE_PATH', '/invalid/path/that/cannot/be/created/readonly'):
            # This should not fail since we're not actually creating directories
            missing = Config.validate_config()
            # We just check that validation runs without crashing
            assert isinstance(missing, list)
    
    def test_full_archive_workflow(self):
        """Test complete archiving workflow."""
        # Start run
        run_id = self.archiver.start_new_run()
        
        # Archive articles
        test_articles = [
            Article(
                title="Integration Test Article",
                url="https://example.com/integration",
                summary="Integration test summary",
                content="Integration test content",
                source="Integration Test Source",
                published_date=datetime.now(),
                category=SourceCategory.MAINSTREAM,
                tier=SourceTier.TIER1_RSS
            )
        ]
        
        self.archiver.archive_collected_articles(test_articles, {"integration_test": True})
        
        # Archive AI request and response  
        request_id = self.archiver.archive_ai_request(
            prompt="Integration test prompt",
            articles_summary="Integration test articles",
            cluster_index=0,
            main_article_title="Integration Test Article"
        )
        
        test_analysis = AIAnalysis(
            selected_stories=[],
            total_cost=0.10,
            model_used="claude-3-haiku-20240307",
            processing_time=3.0,
            stories_found=1,
            relevance_scores=[0.9],
            content_types=["breaking_news"]
        )
        
        self.archiver.archive_ai_response(
            request_id=request_id,
            response="Integration test response",
            analysis=test_analysis,
            cost=0.10,
            processing_time=3.0
        )
        
        # Archive newsletter
        newsletter_data = {
            "title": "Integration Test Newsletter",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "stories": ["Integration Story"],
            "stories_count": 1
        }
        
        newsletter_html = "<html><body>Integration Test Newsletter</body></html>"
        
        self.archiver.archive_final_newsletter(newsletter_data, newsletter_html)
        
        # Create summary
        summary = self.archiver.create_run_summary()
        
        # Verify all files were created
        date_str = datetime.now().strftime("%Y-%m-%d")
        run_dir = self.archive_path / date_str / f"run_{run_id}"
        
        expected_files = [
            "collected_articles.json",
            "ai_requests.json", 
            "ai_responses.json",
            "final_newsletter.json",
            "final_newsletter.html",
            "run_summary.json"
        ]
        
        for filename in expected_files:
            file_path = run_dir / filename
            assert file_path.exists(), f"Expected file {filename} was not created"
        
        # Test dashboard generation
        dashboard = DebugDashboard(archive_path=str(self.archive_path))
        dashboard_path = dashboard.generate_dashboard(date_str)
        
        assert Path(dashboard_path).exists()
        
        # Verify dashboard contains our test data
        with open(dashboard_path) as f:
            html_content = f.read()
        
        assert "Integration Test Article" in html_content
        assert "Integration Test Newsletter" in html_content

if __name__ == "__main__":
    pytest.main([__file__])