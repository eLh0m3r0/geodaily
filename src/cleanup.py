"""
Automatic cleanup system for old files and data.
Handles log files, newsletter archives, metrics database, and output files.
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from .config import Config
    from .logging_system import get_metrics_aware_logger
    logger = get_metrics_aware_logger(__name__)
except ImportError:
    # Fallback for standalone execution or circular import issues
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Add console handler if not already present
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Mock Config class for standalone execution
    class Config:
        CLEANUP_ENABLED = True
        LOG_RETENTION_DAYS = 30
        NEWSLETTER_RETENTION_DAYS = 90
        OUTPUT_RETENTION_DAYS = 7
        METRICS_RETENTION_DAYS = 180
        CLEANUP_DRY_RUN = False

        PROJECT_ROOT = Path(__file__).parent.parent
        LOGS_DIR = PROJECT_ROOT / "logs"
        OUTPUT_DIR = PROJECT_ROOT / "output"
        NEWSLETTERS_DIR = PROJECT_ROOT / "docs" / "newsletters"
        METRICS_DB_PATH = PROJECT_ROOT / "data" / "metrics.db"

@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    files_removed: int = 0
    bytes_freed: int = 0
    database_records_removed: int = 0
    errors: List[str] = None
    dry_run: bool = False

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class CleanupManager:
    """Manages automatic cleanup of old files and data."""

    def __init__(self, dry_run: bool = None):
        """Initialize cleanup manager."""
        self.dry_run = dry_run if dry_run is not None else Config.CLEANUP_DRY_RUN
        self.logger = logger
        self._is_structured_logger = hasattr(self.logger, 'info') and 'structured_data' in str(self.logger.info.__code__.co_varnames)

        if self.dry_run:
            self._log_info("🧹 Cleanup running in DRY RUN mode - no files will be deleted")

    def _log_info(self, message: str, **kwargs):
        """Log info message, handling both structured and standard loggers."""
        if self._is_structured_logger and 'structured_data' not in kwargs:
            # Convert kwargs to structured_data for structured logger
            structured_data = kwargs
            self.logger.info(message, structured_data=structured_data)
        elif self._is_structured_logger:
            self.logger.info(message, **kwargs)
        else:
            # Standard logger - include kwargs in message
            if kwargs:
                extra_info = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                message = f"{message} ({extra_info})"
            self.logger.info(message)

    def _log_error(self, message: str, **kwargs):
        """Log error message, handling both structured and standard loggers."""
        if self._is_structured_logger and 'structured_data' not in kwargs:
            structured_data = kwargs
            self.logger.error(message, structured_data=structured_data)
        elif self._is_structured_logger:
            self.logger.error(message, **kwargs)
        else:
            if kwargs:
                extra_info = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                message = f"{message} ({extra_info})"
            self.logger.error(message)

    def _log_warning(self, message: str, **kwargs):
        """Log warning message, handling both structured and standard loggers."""
        if self._is_structured_logger and 'structured_data' not in kwargs:
            structured_data = kwargs
            self.logger.warning(message, structured_data=structured_data)
        elif self._is_structured_logger:
            self.logger.warning(message, **kwargs)
        else:
            if kwargs:
                extra_info = ", ".join(f"{k}={v}" for k, v in kwargs.items())
                message = f"{message} ({extra_info})"
            self.logger.warning(message)

    def run_full_cleanup(self) -> CleanupResult:
        """Run complete cleanup of all configured areas."""
        self._log_info("🧹 Starting full cleanup process")

        total_result = CleanupResult(dry_run=self.dry_run)

        try:
            # Cleanup log files
            log_result = self.cleanup_log_files()
            total_result.files_removed += log_result.files_removed
            total_result.bytes_freed += log_result.bytes_freed
            total_result.errors.extend(log_result.errors)

            # Cleanup newsletter archives
            newsletter_result = self.cleanup_newsletter_archives()
            total_result.files_removed += newsletter_result.files_removed
            total_result.bytes_freed += newsletter_result.bytes_freed
            total_result.errors.extend(newsletter_result.errors)

            # Cleanup output files
            output_result = self.cleanup_output_files()
            total_result.files_removed += output_result.files_removed
            total_result.bytes_freed += output_result.bytes_freed
            total_result.errors.extend(output_result.errors)

            # Cleanup metrics database
            metrics_result = self.cleanup_metrics_database()
            total_result.database_records_removed += metrics_result.database_records_removed
            total_result.errors.extend(metrics_result.errors)

            # Log summary
            self._log_info("🧹 Cleanup completed",
                           structured_data={
                               'files_removed': total_result.files_removed,
                               'bytes_freed': total_result.bytes_freed,
                               'database_records_removed': total_result.database_records_removed,
                               'errors_count': len(total_result.errors),
                               'dry_run': self.dry_run
                           })

            if total_result.errors:
                self._log_warning("🧹 Cleanup completed with errors",
                                  structured_data={'errors': total_result.errors})

        except Exception as e:
            error_msg = f"Cleanup failed: {e}"
            self._log_error(error_msg, error_details=str(e))
            total_result.errors.append(error_msg)

        return total_result

    def cleanup_log_files(self) -> CleanupResult:
        """Clean up old log files based on retention policy."""
        result = CleanupResult(dry_run=self.dry_run)
        retention_date = datetime.now() - timedelta(days=Config.LOG_RETENTION_DAYS)

        self._log_info("🗂️ Cleaning up log files",
                      retention_days=Config.LOG_RETENTION_DAYS,
                      retention_date=retention_date.isoformat(),
                      logs_dir=str(Config.LOGS_DIR))

        if not Config.LOGS_DIR.exists():
            self._log_info("🗂️ Logs directory does not exist, skipping log cleanup")
            return result

        try:
            for log_file in Config.LOGS_DIR.glob("*.log"):
                if log_file.is_file():
                    # Extract date from filename (format: geodaily_YYYYMMDD.log)
                    try:
                        date_str = log_file.stem.split('_')[-1]
                        file_date = datetime.strptime(date_str, '%Y%m%d').date()
                        retention_cutoff = retention_date.date()

                        if file_date < retention_cutoff:
                            file_size = log_file.stat().st_size
                            result.bytes_freed += file_size
                            result.files_removed += 1

                            if self.dry_run:
                                self._log_info("🗂️ Would remove old log file",
                                                file=str(log_file),
                                                file_date=file_date.isoformat(),
                                                file_size=file_size)
                            else:
                                log_file.unlink()
                                self._log_info("🗂️ Removed old log file",
                                               file=str(log_file),
                                               file_date=file_date.isoformat(),
                                               file_size=file_size)
                    except (ValueError, IndexError) as e:
                        self._log_warning("🗂️ Could not parse date from log filename",
                                          file=str(log_file),
                                          error=str(e))

        except Exception as e:
            error_msg = f"Log cleanup failed: {e}"
            self._log_error(error_msg, error_details=str(e))
            result.errors.append(error_msg)

        return result

    def cleanup_newsletter_archives(self) -> CleanupResult:
        """Clean up old newsletter archive files."""
        result = CleanupResult(dry_run=self.dry_run)
        retention_date = datetime.now() - timedelta(days=Config.NEWSLETTER_RETENTION_DAYS)

        self._log_info("📰 Cleaning up newsletter archives",
                       retention_days=Config.NEWSLETTER_RETENTION_DAYS,
                       retention_date=retention_date.isoformat(),
                       newsletters_dir=str(Config.NEWSLETTERS_DIR))

        if not Config.NEWSLETTERS_DIR.exists():
            self._log_info("📰 Newsletters directory does not exist, skipping newsletter cleanup")
            return result

        try:
            for newsletter_file in Config.NEWSLETTERS_DIR.glob("*.html"):
                if newsletter_file.is_file():
                    # Extract date from filename (format: newsletter-YYYY-MM-DD.html)
                    try:
                        date_str = newsletter_file.stem.split('-', 1)[-1]
                        file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        retention_cutoff = retention_date.date()

                        if file_date < retention_cutoff:
                            file_size = newsletter_file.stat().st_size
                            result.bytes_freed += file_size
                            result.files_removed += 1

                            if self.dry_run:
                                self._log_info("📰 Would remove old newsletter",
                                               file=str(newsletter_file),
                                               file_date=file_date.isoformat(),
                                               file_size=file_size)
                            else:
                                newsletter_file.unlink()
                                self._log_info("📰 Removed old newsletter",
                                               file=str(newsletter_file),
                                               file_date=file_date.isoformat(),
                                               file_size=file_size)
                    except (ValueError, IndexError) as e:
                        self._log_warning("📰 Could not parse date from newsletter filename",
                                          file=str(newsletter_file),
                                          error=str(e))

        except Exception as e:
            error_msg = f"Newsletter cleanup failed: {e}"
            self._log_error(error_msg, error_details=str(e))
            result.errors.append(error_msg)

        return result

    def cleanup_output_files(self) -> CleanupResult:
        """Clean up old output files."""
        result = CleanupResult(dry_run=self.dry_run)
        retention_date = datetime.now() - timedelta(days=Config.OUTPUT_RETENTION_DAYS)

        self._log_info("📁 Cleaning up output files",
                       retention_days=Config.OUTPUT_RETENTION_DAYS,
                       retention_date=retention_date.isoformat(),
                       output_dir=str(Config.OUTPUT_DIR))

        if not Config.OUTPUT_DIR.exists():
            self._log_info("📁 Output directory does not exist, skipping output cleanup")
            return result

        try:
            for output_file in Config.OUTPUT_DIR.glob("*"):
                if output_file.is_file():
                    # Extract timestamp from filename (format: newsletter_YYYYMMDD_HHMMSS.html)
                    try:
                        # Look for timestamp pattern in filename
                        filename = output_file.stem
                        if '_20' in filename:  # Look for date pattern
                            date_part = filename.split('_20', 1)[-1]
                            if len(date_part) >= 8:  # YYYYMMDD
                                date_str = date_part[:8]
                                file_date = datetime.strptime(date_str, '%Y%m%d').date()
                                retention_cutoff = retention_date.date()

                                if file_date < retention_cutoff:
                                    file_size = output_file.stat().st_size
                                    result.bytes_freed += file_size
                                    result.files_removed += 1

                                    if self.dry_run:
                                        self._log_info("📁 Would remove old output file",
                                                       file=str(output_file),
                                                       file_date=file_date.isoformat(),
                                                       file_size=file_size)
                                    else:
                                        output_file.unlink()
                                        self._log_info("📁 Removed old output file",
                                                       file=str(output_file),
                                                       file_date=file_date.isoformat(),
                                                       file_size=file_size)
                    except (ValueError, IndexError) as e:
                        # For files without clear timestamps, use file modification time
                        file_mtime = datetime.fromtimestamp(output_file.stat().st_mtime)
                        if file_mtime < retention_date:
                            file_size = output_file.stat().st_size
                            result.bytes_freed += file_size
                            result.files_removed += 1

                            if self.dry_run:
                                self._log_info("📁 Would remove old output file (by mtime)",
                                               file=str(output_file),
                                               file_mtime=file_mtime.isoformat(),
                                               file_size=file_size)
                            else:
                                output_file.unlink()
                                self._log_info("📁 Removed old output file (by mtime)",
                                               file=str(output_file),
                                               file_mtime=file_mtime.isoformat(),
                                               file_size=file_size)

        except Exception as e:
            error_msg = f"Output cleanup failed: {e}"
            self._log_error(error_msg, error_details=str(e))
            result.errors.append(error_msg)

        return result

    def cleanup_metrics_database(self) -> CleanupResult:
        """Clean up old metrics data from database."""
        result = CleanupResult(dry_run=self.dry_run)
        retention_date = datetime.now() - timedelta(days=Config.METRICS_RETENTION_DAYS)

        self._log_info("🗃️ Cleaning up metrics database",
                       retention_days=Config.METRICS_RETENTION_DAYS,
                       retention_date=retention_date.isoformat(),
                       db_path=str(Config.METRICS_DB_PATH))

        if not Config.METRICS_DB_PATH.exists():
            self._log_info("🗃️ Metrics database does not exist, skipping database cleanup")
            return result

        try:
            conn = sqlite3.connect(str(Config.METRICS_DB_PATH))
            cursor = conn.cursor()

            # Get count of records to be deleted before deletion
            retention_date_str = retention_date.date().isoformat()

            # Count pipeline runs to delete
            cursor.execute("""
                SELECT COUNT(*) FROM pipeline_runs
                WHERE run_date < ?
            """, (retention_date_str,))
            pipeline_runs_count = cursor.fetchone()[0]

            # Count collection metrics to delete
            cursor.execute("""
                SELECT COUNT(*) FROM collection_metrics
                WHERE date(collected_at) < ?
            """, (retention_date_str,))
            collection_metrics_count = cursor.fetchone()[0]

            # Count processing metrics to delete
            cursor.execute("""
                SELECT COUNT(*) FROM processing_metrics
                WHERE date(processed_at) < ?
            """, (retention_date_str,))
            processing_metrics_count = cursor.fetchone()[0]

            # Count AI metrics to delete
            cursor.execute("""
                SELECT COUNT(*) FROM ai_metrics
                WHERE date(analyzed_at) < ?
            """, (retention_date_str,))
            ai_metrics_count = cursor.fetchone()[0]

            # Count publishing metrics to delete
            cursor.execute("""
                SELECT COUNT(*) FROM publishing_metrics
                WHERE date(published_at) < ?
            """, (retention_date_str,))
            publishing_metrics_count = cursor.fetchone()[0]

            total_records = (pipeline_runs_count + collection_metrics_count +
                           processing_metrics_count + ai_metrics_count + publishing_metrics_count)

            result.database_records_removed = total_records

            if self.dry_run:
                self._log_info("🗃️ Would remove old metrics records",
                               pipeline_runs=pipeline_runs_count,
                               collection_metrics=collection_metrics_count,
                               processing_metrics=processing_metrics_count,
                               ai_metrics=ai_metrics_count,
                               publishing_metrics=publishing_metrics_count,
                               total_records=total_records)
            else:
                # Delete old records (foreign key constraints will handle cascading)
                cursor.execute("DELETE FROM pipeline_runs WHERE run_date < ?", (retention_date_str,))
                cursor.execute("DELETE FROM collection_metrics WHERE date(collected_at) < ?", (retention_date_str,))
                cursor.execute("DELETE FROM processing_metrics WHERE date(processed_at) < ?", (retention_date_str,))
                cursor.execute("DELETE FROM ai_metrics WHERE date(analyzed_at) < ?", (retention_date_str,))
                cursor.execute("DELETE FROM publishing_metrics WHERE date(published_at) < ?", (retention_date_str,))

                conn.commit()

                self._log_info("🗃️ Removed old metrics records",
                               pipeline_runs=pipeline_runs_count,
                               collection_metrics=collection_metrics_count,
                               processing_metrics=processing_metrics_count,
                               ai_metrics=ai_metrics_count,
                               publishing_metrics=publishing_metrics_count,
                               total_records=total_records)

        except Exception as e:
            error_msg = f"Metrics database cleanup failed: {e}"
            self._log_error(error_msg, error_details=str(e))
            result.errors.append(error_msg)
        finally:
            if 'conn' in locals():
                conn.close()

        return result

    def get_cleanup_status(self) -> Dict[str, Any]:
        """Get current status of files and data that would be cleaned up."""
        status = {
            'log_files': {'total': 0, 'old': 0, 'size_old': 0},
            'newsletter_files': {'total': 0, 'old': 0, 'size_old': 0},
            'output_files': {'total': 0, 'old': 0, 'size_old': 0},
            'metrics_records': {'total': 0, 'old': 0},
            'retention_policies': {
                'logs_days': Config.LOG_RETENTION_DAYS,
                'newsletters_days': Config.NEWSLETTER_RETENTION_DAYS,
                'output_days': Config.OUTPUT_RETENTION_DAYS,
                'metrics_days': Config.METRICS_RETENTION_DAYS
            }
        }

        retention_date = datetime.now() - timedelta(days=max(Config.LOG_RETENTION_DAYS,
                                                           Config.NEWSLETTER_RETENTION_DAYS,
                                                           Config.OUTPUT_RETENTION_DAYS,
                                                           Config.METRICS_RETENTION_DAYS))

        # Check log files
        if Config.LOGS_DIR.exists():
            for log_file in Config.LOGS_DIR.glob("*.log"):
                if log_file.is_file():
                    status['log_files']['total'] += 1
                    try:
                        date_str = log_file.stem.split('_')[-1]
                        file_date = datetime.strptime(date_str, '%Y%m%d').date()
                        if file_date < retention_date.date():
                            status['log_files']['old'] += 1
                            status['log_files']['size_old'] += log_file.stat().st_size
                    except:
                        pass

        # Check newsletter files
        if Config.NEWSLETTERS_DIR.exists():
            for newsletter_file in Config.NEWSLETTERS_DIR.glob("*.html"):
                if newsletter_file.is_file():
                    status['newsletter_files']['total'] += 1
                    try:
                        date_str = newsletter_file.stem.split('-', 1)[-1]
                        file_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        if file_date < retention_date.date():
                            status['newsletter_files']['old'] += 1
                            status['newsletter_files']['size_old'] += newsletter_file.stat().st_size
                    except:
                        pass

        # Check output files
        if Config.OUTPUT_DIR.exists():
            for output_file in Config.OUTPUT_DIR.glob("*"):
                if output_file.is_file():
                    status['output_files']['total'] += 1
                    file_mtime = datetime.fromtimestamp(output_file.stat().st_mtime)
                    if file_mtime < retention_date:
                        status['output_files']['old'] += 1
                        status['output_files']['size_old'] += output_file.stat().st_size

        # Check metrics database
        if Config.METRICS_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(Config.METRICS_DB_PATH))
                cursor = conn.cursor()

                # Count total records
                for table in ['pipeline_runs', 'collection_metrics', 'processing_metrics', 'ai_metrics', 'publishing_metrics']:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    status['metrics_records']['total'] += cursor.fetchone()[0]

                # Count old records
                retention_date_str = retention_date.date().isoformat()
                cursor.execute("SELECT COUNT(*) FROM pipeline_runs WHERE run_date < ?", (retention_date_str,))
                status['metrics_records']['old'] += cursor.fetchone()[0]

                conn.close()
            except Exception as e:
                self._log_warning(f"Could not check metrics database status: {e}")

        return status


def run_cleanup(dry_run: bool = None) -> CleanupResult:
    """Convenience function to run cleanup."""
    manager = CleanupManager(dry_run=dry_run)
    return manager.run_full_cleanup()


def get_cleanup_status() -> Dict[str, Any]:
    """Convenience function to get cleanup status."""
    manager = CleanupManager()
    return manager.get_cleanup_status()


if __name__ == "__main__":
    # Allow running cleanup from command line
    import argparse

    parser = argparse.ArgumentParser(description="Geopolitical Daily Cleanup System")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode")
    parser.add_argument("--status", action="store_true", help="Show cleanup status only")

    args = parser.parse_args()

    if args.status:
        status = get_cleanup_status()
        print("=== Cleanup Status ===")
        print(f"Log files: {status['log_files']['old']}/{status['log_files']['total']} old")
        print(f"Newsletter files: {status['newsletter_files']['old']}/{status['newsletter_files']['total']} old")
        print(f"Output files: {status['output_files']['old']}/{status['output_files']['total']} old")
        print(f"Metrics records: {status['metrics_records']['old']}/{status['metrics_records']['total']} old")
    else:
        result = run_cleanup(dry_run=args.dry_run)
        print(f"Cleanup completed: {result.files_removed} files removed, {result.database_records_removed} records removed")
        if result.errors:
            print(f"Errors: {len(result.errors)}")
            for error in result.errors:
                print(f"  - {error}")