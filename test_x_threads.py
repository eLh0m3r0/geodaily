#!/usr/bin/env python3
"""
Test script for X.com thread generation functionality.
Tests both mock and real generation (controlled by DRY_RUN).
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.models import AIAnalysis
from src.social.x_thread_generator import XThreadGenerator
from datetime import datetime

def create_sample_analysis():
    """Create a sample AIAnalysis for testing"""
    from src.models import ContentType
    
    return AIAnalysis(
        story_title="Putin's Middle East Strategy Faces Critical Failure as Regional Powers Realign",
        why_important="This shift threatens Russia's global power projection capabilities and could fundamentally alter Europe's energy security landscape. The vacuum left by Russia's retreat may lead to increased regional instability or new Western influence.",
        what_overlooked="Most coverage focuses on immediate military aspects, but the real story is the collapse of Russia's soft power infrastructure.",
        prediction="Turkey moves in Syria, Iran pivots to China, Saudi-Israeli cooperation likely.",
        sources=[
            "https://www.foreignaffairs.com/russia/real-meaning-putins-middle-east-failure",
            "https://www.csis.org/analysis/russia-middle-east-strategy"
        ],
        impact_score=9,
        urgency_score=9,
        scope_score=8,
        novelty_score=7,
        credibility_score=9,
        impact_dimension_score=9,
        content_type=ContentType.BREAKING_NEWS,
        confidence=0.85
    )

def test_mock_generation():
    """Test mock thread generation without API calls"""
    print("\n" + "="*60)
    print("Testing MOCK thread generation (no API calls)")
    print("="*60)
    
    generator = XThreadGenerator()
    analysis = create_sample_analysis()
    
    # Generate mock thread
    thread_data = generator.generate_mock_thread(analysis)
    
    if thread_data:
        print(f"\n✅ Thread generated: {thread_data['thread_title']}")
        print(f"   Tweets: {len(thread_data['tweets'])}")
        print(f"   Hashtags: {', '.join(thread_data['hashtags'])}")
        print(f"   Engagement estimate: {thread_data['estimated_engagement']}/10")
        
        print("\n📝 Thread content:")
        for tweet in thread_data['tweets']:
            print(f"\n   Tweet {tweet['number']}:")
            print(f"   {tweet['content']}")
            print(f"   [{tweet['char_count']}/280 chars]")
        
        return thread_data
    else:
        print("❌ Failed to generate mock thread")
        return None

def test_html_export(threads):
    """Test HTML export functionality"""
    print("\n" + "="*60)
    print("Testing HTML export")
    print("="*60)
    
    generator = XThreadGenerator()
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    html_path = generator.export_html(threads, current_date)
    json_path = generator.export_json(threads, current_date)
    
    print(f"\n✅ HTML exported to: {html_path}")
    print(f"✅ JSON exported to: {json_path}")
    
    # Verify files exist and have content
    html_file = Path(html_path)
    json_file = Path(json_path)
    
    if html_file.exists():
        print(f"   HTML file size: {html_file.stat().st_size:,} bytes")
    else:
        print("   ❌ HTML file not found!")
        
    if json_file.exists():
        print(f"   JSON file size: {json_file.stat().st_size:,} bytes")
    else:
        print("   ❌ JSON file not found!")
    
    return html_path, json_path

def test_real_generation():
    """Test real thread generation with Claude API (if not in DRY_RUN)"""
    if Config.DRY_RUN:
        print("\n⚠️  Skipping real API test (DRY_RUN=true)")
        return None
    
    if not Config.ANTHROPIC_API_KEY:
        print("\n⚠️  Skipping real API test (no API key configured)")
        return None
    
    print("\n" + "="*60)
    print("Testing REAL thread generation (Claude API)")
    print("="*60)
    
    from anthropic import Anthropic
    
    generator = XThreadGenerator()
    analysis = create_sample_analysis()
    api_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    
    # Generate real thread
    thread_data = generator.generate_thread_from_analysis(analysis, api_client)
    
    if thread_data:
        print(f"\n✅ Thread generated via Claude API: {thread_data['thread_title']}")
        print(f"   Tweets: {len(thread_data['tweets'])}")
        print(f"   Language: Czech")
        
        print("\n📝 Czech thread content:")
        for tweet in thread_data['tweets']:
            print(f"\n   Tweet {tweet['number']}:")
            print(f"   {tweet['content']}")
            print(f"   [{tweet['char_count']}/280 chars]")
            
            # Validate character count
            if tweet['char_count'] > 280:
                print(f"   ⚠️  WARNING: Tweet exceeds 280 character limit!")
        
        return thread_data
    else:
        print("❌ Failed to generate thread via API")
        return None

def main():
    """Run all tests"""
    print("\n🐦 X.com Thread Generator Test Suite")
    print(f"   Config: DRY_RUN={Config.DRY_RUN}")
    print(f"   X_THREADS_ENABLED={Config.X_THREADS_ENABLED}")
    print(f"   Max threads per day: {Config.X_THREADS_MAX_DAILY}")
    print(f"   Min impact score: {Config.X_THREADS_MIN_IMPACT_SCORE}")
    
    # Test 1: Mock generation
    mock_thread = test_mock_generation()
    
    if mock_thread:
        # Test 2: HTML export with mock data
        test_html_export([mock_thread])
        
        # Test 3: Real API generation (if available)
        real_thread = test_real_generation()
        
        if real_thread:
            # Test 4: Export both threads
            print("\n" + "="*60)
            print("Exporting combined threads (mock + real)")
            print("="*60)
            test_html_export([mock_thread, real_thread])
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
    
    # Show where to find the exported files
    output_dir = Path("docs/threads")
    if output_dir.exists():
        files = list(output_dir.glob("*"))
        if files:
            print(f"\n📁 Generated files in {output_dir}:")
            for f in sorted(files)[-5:]:  # Show last 5 files
                print(f"   - {f.name}")

if __name__ == "__main__":
    main()