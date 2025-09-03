#!/usr/bin/env python3
"""
Archive Cleanup Utility
Manages cleanup of old archive data with intelligent retention policies.

Usage:
    python cleanup_archives.py                    # Run default cleanup (30 days)
    python cleanup_archives.py --days 14         # Keep 14 days
    python cleanup_archives.py --dry-run         # Show what would be deleted
    python cleanup_archives.py --force           # Skip confirmation prompts
    python cleanup_archives.py --deep-clean      # Aggressive cleanup
"""

import argparse
import sys
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.logger import get_logger

logger = get_logger("archive_cleanup")


class ArchiveCleanup:
    """Intelligent archive cleanup with multiple retention policies."""
    
    def __init__(self, archive_path: str = None, dry_run: bool = False):
        self.archive_path = Path(archive_path or getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive'))
        self.dry_run = dry_run
        self.stats = {
            'directories_removed': 0,
            'files_removed': 0,
            'space_freed_bytes': 0,
            'total_runs_processed': 0,
            'errors': []
        }
    
    def run_cleanup(self, retention_days: int = 30, deep_clean: bool = False, 
                   force: bool = False) -> Dict:
        """Run comprehensive archive cleanup."""
        
        logger.info("🧹 Starting Archive Cleanup")
        logger.info(f"Archive path: {self.archive_path}")
        logger.info(f"Retention policy: {retention_days} days")
        logger.info(f"Deep clean: {deep_clean}")
        logger.info(f"Dry run: {self.dry_run}")
        
        if not self.archive_path.exists():
            logger.warning(f"Archive path does not exist: {self.archive_path}")
            return self.stats
        
        # Calculate cutoff dates
        primary_cutoff = datetime.now() - timedelta(days=retention_days)
        
        if deep_clean:
            # More aggressive cleanup for deep clean
            secondary_cutoff = datetime.now() - timedelta(days=retention_days // 2)
        else:
            secondary_cutoff = primary_cutoff
        
        logger.info(f"Primary cutoff date: {primary_cutoff.strftime('%Y-%m-%d')}")
        
        # Get all date directories
        date_dirs = self._find_date_directories()
        
        if not date_dirs:
            logger.info("No date directories found")
            return self.stats
        
        logger.info(f"Found {len(date_dirs)} date directories")
        
        # Analyze directories
        directories_to_remove = []
        directories_to_clean = []  # Partial cleanup within directories
        
        for date_dir in date_dirs:
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                
                if dir_date < primary_cutoff:
                    # Remove entire directory
                    directories_to_remove.append((date_dir, 'old'))
                elif deep_clean and dir_date < secondary_cutoff:
                    # Partial cleanup - keep only successful runs
                    directories_to_clean.append(date_dir)
                    
            except ValueError:
                logger.warning(f"Invalid date directory name: {date_dir.name}")
                continue
        
        # Show cleanup plan
        self._show_cleanup_plan(directories_to_remove, directories_to_clean)
        
        # Confirm if not force mode
        if not force and not self.dry_run:
            if not self._confirm_cleanup():
                logger.info("Cleanup cancelled by user")
                return self.stats
        
        # Execute cleanup
        self._cleanup_directories(directories_to_remove, full_removal=True)
        
        if deep_clean:
            self._cleanup_directories(directories_to_clean, full_removal=False)
        
        # Additional cleanup tasks
        self._cleanup_empty_directories()
        self._cleanup_temporary_files()
        
        # Generate cleanup report
        self._generate_cleanup_report()
        
        logger.info("🎉 Archive cleanup completed")
        return self.stats
    
    def _find_date_directories(self) -> List[Path]:
        """Find all valid date directories in archive."""
        date_dirs = []
        
        for item in self.archive_path.iterdir():
            if item.is_dir() and self._is_valid_date_dir(item.name):
                date_dirs.append(item)
        
        return sorted(date_dirs)
    
    def _is_valid_date_dir(self, dirname: str) -> bool:
        """Check if directory name is a valid date (YYYY-MM-DD)."""
        try:
            datetime.strptime(dirname, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def _show_cleanup_plan(self, to_remove: List[Tuple[Path, str]], 
                          to_clean: List[Path]):
        """Show what will be cleaned up."""
        
        total_size = 0
        total_files = 0
        total_dirs = 0
        
        logger.info("📋 Cleanup Plan:")
        
        if to_remove:
            logger.info(f"🗑️  Directories to remove completely: {len(to_remove)}")
            
            for dir_path, reason in to_remove:
                dir_size = self._get_directory_size(dir_path)
                file_count = self._count_files_in_directory(dir_path)
                
                total_size += dir_size
                total_files += file_count
                total_dirs += 1
                
                logger.info(f"   • {dir_path.name} ({self._format_bytes(dir_size)}, {file_count} files) - {reason}")
        
        if to_clean:
            logger.info(f"🧽 Directories to clean partially: {len(to_clean)}")
            
            for dir_path in to_clean:
                failed_runs = self._find_failed_runs(dir_path)
                failed_size = sum(self._get_directory_size(run_dir) for run_dir in failed_runs)
                failed_files = sum(self._count_files_in_directory(run_dir) for run_dir in failed_runs)
                
                total_size += failed_size
                total_files += failed_files
                
                logger.info(f"   • {dir_path.name} ({len(failed_runs)} failed runs, {self._format_bytes(failed_size)})")
        
        logger.info(f"💾 Total space to free: {self._format_bytes(total_size)}")
        logger.info(f"📄 Total files to remove: {total_files:,}")
        logger.info(f"📁 Total directories affected: {total_dirs}")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN: No files will actually be removed")
    
    def _confirm_cleanup(self) -> bool:
        """Ask user for confirmation."""
        try:
            response = input("\n❓ Proceed with cleanup? (y/N): ").strip().lower()
            return response in ('y', 'yes')
        except KeyboardInterrupt:
            print("\n⚠️ Cleanup cancelled")
            return False
    
    def _cleanup_directories(self, directories: List, full_removal: bool = True):
        """Execute directory cleanup."""
        
        for item in directories:
            if full_removal:
                dir_path, reason = item
                self._remove_directory(dir_path, reason)
            else:
                # Partial cleanup
                dir_path = item
                self._cleanup_failed_runs(dir_path)
    
    def _remove_directory(self, dir_path: Path, reason: str):
        """Remove a directory completely."""
        try:
            if self.dry_run:
                logger.info(f"DRY RUN: Would remove {dir_path.name} ({reason})")
                return
            
            # Calculate stats before removal
            size_before = self._get_directory_size(dir_path)
            files_before = self._count_files_in_directory(dir_path)
            
            shutil.rmtree(dir_path)
            
            # Update stats
            self.stats['directories_removed'] += 1
            self.stats['files_removed'] += files_before
            self.stats['space_freed_bytes'] += size_before
            
            logger.info(f"✅ Removed {dir_path.name} ({self._format_bytes(size_before)}, {files_before} files)")
            
        except Exception as e:
            error_msg = f"Failed to remove {dir_path}: {e}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
    
    def _cleanup_failed_runs(self, dir_path: Path):
        """Clean up failed runs within a directory."""
        failed_runs = self._find_failed_runs(dir_path)
        
        for run_dir in failed_runs:
            try:
                if self.dry_run:
                    logger.info(f"DRY RUN: Would remove failed run {run_dir.name}")
                    continue
                
                # Calculate stats before removal
                size_before = self._get_directory_size(run_dir)
                files_before = self._count_files_in_directory(run_dir)
                
                shutil.rmtree(run_dir)
                
                # Update stats
                self.stats['files_removed'] += files_before
                self.stats['space_freed_bytes'] += size_before
                
                logger.info(f"✅ Removed failed run {run_dir.name}")
                
            except Exception as e:
                error_msg = f"Failed to remove {run_dir}: {e}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
    
    def _find_failed_runs(self, date_dir: Path) -> List[Path]:
        """Find failed runs in a date directory."""
        failed_runs = []
        
        for run_dir in date_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue
            
            # Check if run has final newsletter (indicates success)
            newsletter_file = run_dir / "final_newsletter.json"
            summary_file = run_dir / "run_summary.json"
            
            # Consider run failed if it doesn't have key success indicators
            if not newsletter_file.exists() or not summary_file.exists():
                failed_runs.append(run_dir)
                continue
            
            # Check if run generated stories
            try:
                with open(newsletter_file) as f:
                    data = json.load(f)
                    if data.get('stories_count', 0) == 0:
                        failed_runs.append(run_dir)
            except:
                failed_runs.append(run_dir)
        
        return failed_runs
    
    def _cleanup_empty_directories(self):
        """Remove empty directories."""
        for date_dir in self.archive_path.iterdir():
            if date_dir.is_dir() and not list(date_dir.iterdir()):
                try:
                    if self.dry_run:
                        logger.info(f"DRY RUN: Would remove empty directory {date_dir.name}")
                    else:
                        date_dir.rmdir()
                        logger.info(f"✅ Removed empty directory {date_dir.name}")
                        self.stats['directories_removed'] += 1
                except Exception as e:
                    logger.warning(f"Could not remove empty directory {date_dir}: {e}")
    
    def _cleanup_temporary_files(self):
        """Remove temporary files."""
        temp_patterns = ['*.tmp', '*.log.*', '*.backup', '.DS_Store']
        temp_files_removed = 0
        
        for pattern in temp_patterns:
            for temp_file in self.archive_path.rglob(pattern):
                try:
                    if self.dry_run:
                        logger.debug(f"DRY RUN: Would remove temp file {temp_file}")
                    else:
                        size = temp_file.stat().st_size
                        temp_file.unlink()
                        self.stats['files_removed'] += 1
                        self.stats['space_freed_bytes'] += size
                        temp_files_removed += 1
                except Exception as e:
                    logger.debug(f"Could not remove temp file {temp_file}: {e}")
        
        if temp_files_removed > 0:
            logger.info(f"✅ Removed {temp_files_removed} temporary files")
    
    def _get_directory_size(self, dir_path: Path) -> int:
        """Calculate total size of directory."""
        total_size = 0
        try:
            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.debug(f"Error calculating size for {dir_path}: {e}")
        return total_size
    
    def _count_files_in_directory(self, dir_path: Path) -> int:
        """Count files in directory."""
        try:
            return len([f for f in dir_path.rglob('*') if f.is_file()])
        except Exception as e:
            logger.debug(f"Error counting files in {dir_path}: {e}")
            return 0
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"
    
    def _generate_cleanup_report(self):
        """Generate cleanup report."""
        report_path = self.archive_path / "cleanup_report.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'statistics': self.stats,
            'summary': {
                'directories_removed': self.stats['directories_removed'],
                'files_removed': self.stats['files_removed'],
                'space_freed_mb': round(self.stats['space_freed_bytes'] / 1024 / 1024, 2),
                'errors_count': len(self.stats['errors'])
            }
        }
        
        try:
            if not self.dry_run:
                with open(report_path, 'w') as f:
                    json.dump(report, f, indent=2)
                
                logger.info(f"📊 Cleanup report saved: {report_path}")
        except Exception as e:
            logger.warning(f"Could not save cleanup report: {e}")


def main():
    parser = argparse.ArgumentParser(description="Clean up GeoPolitical Daily archive data")
    parser.add_argument("--days", type=int, default=30, 
                       help="Number of days to retain (default: 30)")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be deleted without actually deleting")
    parser.add_argument("--force", action="store_true", 
                       help="Skip confirmation prompts")
    parser.add_argument("--deep-clean", action="store_true", 
                       help="Aggressive cleanup including failed runs")
    parser.add_argument("--archive-path", type=str, 
                       help="Custom path to AI archive")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize cleanup
    archive_path = args.archive_path or getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive')
    cleanup = ArchiveCleanup(archive_path, dry_run=args.dry_run)
    
    try:
        # Run cleanup
        stats = cleanup.run_cleanup(
            retention_days=args.days,
            deep_clean=args.deep_clean,
            force=args.force
        )
        
        # Summary
        logger.info("📊 Cleanup Summary:")
        logger.info(f"   Directories removed: {stats['directories_removed']}")
        logger.info(f"   Files removed: {stats['files_removed']:,}")
        logger.info(f"   Space freed: {cleanup._format_bytes(stats['space_freed_bytes'])}")
        
        if stats['errors']:
            logger.warning(f"   Errors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                logger.warning(f"     • {error}")
        
        return 0 if not stats['errors'] else 1
        
    except KeyboardInterrupt:
        logger.info("⚠️ Cleanup interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())