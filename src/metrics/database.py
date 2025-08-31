"""
SQLite database for storing newsletter pipeline metrics.
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

try:
    from ..config import Config
    from ..logger import get_logger
except ImportError:
    # Fallback for standalone execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from config import Config
    from logger import get_logger

logger = get_logger(__name__)

@dataclass
class PipelineRun:
    """Represents a single pipeline execution."""
    run_id: str
    run_date: date
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    total_articles_collected: int = 0
    articles_after_processing: int = 0
    clusters_created: int = 0
    stories_selected: int = 0
    ai_tokens_used: int = 0
    ai_cost: float = 0.0
    processing_time_seconds: float = 0.0
    errors: List[str] = None
    newsletter_published: bool = False

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

@dataclass
class CollectionMetrics:
    """Metrics from the collection phase."""
    run_id: str
    source_name: str
    source_category: str
    source_tier: str
    articles_collected: int = 0
    collection_time_seconds: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    collected_at: datetime = None

    def __post_init__(self):
        if self.collected_at is None:
            self.collected_at = datetime.now()

@dataclass
class ProcessingMetrics:
    """Metrics from the processing phase."""
    run_id: str
    total_articles_input: int = 0
    articles_after_deduplication: int = 0
    duplicates_removed: int = 0
    clusters_created: int = 0
    processing_time_seconds: float = 0.0
    deduplication_rate: float = 0.0
    success_rate: float = 0.0
    processed_at: datetime = None

    def __post_init__(self):
        if self.processed_at is None:
            self.processed_at = datetime.now()

@dataclass
class AIMetrics:
    """Metrics from AI analysis."""
    run_id: str
    model_used: str = ""
    total_tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    stories_analyzed: int = 0
    average_confidence: float = 0.0
    average_impact_score: float = 0.0
    analysis_time_seconds: float = 0.0
    mock_mode: bool = False
    analyzed_at: datetime = None

    def __post_init__(self):
        if self.analyzed_at is None:
            self.analyzed_at = datetime.now()

@dataclass
class PublishingMetrics:
    """Metrics from publishing phase."""
    run_id: str
    newsletter_date: date
    github_pages_url: Optional[str] = None
    substack_exports: Optional[List[str]] = None
    email_notifications_sent: int = 0
    publishing_time_seconds: float = 0.0
    success: bool = True
    published_at: datetime = None

    def __post_init__(self):
        if self.substack_exports is None:
            self.substack_exports = []
        if self.published_at is None:
            self.published_at = datetime.now()

class MetricsDatabase:
    """SQLite database for storing and retrieving metrics."""

    def __init__(self, db_path: str = "data/metrics.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self._initialize_database()

    def _initialize_database(self):
        """Create database tables if they don't exist."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Create tables
        self._create_pipeline_runs_table()
        self._create_collection_metrics_table()
        self._create_processing_metrics_table()
        self._create_ai_metrics_table()
        self._create_publishing_metrics_table()

        logger.info(f"Metrics database initialized at {self.db_path}")

    def _create_pipeline_runs_table(self):
        """Create pipeline_runs table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                run_date DATE NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                status TEXT NOT NULL DEFAULT 'running',
                total_articles_collected INTEGER DEFAULT 0,
                articles_after_processing INTEGER DEFAULT 0,
                clusters_created INTEGER DEFAULT 0,
                stories_selected INTEGER DEFAULT 0,
                ai_tokens_used INTEGER DEFAULT 0,
                ai_cost REAL DEFAULT 0.0,
                processing_time_seconds REAL DEFAULT 0.0,
                errors TEXT,  -- JSON array
                newsletter_published BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_collection_metrics_table(self):
        """Create collection_metrics table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_category TEXT NOT NULL,
                source_tier TEXT NOT NULL,
                articles_collected INTEGER DEFAULT 0,
                collection_time_seconds REAL DEFAULT 0.0,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                collected_at DATETIME NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
            )
        """)

    def _create_processing_metrics_table(self):
        """Create processing_metrics table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS processing_metrics (
                run_id TEXT PRIMARY KEY,
                total_articles_input INTEGER DEFAULT 0,
                articles_after_deduplication INTEGER DEFAULT 0,
                duplicates_removed INTEGER DEFAULT 0,
                clusters_created INTEGER DEFAULT 0,
                processing_time_seconds REAL DEFAULT 0.0,
                deduplication_rate REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 0.0,
                processed_at DATETIME NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
            )
        """)

    def _create_ai_metrics_table(self):
        """Create ai_metrics table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_metrics (
                run_id TEXT PRIMARY KEY,
                model_used TEXT,
                total_tokens_used INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                stories_analyzed INTEGER DEFAULT 0,
                average_confidence REAL DEFAULT 0.0,
                average_impact_score REAL DEFAULT 0.0,
                analysis_time_seconds REAL DEFAULT 0.0,
                mock_mode BOOLEAN DEFAULT FALSE,
                analyzed_at DATETIME NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
            )
        """)

    def _create_publishing_metrics_table(self):
        """Create publishing_metrics table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS publishing_metrics (
                run_id TEXT PRIMARY KEY,
                newsletter_date DATE NOT NULL,
                github_pages_url TEXT,
                substack_exports TEXT,  -- JSON array
                email_notifications_sent INTEGER DEFAULT 0,
                publishing_time_seconds REAL DEFAULT 0.0,
                success BOOLEAN DEFAULT TRUE,
                published_at DATETIME NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
            )
        """)

        self.conn.commit()

    # Pipeline Runs CRUD
    def create_pipeline_run(self, run: PipelineRun) -> bool:
        """Create a new pipeline run record."""
        try:
            data = asdict(run)
            data['errors'] = json.dumps(data['errors'])
            if data['end_time']:
                data['end_time'] = data['end_time'].isoformat()

            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())

            self.conn.execute(f"""
                INSERT INTO pipeline_runs ({columns})
                VALUES ({placeholders})
            """, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to create pipeline run: {e}")
            return False

    def update_pipeline_run(self, run: PipelineRun) -> bool:
        """Update an existing pipeline run."""
        try:
            data = asdict(run)
            data['errors'] = json.dumps(data['errors'])
            if data['end_time']:
                data['end_time'] = data['end_time'].isoformat()

            # Remove run_id from update data
            update_data = {k: v for k, v in data.items() if k != 'run_id'}
            set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [run.run_id]

            self.conn.execute(f"""
                UPDATE pipeline_runs
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE run_id = ?
            """, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update pipeline run: {e}")
            return False

    def get_pipeline_run(self, run_id: str) -> Optional[PipelineRun]:
        """Get a pipeline run by ID."""
        try:
            cursor = self.conn.execute("""
                SELECT * FROM pipeline_runs WHERE run_id = ?
            """, (run_id,))

            row = cursor.fetchone()
            if row:
                return self._row_to_pipeline_run(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get pipeline run: {e}")
            return None

    def _row_to_pipeline_run(self, row) -> PipelineRun:
        """Convert database row to PipelineRun object."""
        columns = [desc[0] for desc in self.conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()]
        data = dict(zip(columns, row))

        # Parse JSON fields
        data['errors'] = json.loads(data['errors'] or '[]')

        # Parse datetime fields
        if data['end_time']:
            data['end_time'] = datetime.fromisoformat(data['end_time'])

        return PipelineRun(**data)

    # Collection Metrics CRUD
    def save_collection_metrics(self, metrics: CollectionMetrics) -> bool:
        """Save collection metrics."""
        try:
            data = asdict(metrics)
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())

            self.conn.execute(f"""
                INSERT INTO collection_metrics ({columns})
                VALUES ({placeholders})
            """, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save collection metrics: {e}")
            return False

    # Processing Metrics CRUD
    def save_processing_metrics(self, metrics: ProcessingMetrics) -> bool:
        """Save processing metrics."""
        try:
            data = asdict(metrics)
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())

            self.conn.execute(f"""
                INSERT INTO processing_metrics ({columns})
                VALUES ({placeholders})
            """, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save processing metrics: {e}")
            return False

    # AI Metrics CRUD
    def save_ai_metrics(self, metrics: AIMetrics) -> bool:
        """Save AI metrics."""
        try:
            data = asdict(metrics)
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())

            self.conn.execute(f"""
                INSERT INTO ai_metrics ({columns})
                VALUES ({placeholders})
            """, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save AI metrics: {e}")
            return False

    # Publishing Metrics CRUD
    def save_publishing_metrics(self, metrics: PublishingMetrics) -> bool:
        """Save publishing metrics."""
        try:
            data = asdict(metrics)
            data['substack_exports'] = json.dumps(data['substack_exports'])
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())

            self.conn.execute(f"""
                INSERT INTO publishing_metrics ({columns})
                VALUES ({placeholders})
            """, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save publishing metrics: {e}")
            return False

    # Analytics Queries
    def get_recent_pipeline_runs(self, limit: int = 30) -> List[PipelineRun]:
        """Get recent pipeline runs."""
        try:
            cursor = self.conn.execute("""
                SELECT * FROM pipeline_runs
                ORDER BY run_date DESC, start_time DESC
                LIMIT ?
            """, (limit,))

            runs = []
            for row in cursor.fetchall():
                runs.append(self._row_to_pipeline_run(row))
            return runs
        except Exception as e:
            logger.error(f"Failed to get recent pipeline runs: {e}")
            return []

    def get_daily_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get daily statistics for the last N days."""
        try:
            cursor = self.conn.execute("""
                SELECT
                    run_date,
                    COUNT(*) as runs_count,
                    AVG(total_articles_collected) as avg_articles,
                    AVG(processing_time_seconds) as avg_processing_time,
                    AVG(ai_cost) as avg_ai_cost,
                    SUM(ai_tokens_used) as total_tokens,
                    SUM(ai_cost) as total_cost
                FROM pipeline_runs
                WHERE run_date >= date('now', '-{} days')
                GROUP BY run_date
                ORDER BY run_date DESC
            """.format(days))

            daily_stats = []
            for row in cursor.fetchall():
                daily_stats.append({
                    'date': row[0],
                    'runs_count': row[1],
                    'avg_articles': row[2] or 0,
                    'avg_processing_time': row[3] or 0,
                    'avg_ai_cost': row[4] or 0,
                    'total_tokens': row[5] or 0,
                    'total_cost': row[6] or 0
                })

            return {'daily_stats': daily_stats}
        except Exception as e:
            logger.error(f"Failed to get daily stats: {e}")
            return {'daily_stats': []}

    def get_source_performance(self, days: int = 30) -> Dict[str, Any]:
        """Get source performance metrics."""
        try:
            cursor = self.conn.execute("""
                SELECT
                    source_name,
                    source_category,
                    COUNT(*) as collection_attempts,
                    AVG(articles_collected) as avg_articles,
                    SUM(articles_collected) as total_articles,
                    AVG(collection_time_seconds) as avg_collection_time,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_collections,
                    ROUND(
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                        2
                    ) as success_rate
                FROM collection_metrics
                WHERE collected_at >= datetime('now', '-{} days')
                GROUP BY source_name, source_category
                ORDER BY total_articles DESC
            """.format(days))

            source_stats = []
            for row in cursor.fetchall():
                source_stats.append({
                    'source_name': row[0],
                    'source_category': row[1],
                    'collection_attempts': row[2],
                    'avg_articles': row[3] or 0,
                    'total_articles': row[4] or 0,
                    'avg_collection_time': row[5] or 0,
                    'successful_collections': row[6],
                    'success_rate': row[7] or 0
                })

            return {'source_stats': source_stats}
        except Exception as e:
            logger.error(f"Failed to get source performance: {e}")
            return {'source_stats': []}

    def get_ai_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get AI usage statistics."""
        try:
            cursor = self.conn.execute("""
                SELECT
                    model_used,
                    COUNT(*) as analysis_runs,
                    SUM(total_tokens_used) as total_tokens,
                    AVG(total_tokens_used) as avg_tokens_per_run,
                    SUM(total_cost) as total_cost,
                    AVG(total_cost) as avg_cost_per_run,
                    AVG(average_confidence) as avg_confidence,
                    AVG(average_impact_score) as avg_impact_score,
                    SUM(stories_analyzed) as total_stories
                FROM ai_metrics
                WHERE analyzed_at >= datetime('now', '-{} days')
                GROUP BY model_used
                ORDER BY total_cost DESC
            """.format(days))

            ai_stats = []
            for row in cursor.fetchall():
                ai_stats.append({
                    'model_used': row[0],
                    'analysis_runs': row[1],
                    'total_tokens': row[2] or 0,
                    'avg_tokens_per_run': row[3] or 0,
                    'total_cost': row[4] or 0,
                    'avg_cost_per_run': row[5] or 0,
                    'avg_confidence': row[6] or 0,
                    'avg_impact_score': row[7] or 0,
                    'total_stories': row[8] or 0
                })

            return {'ai_stats': ai_stats}
        except Exception as e:
            logger.error(f"Failed to get AI usage stats: {e}")
            return {'ai_stats': []}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()