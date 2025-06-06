#!/usr/bin/env python3
"""
Test script to verify newsletter generation works.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models import AIAnalysis
from newsletter.generator import NewsletterGenerator
from logger import setup_logger

def create_mock_analyses():
    """Create mock AI analyses for testing."""
    
    analyses = [
        AIAnalysis(
            story_title="China's New Arctic Strategy Threatens NATO Supply Lines",
            why_important="China is expanding its presence in the Arctic through infrastructure investments and partnerships with Russia, potentially threatening NATO's northern supply routes and creating new geopolitical vulnerabilities that could reshape global shipping patterns.",
            what_overlooked="Mainstream media focuses on military aspects but misses the infrastructure and economic dimensions of China's long-term Arctic strategy.",
            prediction="Expect increased NATO Arctic exercises and new security partnerships with Nordic countries within 6 months.",
            impact_score=8,
            sources=[
                "https://foreignaffairs.com/china-arctic-strategy",
                "https://warontherocks.com/nato-arctic-vulnerability"
            ],
            confidence=0.85
        ),
        AIAnalysis(
            story_title="The Hidden Semiconductor War in Africa",
            why_important="Major powers are quietly competing for control of rare earth minerals in Africa essential for semiconductor production, with implications for global technology supply chains and future innovation leadership.",
            what_overlooked="Focus on Asia-Pacific chip competition misses the crucial African mineral supply chain dimension that could determine technological sovereignty.",
            prediction="Expect new Chinese and Western infrastructure deals in mineral-rich African nations, particularly in DRC and Madagascar.",
            impact_score=7,
            sources=[
                "https://thediplomat.com/africa-semiconductors",
                "https://foreignpolicy.com/rare-earth-africa"
            ],
            confidence=0.78
        ),
        AIAnalysis(
            story_title="India's Quiet Energy Diplomacy in Central Asia",
            why_important="India is building new energy partnerships in Central Asia that could reshape regional power dynamics and reduce dependence on traditional suppliers, challenging both Russian and Chinese influence.",
            what_overlooked="Western analysis focuses on Russia-China competition but underestimates India's growing role as a third major power in Central Asian energy markets.",
            prediction="India will announce major pipeline or LNG deals with Kazakhstan or Uzbekistan before year-end.",
            impact_score=6,
            sources=[
                "https://carnegieendowment.org/india-central-asia",
                "https://csis.org/energy-diplomacy-india"
            ],
            confidence=0.72
        ),
        AIAnalysis(
            story_title="Turkey's Drone Diplomacy Reshapes Middle East Alliances",
            why_important="Turkey's military drone exports are creating new alliance patterns in the Middle East and Africa, giving Ankara unprecedented influence over regional conflicts and challenging traditional arms suppliers.",
            what_overlooked="Analysis focuses on individual conflicts but misses how drone diplomacy is systematically reshaping Turkey's strategic position across multiple regions.",
            prediction="Turkey will secure major drone deals with at least two African nations, expanding its influence beyond the Middle East.",
            impact_score=9,
            sources=[
                "https://atlanticcouncil.org/turkey-drone-diplomacy",
                "https://brookings.edu/middle-east-drones"
            ],
            confidence=0.88
        )
    ]
    
    return analyses

def test_newsletter_generation():
    """Test newsletter generation functionality."""
    logger = setup_logger("test_newsletter")
    
    logger.info("=== Testing Newsletter Generation ===")
    
    # Step 1: Create mock analyses
    logger.info("Step 1: Creating mock AI analyses...")
    analyses = create_mock_analyses()
    logger.info(f"Created {len(analyses)} mock analyses")
    
    # Step 2: Initialize generator
    logger.info("Step 2: Initializing newsletter generator...")
    generator = NewsletterGenerator()
    
    # Step 3: Generate newsletter object
    logger.info("Step 3: Generating newsletter object...")
    newsletter = generator.generate_newsletter(analyses)
    
    logger.info(f"Newsletter generated:")
    logger.info(f"  - Title: {newsletter.title}")
    logger.info(f"  - Date: {newsletter.date.strftime('%Y-%m-%d')}")
    logger.info(f"  - Stories: {len(newsletter.stories)}")
    logger.info(f"  - Intro length: {len(newsletter.intro_text)} characters")
    
    # Step 4: Generate HTML
    logger.info("Step 4: Generating HTML content...")
    html_content = generator.generate_html(newsletter)
    
    logger.info(f"HTML generated:")
    logger.info(f"  - Content length: {len(html_content)} characters")
    logger.info(f"  - Contains title: {'<title>' in html_content}")
    logger.info(f"  - Contains stories: {all(story.story_title in html_content for story in newsletter.stories)}")
    
    # Step 5: Save HTML file
    logger.info("Step 5: Saving HTML file...")
    file_path = generator.save_html(html_content, "test_newsletter.html")
    
    logger.info(f"Newsletter saved to: {file_path}")
    logger.info(f"File exists: {file_path.exists()}")
    
    if file_path.exists():
        file_size = file_path.stat().st_size
        logger.info(f"File size: {file_size} bytes")
    
    # Step 6: Display sample content
    logger.info("Step 6: Sample newsletter content:")
    logger.info("Stories included:")
    for i, story in enumerate(newsletter.stories, 1):
        logger.info(f"  {i}. {story.story_title} (Impact: {story.impact_score}/10)")
        logger.info(f"     Why important: {story.why_important[:100]}...")
        logger.info(f"     What overlooked: {story.what_overlooked}")
        logger.info("")
    
    logger.info("=== Newsletter Generation Test Complete ===")
    return file_path.exists() and len(html_content) > 1000

if __name__ == "__main__":
    success = test_newsletter_generation()
    if success:
        print("✅ Newsletter generation test passed!")
        print("📧 Check the generated test_newsletter.html file in the output/ directory")
    else:
        print("❌ Newsletter generation test failed!")
        sys.exit(1)
