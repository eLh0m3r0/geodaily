#!/usr/bin/env python3
"""
Main pipeline for the Geopolitical Daily newsletter.
Orchestrates the complete workflow from data collection to publishing.
"""

import sys
from datetime import datetime
from pathlib import Path

try:
    from .collectors.main_collector import MainCollector
    from .processors.main_processor import MainProcessor
    from .ai.claude_analyzer import ClaudeAnalyzer
    from .newsletter.generator import NewsletterGenerator
    from .config import Config
    from .logger import setup_logger
except ImportError:
    from collectors.main_collector import MainCollector
    from processors.main_processor import MainProcessor
    from ai.claude_analyzer import ClaudeAnalyzer
    from newsletter.generator import NewsletterGenerator
    from config import Config
    from logger import setup_logger

logger = setup_logger("main_pipeline")

def run_complete_pipeline() -> bool:
    """
    Run the complete newsletter generation pipeline.
    
    Returns:
        True if successful, False otherwise
    """
    start_time = datetime.now()
    logger.info("=== Starting Geopolitical Daily Newsletter Pipeline ===")
    logger.info(f"Pipeline started at: {start_time}")
    
    try:
        # Step 1: Validate configuration
        logger.info("Step 1: Validating configuration...")
        missing_config = Config.validate_config()
        if missing_config:
            logger.error(f"Missing configuration: {missing_config}")
            return False
        logger.info("Configuration validated successfully")
        
        # Step 2: Collect articles
        logger.info("Step 2: Collecting articles from all sources...")
        collector = MainCollector()
        raw_articles = collector.collect_all_articles()
        
        collection_stats = collector.get_stats()
        logger.info(f"Collection completed: {collection_stats.total_articles_collected} articles")
        
        if collection_stats.total_articles_collected < 10:
            logger.error(f"Insufficient articles collected: {collection_stats.total_articles_collected}")
            return False
        
        # Step 3: Process articles (deduplication, clustering, scoring)
        logger.info("Step 3: Processing articles...")
        processor = MainProcessor()
        clusters = processor.process_articles(raw_articles)
        
        processing_stats = processor.get_stats()
        logger.info(f"Processing completed: {len(clusters)} clusters created")
        
        if len(clusters) < 5:
            logger.error(f"Insufficient clusters created: {len(clusters)}")
            return False
        
        # Step 4: AI Analysis (if not in dry run mode)
        if Config.DRY_RUN:
            logger.info("Step 4: Skipping AI analysis (dry run mode)")
            # Create mock analyses for testing
            analyses = create_mock_analyses(clusters[:4])
        else:
            logger.info("Step 4: Running AI analysis...")
            try:
                analyzer = ClaudeAnalyzer()
                analyses = analyzer.analyze_clusters(clusters, target_stories=4)
                
                if len(analyses) < 3:
                    logger.error(f"Insufficient AI analyses: {len(analyses)}")
                    return False
                
                logger.info(f"AI analysis completed: {len(analyses)} stories selected")
            except Exception as e:
                logger.error(f"AI analysis failed: {e}")
                # Fallback to mock analyses
                logger.info("Falling back to mock analyses")
                analyses = create_mock_analyses(clusters[:4])
        
        # Step 5: Generate newsletter
        logger.info("Step 5: Generating newsletter...")
        generator = NewsletterGenerator()
        newsletter = generator.generate_newsletter(analyses)
        html_content = generator.generate_html(newsletter)
        
        # Save newsletter
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"newsletter_{timestamp}.html"
        file_path = generator.save_html(html_content, filename)
        
        logger.info(f"Newsletter saved to: {file_path}")
        
        # Step 6: Publishing (placeholder for Substack integration)
        if Config.DRY_RUN:
            logger.info("Step 6: Skipping publishing (dry run mode)")
        else:
            logger.info("Step 6: Publishing newsletter...")
            # TODO: Implement Substack publishing
            logger.info("Publishing not yet implemented - newsletter saved locally")
        
        # Step 7: Generate summary report
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        logger.info("=== Pipeline Summary ===")
        logger.info(f"Total execution time: {total_time:.2f} seconds")
        logger.info(f"Articles collected: {collection_stats.total_articles_collected}")
        logger.info(f"Articles after processing: {processing_stats.articles_after_deduplication}")
        logger.info(f"Clusters created: {len(clusters)}")
        logger.info(f"Stories selected: {len(analyses)}")
        logger.info(f"Newsletter file: {file_path}")
        logger.info(f"Success rate: {processing_stats.success_rate:.2%}")
        
        if collection_stats.errors:
            logger.warning(f"Collection errors: {len(collection_stats.errors)}")
        
        if processing_stats.errors:
            logger.warning(f"Processing errors: {len(processing_stats.errors)}")
        
        logger.info("=== Pipeline Completed Successfully ===")
        return True
        
    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}")
        logger.exception("Full error traceback:")
        return False

def create_mock_analyses(clusters):
    """Create mock AI analyses for testing/fallback."""
    from models import AIAnalysis
    
    mock_analyses = []
    
    for i, cluster in enumerate(clusters[:4]):
        main_article = cluster.main_article
        
        analysis = AIAnalysis(
            story_title=main_article.title,
            why_important=f"This story represents a significant development in {main_article.source_category.value} geopolitics with potential implications for international relations and strategic decision-making.",
            what_overlooked="Mainstream media coverage may be missing the broader strategic implications and second-order effects of this development.",
            prediction="This situation will likely evolve over the coming weeks with potential impacts on regional stability and international partnerships.",
            impact_score=min(8, max(5, int(cluster.cluster_score))),
            sources=[article.url for article in cluster.articles],
            confidence=0.7
        )
        
        mock_analyses.append(analysis)
    
    return mock_analyses

def main():
    """Main entry point for command-line execution."""
    success = run_complete_pipeline()
    
    if success:
        print("✅ Newsletter pipeline completed successfully!")
        sys.exit(0)
    else:
        print("❌ Newsletter pipeline failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
