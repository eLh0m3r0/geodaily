"""
Newsletter Archive Manager for maintaining a rolling archive of the last N newsletters.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import shutil

from ..logger import get_logger

logger = get_logger(__name__)

class NewsletterArchiveManager:
    """Manages a rolling archive of newsletters, keeping only the last N editions."""
    
    def __init__(self, output_dir: str = "docs", max_newsletters: int = 10):
        """
        Initialize archive manager.
        
        Args:
            output_dir: Base output directory (default: "docs")
            max_newsletters: Maximum number of newsletters to keep (default: 10)
        """
        self.output_dir = Path(output_dir)
        self.newsletters_dir = self.output_dir / "newsletters"
        self.max_newsletters = max_newsletters
        
        # Ensure directories exist
        self.output_dir.mkdir(exist_ok=True)
        self.newsletters_dir.mkdir(exist_ok=True)
        
        logger.info(f"Archive manager initialized: max_newsletters={max_newsletters}, dir={self.output_dir}")
    
    def add_newsletter(self, newsletter_content: str, date: datetime) -> str:
        """
        Add a new newsletter to the archive, managing rotation.
        
        Args:
            newsletter_content: HTML content of the newsletter
            date: Date of the newsletter
            
        Returns:
            Path to the saved newsletter file
        """
        date_str = date.strftime('%Y-%m-%d')
        filename = f"newsletter-{date_str}.html"
        newsletter_path = self.newsletters_dir / filename
        
        logger.info(f"Adding newsletter to archive: {filename}")
        
        # Save new newsletter
        with open(newsletter_path, 'w', encoding='utf-8') as f:
            f.write(newsletter_content)
        
        # Manage archive rotation
        self._rotate_archive()
        
        # Update archive metadata
        self._update_archive_metadata()
        
        logger.info(f"Newsletter added to archive: {newsletter_path}")
        return str(newsletter_path)
    
    def _rotate_archive(self) -> None:
        """Remove old newsletters to maintain the maximum count."""
        
        # Get all newsletter files sorted by date (newest first)
        newsletter_files = self._get_sorted_newsletters()
        
        if len(newsletter_files) <= self.max_newsletters:
            logger.debug(f"Archive rotation not needed: {len(newsletter_files)} <= {self.max_newsletters}")
            return
        
        # Remove excess newsletters (oldest first)
        excess_count = len(newsletter_files) - self.max_newsletters
        files_to_remove = newsletter_files[-excess_count:]  # Take from the end (oldest)
        
        logger.info(f"Archive rotation: removing {len(files_to_remove)} old newsletters")
        
        for file_path in files_to_remove:
            try:
                file_path.unlink()
                logger.debug(f"Removed old newsletter: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to remove {file_path}: {e}")
    
    def _get_sorted_newsletters(self) -> List[Path]:
        """Get list of newsletter files sorted by date (newest first)."""
        
        newsletter_files = []
        
        for file_path in self.newsletters_dir.glob("newsletter-*.html"):
            try:
                # Extract date from filename
                date_str = file_path.stem.replace('newsletter-', '')
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                newsletter_files.append((date_obj, file_path))
            except ValueError as e:
                logger.warning(f"Skipping file with invalid date format: {file_path.name}: {e}")
                continue
        
        # Sort by date (newest first)
        newsletter_files.sort(key=lambda x: x[0], reverse=True)
        
        return [file_path for _, file_path in newsletter_files]
    
    def get_newsletter_list(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get list of newsletters with metadata.
        
        Args:
            limit: Maximum number of newsletters to return
            
        Returns:
            List of newsletter metadata dictionaries
        """
        newsletter_files = self._get_sorted_newsletters()
        
        if limit:
            newsletter_files = newsletter_files[:limit]
        
        newsletters = []
        for file_path in newsletter_files:
            try:
                date_str = file_path.stem.replace('newsletter-', '')
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                
                newsletters.append({
                    'filename': file_path.name,
                    'date': date_obj,
                    'date_str': date_str,
                    'formatted_date': date_obj.strftime('%B %d, %Y'),
                    'path': str(file_path),
                    'relative_path': f"newsletters/{file_path.name}",
                    'file_size': file_path.stat().st_size if file_path.exists() else 0
                })
            except ValueError as e:
                logger.warning(f"Skipping file with invalid date: {file_path.name}: {e}")
                continue
        
        return newsletters
    
    def _update_archive_metadata(self) -> None:
        """Update archive metadata file for use by other components."""
        
        newsletters = self.get_newsletter_list()
        
        metadata = {
            'last_updated': datetime.now().isoformat(),
            'total_newsletters': len(newsletters),
            'max_newsletters': self.max_newsletters,
            'newsletters': [
                {
                    'filename': n['filename'],
                    'date': n['date'].isoformat(),
                    'formatted_date': n['formatted_date'],
                    'relative_path': n['relative_path']
                }
                for n in newsletters
            ]
        }
        
        metadata_path = self.output_dir / "archive_metadata.json"
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.debug(f"Archive metadata updated: {metadata_path}")
        except Exception as e:
            logger.error(f"Failed to update archive metadata: {e}")
    
    def cleanup_orphaned_files(self) -> int:
        """
        Clean up orphaned or invalid newsletter files.
        
        Returns:
            Number of files cleaned up
        """
        logger.info("Cleaning up orphaned newsletter files")
        
        cleaned_count = 0
        
        for file_path in self.newsletters_dir.glob("newsletter-*.html"):
            try:
                # Validate filename format
                date_str = file_path.stem.replace('newsletter-', '')
                datetime.strptime(date_str, '%Y-%m-%d')
                
                # Check if file is readable
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(100)  # Read first 100 chars
                    if not content.strip():
                        logger.warning(f"Removing empty newsletter file: {file_path.name}")
                        file_path.unlink()
                        cleaned_count += 1
                        
            except ValueError:
                logger.warning(f"Removing file with invalid date format: {file_path.name}")
                file_path.unlink()
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Error processing file {file_path.name}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} orphaned files")
            self._update_archive_metadata()
        
        return cleaned_count
    
    def get_stats(self) -> Dict:
        """Get archive statistics."""
        
        newsletters = self.get_newsletter_list()
        
        if newsletters:
            oldest_date = min(n['date'] for n in newsletters)
            newest_date = max(n['date'] for n in newsletters)
            total_size = sum(n['file_size'] for n in newsletters)
        else:
            oldest_date = newest_date = None
            total_size = 0
        
        return {
            'total_newsletters': len(newsletters),
            'max_newsletters': self.max_newsletters,
            'oldest_newsletter': oldest_date.isoformat() if oldest_date else None,
            'newest_newsletter': newest_date.isoformat() if newest_date else None,
            'total_size_bytes': total_size,
            'archive_directory': str(self.newsletters_dir),
            'is_at_capacity': len(newsletters) >= self.max_newsletters
        }
    
    def validate_archive_integrity(self) -> Dict:
        """
        Validate archive integrity and return report.
        
        Returns:
            Validation report dictionary
        """
        report = {
            'valid': True,
            'issues': [],
            'warnings': [],
            'newsletters_checked': 0,
            'total_size_mb': 0
        }
        
        newsletters = self.get_newsletter_list()
        
        for newsletter in newsletters:
            report['newsletters_checked'] += 1
            file_path = Path(newsletter['path'])
            
            # Check file exists
            if not file_path.exists():
                report['valid'] = False
                report['issues'].append(f"Missing file: {newsletter['filename']}")
                continue
            
            # Check file size
            file_size = file_path.stat().st_size
            report['total_size_mb'] += file_size / (1024 * 1024)
            
            if file_size < 1000:  # Less than 1KB
                report['warnings'].append(f"Suspiciously small file: {newsletter['filename']} ({file_size} bytes)")
            elif file_size > 10 * 1024 * 1024:  # More than 10MB
                report['warnings'].append(f"Large file: {newsletter['filename']} ({file_size / 1024 / 1024:.1f} MB)")
            
            # Check file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(500)  # Read first 500 chars
                    if not content.strip():
                        report['issues'].append(f"Empty file: {newsletter['filename']}")
                        report['valid'] = False
                    elif not content.lower().startswith('<!doctype html'):
                        report['warnings'].append(f"File doesn't start with HTML doctype: {newsletter['filename']}")
            except Exception as e:
                report['issues'].append(f"Cannot read file {newsletter['filename']}: {e}")
                report['valid'] = False
        
        # Check for gaps in dates
        if len(newsletters) > 1:
            dates = sorted([n['date'] for n in newsletters])
            for i in range(1, len(dates)):
                gap = (dates[i] - dates[i-1]).days
                if gap > 7:  # More than a week gap
                    report['warnings'].append(f"Large date gap: {gap} days between {dates[i-1].strftime('%Y-%m-%d')} and {dates[i].strftime('%Y-%m-%d')}")
        
        report['total_size_mb'] = round(report['total_size_mb'], 2)
        
        logger.info(f"Archive integrity check: {'PASSED' if report['valid'] else 'FAILED'}, "
                   f"{len(report['issues'])} issues, {len(report['warnings'])} warnings")
        
        return report