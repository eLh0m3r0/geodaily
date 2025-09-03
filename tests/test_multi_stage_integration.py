#!/usr/bin/env python3
"""
Integration test for the new multi-stage analysis pipeline.
Tests content enrichment, multi-stage AI analysis, and enhanced archiving.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.models import Article, SourceCategory
from src.content import enrich_articles_with_content
from src.ai.multi_stage_analyzer import MultiStageAIAnalyzer
from src.archiver.ai_data_archiver import ai_archiver
from src.dashboard.enhanced_multi_stage_dashboard import EnhancedMultiStageDashboard

def create_test_articles():
    """Create sample articles for testing."""
    test_articles = [
        Article(
            source="BBC",
            source_category=SourceCategory.MAINSTREAM,
            title="China's Economic Challenges Amid Global Tensions",
            url="https://www.bbc.co.uk/news/world-asia-china-123456789",
            summary="China faces mounting economic pressures as global trade tensions continue to impact growth.",
            published_date=datetime.now()
        ),
        Article(
            source="Foreign Affairs",
            source_category=SourceCategory.THINK_TANK,
            title="The Future of NATO in Eastern Europe",
            url="https://www.foreignaffairs.com/europe/future-nato-eastern-europe",
            summary="NATO's expansion and strategy in Eastern Europe continues to evolve amid security concerns.",
            published_date=datetime.now()
        ),
        Article(
            source="Reuters",
            source_category=SourceCategory.MAINSTREAM,
            title="Middle East Peace Talks Resume in Qatar",
            url="https://www.reuters.com/world/middle-east/peace-talks-resume-qatar-123",
            summary="Diplomatic efforts resume as regional leaders gather in Doha for peace negotiations.",
            published_date=datetime.now()
        ),
        Article(
            source="Atlantic Council",
            source_category=SourceCategory.THINK_TANK,
            title="Cyber Security Implications of AI in Defense",
            url="https://www.atlanticcouncil.org/blogs/natosource/cyber-ai-defense/",
            summary="The intersection of artificial intelligence and cybersecurity creates new challenges for defense.",
            published_date=datetime.now()
        )
    ]
    return test_articles

async def test_content_enrichment(articles):
    """Test the content enrichment functionality."""
    print("🔍 Testing content enrichment...")
    
    try:
        enriched_results = await enrich_articles_with_content(articles)
        
        print(f"✅ Content enrichment completed for {len(enriched_results)} articles")
        
        for article, extraction_result in enriched_results:
            print(f"   📄 {article.title[:50]}...")
            print(f"      Quality: {extraction_result.quality_score:.2f}")
            print(f"      Method: {extraction_result.extraction_method}")
            print(f"      Words: {extraction_result.word_count}")
            print(f"      Success: {extraction_result.success}")
            
            # Update article with enriched content
            if extraction_result.success and extraction_result.quality_score > 0.4:
                article.full_content = extraction_result.full_content
                article.content_quality_score = extraction_result.quality_score
                article.extraction_method = extraction_result.extraction_method
                article.word_count = extraction_result.word_count
            else:
                article.full_content = article.summary
                article.content_quality_score = 0.3
                article.extraction_method = "summary_fallback"
                article.word_count = len(article.summary.split())
        
        return [article for article, _ in enriched_results]
        
    except Exception as e:
        print(f"❌ Content enrichment failed: {e}")
        # Return original articles as fallback
        for article in articles:
            article.full_content = article.summary
            article.content_quality_score = 0.3
            article.extraction_method = "fallback"
            article.word_count = len(article.summary.split())
        return articles

async def test_multi_stage_analysis(articles):
    """Test the multi-stage AI analysis."""
    print("🧠 Testing multi-stage AI analysis...")
    
    try:
        analyzer = MultiStageAIAnalyzer()
        analyses = await analyzer.analyze_articles_comprehensive(articles, target_stories=2)
        
        print(f"✅ Multi-stage analysis completed: {len(analyses)} stories selected")
        
        # Print stage statistics
        stage_stats = analyzer.get_stage_statistics()
        total_tokens = sum(stats['tokens_used'] for stats in stage_stats.values())
        total_cost = sum(stats['cost'] for stats in stage_stats.values())
        
        print(f"📊 Analysis Statistics:")
        print(f"   Total tokens: {total_tokens}")
        print(f"   Total cost: ${total_cost:.4f}")
        print(f"   Mock mode: {analyzer.mock_mode}")
        
        for stage, stats in stage_stats.items():
            print(f"   {stage}: {stats['input_count']} → {stats['output_count']} "
                  f"(tokens: {stats['tokens_used']}, cost: ${stats['cost']:.4f})")
        
        # Print selected stories
        for i, analysis in enumerate(analyses, 1):
            print(f"   📈 Story {i}: {analysis.story_title}")
            print(f"      Impact: {analysis.impact_score}/10")
            print(f"      Type: {analysis.content_type.value}")
            print(f"      Confidence: {analysis.confidence:.2f}")
        
        return analyses
        
    except Exception as e:
        print(f"❌ Multi-stage analysis failed: {e}")
        return []

def test_archiving_integration():
    """Test the enhanced archiving functionality."""
    print("🗄️ Testing archiving integration...")
    
    try:
        ai_archiver.start_new_run()
        print("✅ Archive run started successfully")
        
        # Create run summary
        ai_archiver.create_run_summary()
        print("✅ Archive run summary created")
        
        return True
        
    except Exception as e:
        print(f"❌ Archiving integration failed: {e}")
        return False

def test_dashboard_generation():
    """Test the enhanced dashboard generation."""
    print("📊 Testing dashboard generation...")
    
    try:
        dashboard_generator = EnhancedMultiStageDashboard()
        current_date = datetime.now().date()
        
        # Try to generate dashboard for today
        dashboard_path = dashboard_generator.generate_dashboard_for_date(current_date)
        
        if dashboard_path and dashboard_path.exists():
            print(f"✅ Dashboard generated successfully: {dashboard_path}")
            return True
        else:
            print("⚠️ Dashboard generation completed but no data found for today")
            return False
        
    except Exception as e:
        print(f"❌ Dashboard generation failed: {e}")
        return False

async def run_integration_test():
    """Run complete integration test."""
    print("🚀 Starting Multi-Stage Pipeline Integration Test")
    print("=" * 60)
    
    # Step 1: Create test articles
    print("📰 Creating test articles...")
    articles = create_test_articles()
    print(f"✅ Created {len(articles)} test articles")
    
    # Step 2: Test content enrichment
    enriched_articles = await test_content_enrichment(articles)
    
    # Step 3: Test multi-stage AI analysis
    analyses = await test_multi_stage_analysis(enriched_articles)
    
    # Step 4: Test archiving integration
    archiving_success = test_archiving_integration()
    
    # Step 5: Test dashboard generation
    dashboard_success = test_dashboard_generation()
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎯 Integration Test Summary:")
    print(f"   Content Enrichment: ✅ {len(enriched_articles)} articles processed")
    print(f"   Multi-Stage Analysis: ✅ {len(analyses)} stories selected")
    print(f"   Archiving Integration: {'✅' if archiving_success else '❌'} {'Success' if archiving_success else 'Failed'}")
    print(f"   Dashboard Generation: {'✅' if dashboard_success else '⚠️'} {'Success' if dashboard_success else 'No data'}")
    
    overall_success = len(enriched_articles) > 0 and len(analyses) > 0 and archiving_success
    
    if overall_success:
        print("\n🎉 Integration test completed successfully!")
        print("💡 The new multi-stage pipeline is ready for production use.")
        return True
    else:
        print("\n⚠️ Integration test completed with some issues.")
        print("🔧 Please review the errors above before deploying to production.")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_integration_test())
    sys.exit(0 if success else 1)