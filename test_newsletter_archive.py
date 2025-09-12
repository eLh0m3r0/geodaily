#!/usr/bin/env python3
"""
Test script for Newsletter Archive Manager functionality.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.publishers.newsletter_archive_manager import NewsletterArchiveManager
from src.publishers.github_pages_publisher import GitHubPagesPublisher
from src.models import Newsletter, AIAnalysis, ContentType
from src.logger import get_logger

logger = get_logger(__name__)

def create_mock_newsletter(date: datetime, title: str = "Test Newsletter") -> Newsletter:
    """Create a mock newsletter for testing."""
    
    # Create mock AI analyses
    mock_analyses = [
        AIAnalysis(
            story_title=f"Test Story {i+1} - {date.strftime('%Y-%m-%d')}",
            why_important=f"This is why story {i+1} matters on {date.strftime('%Y-%m-%d')}",
            what_overlooked=f"What others are missing about story {i+1}",
            prediction=f"What to watch for story {i+1}",
            confidence=0.8,
            impact_score=7 + i,
            sources=[f"https://example.com/story{i+1}"],
            urgency_score=5 + i,
            scope_score=6 + i,
            novelty_score=4 + i,
            credibility_score=8,
            impact_dimension_score=7 + i,
            content_type=ContentType.ANALYSIS
        )
        for i in range(3)
    ]
    
    return Newsletter(
        date=date,
        title=title,
        stories=mock_analyses,
        intro_text=f"Test newsletter for {date.strftime('%B %d, %Y')}",
        footer_text="Test footer"
    )

def generate_mock_html(newsletter: Newsletter) -> str:
    """Generate mock HTML content for testing."""
    
    stories_html = ""
    for story in newsletter.stories:
        stories_html += f"""
        <div class="story">
            <h2>{story.story_title}</h2>
            <p><strong>Impact Score:</strong> {story.impact_score}/10</p>
            <p><strong>Why This Matters:</strong> {story.why_important}</p>
            <p><strong>What Others Miss:</strong> {story.what_overlooked}</p>
            <p><strong>What to Watch:</strong> {story.prediction}</p>
        </div>
        """
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{newsletter.title} - {newsletter.date.strftime('%Y-%m-%d')}</title>
</head>
<body>
    <h1>{newsletter.title}</h1>
    <p class="date">{newsletter.date.strftime('%B %d, %Y')}</p>
    <div class="intro">{newsletter.intro_text}</div>
    {stories_html}
    <footer>{newsletter.footer_text}</footer>
</body>
</html>"""

def test_archive_manager():
    """Test the Newsletter Archive Manager functionality."""
    
    print("🧪 Testing Newsletter Archive Manager...")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Initialize archive manager with max 5 newsletters for testing
        archive_manager = NewsletterArchiveManager(temp_dir, max_newsletters=5)
        
        # Test 1: Add newsletters one by one
        print("\n📰 Test 1: Adding newsletters sequentially...")
        
        newsletters = []
        base_date = datetime.now() - timedelta(days=10)
        
        for i in range(7):  # Add 7 newsletters (more than max of 5)
            date = base_date + timedelta(days=i)
            newsletter = create_mock_newsletter(date, f"Test Newsletter #{i+1}")
            html_content = generate_mock_html(newsletter)
            
            path = archive_manager.add_newsletter(html_content, date)
            print(f"  ✅ Added newsletter for {date.strftime('%Y-%m-%d')}: {Path(path).name}")
            newsletters.append((date, newsletter))
        
        # Check that only 5 newsletters remain
        newsletter_list = archive_manager.get_newsletter_list()
        print(f"\n📊 Archive status: {len(newsletter_list)} newsletters (max: {archive_manager.max_newsletters})")
        
        if len(newsletter_list) == 5:
            print("  ✅ Archive rotation working correctly!")
        else:
            print(f"  ❌ Expected 5 newsletters, found {len(newsletter_list)}")
            return False
        
        # Check that we have the 5 most recent ones
        expected_dates = sorted([date for date, _ in newsletters], reverse=True)[:5]
        actual_dates = [n['date'] for n in newsletter_list]
        
        # Convert to strings for comparison
        expected_date_strs = [d.strftime('%Y-%m-%d') for d in expected_dates]
        actual_date_strs = [d.strftime('%Y-%m-%d') for d in actual_dates]
        
        if actual_date_strs == expected_date_strs:
            print("  ✅ Correct newsletters retained (newest 5)")
        else:
            print("  ❌ Wrong newsletters retained")
            print(f"    Expected: {expected_date_strs}")
            print(f"    Actual: {actual_date_strs}")
            return False
        
        # Test 2: Statistics
        print("\n📈 Test 2: Archive statistics...")
        stats = archive_manager.get_stats()
        print(f"  📊 Total newsletters: {stats['total_newsletters']}")
        print(f"  🗓️ Oldest: {stats['oldest_newsletter']}")
        print(f"  🗓️ Newest: {stats['newest_newsletter']}")
        print(f"  📁 Size: {stats['total_size_bytes']} bytes")
        print(f"  ⚠️ At capacity: {stats['is_at_capacity']}")
        
        # Test 3: Integrity validation
        print("\n🔍 Test 3: Archive integrity validation...")
        report = archive_manager.validate_archive_integrity()
        
        if report['valid']:
            print("  ✅ Archive integrity check passed!")
            if report['warnings']:
                print(f"  ⚠️ {len(report['warnings'])} warnings:")
                for warning in report['warnings']:
                    print(f"    - {warning}")
        else:
            print("  ❌ Archive integrity check failed!")
            for issue in report['issues']:
                print(f"    ❌ {issue}")
            return False
        
        # Test 4: Archive metadata
        print("\n📄 Test 4: Archive metadata...")
        metadata_path = Path(temp_dir) / "archive_metadata.json"
        
        if metadata_path.exists():
            print("  ✅ Archive metadata file created")
            
            import json
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            print(f"  📊 Metadata contains {len(metadata['newsletters'])} newsletters")
            print(f"  🕒 Last updated: {metadata['last_updated']}")
        else:
            print("  ❌ Archive metadata file not found")
            return False
        
        print("\n✅ All Archive Manager tests passed!")
        return True

def test_github_pages_publisher():
    """Test the GitHub Pages Publisher with Archive Manager integration."""
    
    print("\n🌐 Testing GitHub Pages Publisher with Archive Manager...")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Initialize publisher with max 3 newsletters for testing
        publisher = GitHubPagesPublisher(output_dir=temp_dir, max_newsletters=3)
        
        # Create newsletters
        base_date = datetime.now() - timedelta(days=5)
        
        for i in range(5):  # Add 5 newsletters (more than max of 3)
            date = base_date + timedelta(days=i)
            newsletter = create_mock_newsletter(date, f"GitHub Test Newsletter #{i+1}")
            
            # Mock AI analyses for publisher
            analyses = newsletter.stories
            
            print(f"  📰 Publishing newsletter for {date.strftime('%Y-%m-%d')}...")
            
            try:
                url = publisher.publish_newsletter(newsletter, analyses)
                print(f"    ✅ Published to: {url}")
            except Exception as e:
                print(f"    ❌ Failed to publish: {e}")
                return False
        
        # Check statistics
        stats = publisher.get_stats()
        print(f"\n📊 Publisher stats:")
        print(f"  📰 Total newsletters: {stats['total_newsletters']}")
        print(f"  📰 Max newsletters: {stats['max_newsletters']}")
        print(f"  ⚠️ At capacity: {stats['archive_at_capacity']}")
        
        # Verify files exist
        docs_dir = Path(temp_dir)
        
        expected_files = [
            "index.html",
            "archive.html", 
            "about.html",
            "feed.xml",
            "archive_metadata.json",
            "assets/style.css"
        ]
        
        for file_path in expected_files:
            full_path = docs_dir / file_path
            if full_path.exists():
                print(f"  ✅ {file_path} created")
            else:
                print(f"  ❌ {file_path} missing")
                return False
        
        # Check newsletter files (should only have 3)
        newsletter_files = list((docs_dir / "newsletters").glob("newsletter-*.html"))
        print(f"  📁 Newsletter files: {len(newsletter_files)}")
        
        if len(newsletter_files) == 3:
            print("  ✅ Correct number of newsletter files retained")
        else:
            print(f"  ❌ Expected 3 newsletter files, found {len(newsletter_files)}")
            return False
        
        # Check that index.html contains links to all 3 newsletters
        with open(docs_dir / "index.html", 'r') as f:
            index_content = f.read()
        
        link_count = index_content.count('newsletters/newsletter-')
        if link_count == 3:
            print("  ✅ Index page contains correct number of newsletter links")
        else:
            print(f"  ❌ Index page should contain 3 newsletter links, found {link_count}")
            return False
        
        print("\n✅ All GitHub Pages Publisher tests passed!")
        return True

def main():
    """Run all tests."""
    
    print("🚀 Starting Newsletter Archive Tests")
    print("=" * 50)
    
    try:
        # Test Archive Manager
        if not test_archive_manager():
            print("\n❌ Archive Manager tests failed!")
            sys.exit(1)
        
        # Test GitHub Pages Publisher
        if not test_github_pages_publisher():
            print("\n❌ GitHub Pages Publisher tests failed!")
            sys.exit(1)
        
        print("\n" + "=" * 50)
        print("🎉 All tests passed! Archive functionality is working correctly.")
        print("\nKey features verified:")
        print("✅ Newsletter rotation (keeps only N most recent)")
        print("✅ Archive metadata generation")
        print("✅ HTML page updates with archive links")
        print("✅ RSS feed integration")
        print("✅ Integrity validation")
        print("✅ Statistics reporting")
        
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()