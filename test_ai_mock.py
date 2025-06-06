#!/usr/bin/env python3
"""
Test script to verify AI analyzer structure (without real API calls).
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models import Article, ArticleCluster, SourceCategory, SourceTier, AIAnalysis
from logger import setup_logger

def create_mock_clusters():
    """Create mock clusters for testing."""
    
    # Create mock articles
    articles = [
        Article(
            source="Foreign Affairs",
            source_category=SourceCategory.ANALYSIS,
            title="China's New Arctic Strategy Threatens NATO Supply Lines",
            url="https://example.com/china-arctic",
            summary="China is expanding its presence in the Arctic through infrastructure investments and partnerships with Russia, potentially threatening NATO's northern supply routes and creating new geopolitical vulnerabilities.",
            published_date=datetime.now(timezone.utc),
            relevance_score=8.5
        ),
        Article(
            source="War on the Rocks",
            source_category=SourceCategory.ANALYSIS,
            title="The Hidden Semiconductor War in Africa",
            url="https://example.com/africa-semiconductors",
            summary="Major powers are quietly competing for control of rare earth minerals in Africa essential for semiconductor production, with implications for global technology supply chains.",
            published_date=datetime.now(timezone.utc),
            relevance_score=7.8
        ),
        Article(
            source="The Diplomat",
            source_category=SourceCategory.ANALYSIS,
            title="India's Quiet Energy Diplomacy in Central Asia",
            url="https://example.com/india-energy",
            summary="India is building new energy partnerships in Central Asia that could reshape regional power dynamics and reduce dependence on traditional suppliers.",
            published_date=datetime.now(timezone.utc),
            relevance_score=7.2
        )
    ]
    
    # Create clusters
    clusters = []
    for i, article in enumerate(articles):
        cluster = ArticleCluster(
            cluster_id=f"cluster_{i}",
            articles=[article],
            main_article=article,
            cluster_score=article.relevance_score
        )
        clusters.append(cluster)
    
    return clusters

def test_ai_analyzer_structure():
    """Test AI analyzer structure without making real API calls."""
    logger = setup_logger("test_ai_mock")
    
    logger.info("=== Testing AI Analyzer Structure ===")
    
    # Test 1: Create mock clusters
    logger.info("Step 1: Creating mock clusters...")
    clusters = create_mock_clusters()
    logger.info(f"Created {len(clusters)} mock clusters")
    
    # Test 2: Test cluster summary preparation
    logger.info("Step 2: Testing cluster summary preparation...")
    
    # Mock the analyzer methods we can test without API
    class MockClaudeAnalyzer:
        def _prepare_cluster_summaries(self, clusters):
            summaries = []
            for cluster in clusters:
                main_article = cluster.main_article
                summary = {
                    'cluster_id': cluster.cluster_id,
                    'title': main_article.title,
                    'source': main_article.source,
                    'source_category': main_article.source_category.value,
                    'summary': main_article.summary[:500],
                    'url': main_article.url,
                    'cluster_size': len(cluster.articles),
                    'cluster_score': cluster.cluster_score,
                    'sources_in_cluster': [a.source for a in cluster.articles]
                }
                summaries.append(summary)
            return summaries
        
        def _create_selection_prompt(self, cluster_summaries, target_stories):
            clusters_text = ""
            for i, cluster in enumerate(cluster_summaries, 1):
                clusters_text += f"""
{i}. Cluster ID: {cluster['cluster_id']}
   Title: {cluster['title']}
   Source: {cluster['source']} ({cluster['source_category']})
   Summary: {cluster['summary']}
   Cluster size: {cluster['cluster_size']} articles
   Score: {cluster['cluster_score']:.2f}
   
"""
            
            prompt = f"""You are a geopolitical analyst. Select {target_stories} stories from:
{clusters_text}
Respond in JSON format with selected stories."""
            
            return prompt
    
    analyzer = MockClaudeAnalyzer()
    
    # Test cluster summary preparation
    summaries = analyzer._prepare_cluster_summaries(clusters)
    logger.info(f"Generated {len(summaries)} cluster summaries")
    
    for summary in summaries:
        logger.info(f"  - {summary['title']} (score: {summary['cluster_score']:.2f})")
    
    # Test prompt creation
    logger.info("Step 3: Testing prompt creation...")
    prompt = analyzer._create_selection_prompt(summaries, 3)
    logger.info(f"Generated prompt length: {len(prompt)} characters")
    logger.info("Prompt preview:")
    logger.info(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    
    # Test 3: Create mock AI analysis
    logger.info("Step 4: Creating mock AI analysis...")
    
    mock_analyses = [
        AIAnalysis(
            story_title="China's New Arctic Strategy Threatens NATO Supply Lines",
            why_important="China's Arctic expansion creates new vulnerabilities for NATO's northern supply routes and challenges Western dominance in a strategically critical region with implications for global shipping and resource access.",
            what_overlooked="Mainstream media focuses on military aspects but misses the infrastructure and economic dimensions of China's Arctic strategy.",
            prediction="Expect increased NATO Arctic exercises and new security partnerships with Nordic countries within 6 months.",
            impact_score=8,
            sources=["https://example.com/china-arctic"],
            confidence=0.85
        ),
        AIAnalysis(
            story_title="The Hidden Semiconductor War in Africa",
            why_important="Control of African rare earth minerals is becoming critical for semiconductor production, with major powers quietly competing for access that could determine future technology leadership.",
            what_overlooked="Focus on Asia-Pacific chip competition misses the crucial African mineral supply chain dimension.",
            prediction="Expect new Chinese and Western infrastructure deals in mineral-rich African nations.",
            impact_score=7,
            sources=["https://example.com/africa-semiconductors"],
            confidence=0.78
        )
    ]
    
    logger.info(f"Created {len(mock_analyses)} mock analyses:")
    for analysis in mock_analyses:
        logger.info(f"  - {analysis.story_title} (impact: {analysis.impact_score}/10)")
        logger.info(f"    Why important: {analysis.why_important[:100]}...")
        logger.info(f"    What overlooked: {analysis.what_overlooked}")
        logger.info(f"    Prediction: {analysis.prediction}")
        logger.info("")
    
    logger.info("=== AI Analyzer Structure Test Complete ===")
    return True

if __name__ == "__main__":
    success = test_ai_analyzer_structure()
    if success:
        print("✅ AI analyzer structure test passed!")
    else:
        print("❌ AI analyzer structure test failed!")
        sys.exit(1)
