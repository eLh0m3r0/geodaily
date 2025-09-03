#!/usr/bin/env python3
"""
Main pipeline for the Geopolitical Daily newsletter.
Orchestrates the complete workflow from data collection to publishing.
"""

import sys
import time
import os
import asyncio
from datetime import datetime
from pathlib import Path

from .collectors.main_collector import MainCollector
from .processors.main_processor import MainProcessor
from .processors.content_quality_validator import content_quality_validator
from .ai.claude_analyzer import ClaudeAnalyzer
from .ai.simple_multi_stage_analyzer import SimplifiedMultiStageAnalyzer
from .ai.cost_controller import ai_cost_controller
from .archiver.ai_data_archiver import ai_archiver
from .content import enrich_articles_with_content
from .dashboard.enhanced_multi_stage_dashboard import EnhancedMultiStageDashboard
from .newsletter.generator import NewsletterGenerator
from .publishers.github_pages_publisher import GitHubPagesPublisher
from .notifications.email_notifier import EmailNotifier
from .metrics.collector import MetricsCollector
from .config import Config
from .logging_system import (
    setup_structured_logging, get_metrics_aware_logger,
    PipelineStage, ErrorCategory, PerformanceProfiler,
    PipelineTracker, error_handler, retry_on_error
)
from .cleanup import CleanupManager
from .resilience.graceful_degradation import degradation_manager
from .resilience.network_resilience import network_manager, rss_manager, scraping_manager
from .resilience.health_monitoring import health_monitor

# Initialize structured logging with metrics integration
logger = setup_structured_logging()
metrics_collector = MetricsCollector()
pipeline_tracker = PipelineTracker(logger)

@error_handler(logger, pipeline_stage=PipelineStage.INITIALIZATION)
def run_complete_pipeline() -> bool:
    """
    Run the complete newsletter generation pipeline.

    Returns:
        True if successful, False otherwise
    """
    start_time = datetime.now()
    run_id = metrics_collector.start_pipeline_run()

    # Track pipeline start
    pipeline_tracker.track_pipeline_start(run_id)

    logger.info("=== Starting Geopolitical Daily Newsletter Pipeline ===",
               pipeline_stage=PipelineStage.INITIALIZATION,
               run_id=run_id,
               structured_data={
                   'start_time': start_time.isoformat(),
                   'config': {
                       'ai_provider': Config.AI_PROVIDER,
                       'ai_model': Config.AI_MODEL,
                       'dry_run': Config.DRY_RUN
                   }
               })

    # Initialize AI archiver for this run
    ai_archiver.start_new_run()
    
    try:
        # Step 0: Check for duplicate newsletter (same date)
        current_date = datetime.now().date()
        from pathlib import Path
        docs_dir = Path("docs")
        newsletter_filename = f"newsletter-{current_date.strftime('%Y-%m-%d')}.html"
        newsletter_path = docs_dir / "newsletters" / newsletter_filename

        # Allow overwriting if explicitly requested via environment variable or debug mode
        allow_overwrite = Config.DEBUG or os.getenv('ALLOW_OVERWRITE', '').lower() in ('true', '1', 'yes')

        if newsletter_path.exists() and not allow_overwrite:
            logger.warning(f"Newsletter for {current_date.strftime('%Y-%m-%d')} already exists. Skipping pipeline execution to prevent duplicates.",
                          pipeline_stage=PipelineStage.INITIALIZATION,
                          run_id=run_id,
                          structured_data={
                              'existing_file': str(newsletter_path),
                              'reason': 'duplicate_prevention',
                              'allow_overwrite': allow_overwrite
                          })
            pipeline_tracker.track_pipeline_success(run_id, 0)  # Mark as successful with 0 execution time
            return True  # Return True since this is expected behavior
        elif newsletter_path.exists() and allow_overwrite:
            logger.info(f"Newsletter for {current_date.strftime('%Y-%m-%d')} already exists but overwrite is allowed. Continuing with pipeline execution.",
                       pipeline_stage=PipelineStage.INITIALIZATION,
                       run_id=run_id,
                       structured_data={
                           'existing_file': str(newsletter_path),
                           'action': 'overwrite_allowed',
                           'allow_overwrite': allow_overwrite
                       })

        # Step 1: Validate configuration
        with PerformanceProfiler.profile_operation("config_validation", logger):
            logger.info("Step 1: Validating configuration...",
                        pipeline_stage=PipelineStage.CONFIGURATION,
                        run_id=run_id)

            missing_config = Config.validate_config()
            if missing_config:
                logger.error(f"Missing configuration: {missing_config}",
                            pipeline_stage=PipelineStage.CONFIGURATION,
                            run_id=run_id,
                            error_category=ErrorCategory.CONFIGURATION_ERROR,
                            structured_data={'missing_items': missing_config})
                pipeline_tracker.track_pipeline_failure(run_id, ValueError("Missing configuration"), PipelineStage.CONFIGURATION)
                return False

            logger.info("Configuration validated successfully",
                        pipeline_stage=PipelineStage.CONFIGURATION,
                        run_id=run_id,
                        structured_data={'validated_items': ['api_keys', 'sources_file']})

            # Initialize resilience infrastructure
            with PerformanceProfiler.profile_operation("resilience_init", logger):
                logger.info("Initializing resilience infrastructure...",
                           pipeline_stage=PipelineStage.CONFIGURATION,
                           run_id=run_id)

                # Register system components for graceful degradation
                degradation_manager.register_component(
                    "collection_system",
                    degradation_rules=[
                        # Will be populated based on actual component failures
                    ]
                )
                degradation_manager.register_component("ai_analyzer")
                degradation_manager.register_component("newsletter_generator")
                degradation_manager.register_component("publishing_system")

                # Start health monitoring
                health_monitor.start_monitoring()

                logger.info("Resilience infrastructure initialized",
                           pipeline_stage=PipelineStage.CONFIGURATION,
                           run_id=run_id,
                           structured_data={
                               'components_registered': len(degradation_manager.components),
                               'health_checks_active': len(health_monitor.health_checks)
                           })
        
        # Step 2: Collect articles
        with PerformanceProfiler.profile_operation("article_collection", logger):
            logger.info("Step 2: Collecting articles from all sources...",
                       pipeline_stage=PipelineStage.COLLECTION,
                       run_id=run_id)

            # Check if collection should be skipped due to degradation
            if degradation_manager.should_skip_operation("article_collection", "collection_system"):
                logger.warning("Skipping article collection due to system degradation",
                             pipeline_stage=PipelineStage.COLLECTION,
                             run_id=run_id,
                             structured_data={
                                 'degradation_level': degradation_manager.overall_degradation_level.value,
                                 'reason': 'graceful_degradation'
                             })
                # Continue with minimal fallback or skip to next step
                raw_articles = []
            else:
                try:
                    collector = MainCollector()
                    raw_articles = collector.collect_all_articles()

                    collection_stats = collector.get_stats()
                    logger.info(f"Collection completed: {collection_stats.total_articles_collected} articles",
                                pipeline_stage=PipelineStage.COLLECTION,
                                run_id=run_id,
                                structured_data={
                                    'articles_collected': collection_stats.total_articles_collected,
                                    'sources_attempted': getattr(collection_stats, 'sources_attempted', 0),
                                    'collection_errors': len(collection_stats.errors) if isinstance(collection_stats.errors, list) and collection_stats.errors else 0
                                })
                    
                    # Archive collected articles
                    ai_archiver.archive_collected_articles(raw_articles)
        
                    # Log source distribution for debugging
                    source_counts = {}
                    for article in raw_articles:
                        source_name = getattr(article, 'source', 'unknown')
                        source_counts[source_name] = source_counts.get(source_name, 0) + 1
        
                    logger.info("Source distribution after collection:",
                                pipeline_stage=PipelineStage.COLLECTION,
                                run_id=run_id,
                                structured_data={
                                    'source_counts': source_counts,
                                    'total_sources': len(source_counts),
                                    'top_sources': sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                                })

                    if collection_stats.total_articles_collected < 10:
                        logger.error(f"Insufficient articles collected: {collection_stats.total_articles_collected}",
                                    pipeline_stage=PipelineStage.COLLECTION,
                                    run_id=run_id,
                                    error_category=ErrorCategory.VALIDATION_ERROR,
                                    structured_data={
                                        'threshold': 10,
                                        'actual': collection_stats.total_articles_collected
                                    })
                        pipeline_tracker.track_pipeline_failure(run_id, ValueError("Insufficient articles"), PipelineStage.COLLECTION)
                        return False

                except Exception as e:
                    logger.error(f"Article collection failed: {e}",
                                pipeline_stage=PipelineStage.COLLECTION,
                                run_id=run_id,
                                error_category=ErrorCategory.API_ERROR,
                                structured_data={'error_details': str(e)})
                    pipeline_tracker.track_pipeline_failure(run_id, e, PipelineStage.COLLECTION)
                    return False

        # Collect collection metrics
        sources_config = Config.load_sources()
        sources = []
        for source_config in sources_config.get('tier1_sources', []) + sources_config.get('tier2_sources', []):
            from .models import NewsSource, SourceCategory, SourceTier
            try:
                category = SourceCategory(source_config['category'])
                tier = SourceTier.TIER1_RSS if source_config in sources_config.get('tier1_sources', []) else SourceTier.TIER2_SCRAPING
                source = NewsSource(
                    name=source_config['name'],
                    url=source_config['url'],
                    category=category,
                    tier=tier
                )
                sources.append(source)
            except Exception as e:
                logger.warning(f"Could not create source object for metrics: {e}")

        metrics_collector.collect_collection_metrics(sources, raw_articles)

        # Step 2.5: Content Enrichment with Full-Text Scraping
        with PerformanceProfiler.profile_operation("content_enrichment", logger):
            logger.info("Step 2.5: Enriching articles with full-text content...",
                       pipeline_stage=PipelineStage.PROCESSING,
                       run_id=run_id,
                       structured_data={'articles_to_enrich': len(raw_articles)})

            try:
                # Skip content enrichment if too many articles (to save time and avoid failures)
                if len(raw_articles) > 100:
                    logger.info(f"Skipping content enrichment for {len(raw_articles)} articles (too many)")
                    enriched_results = [(article, None) for article in raw_articles]
                    for article in raw_articles:
                        article.full_content = article.summary
                        article.content_quality_score = 0.5
                        article.extraction_method = "skipped_too_many"
                        article.word_count = len(article.summary.split())
                else:
                    # Enrich articles with full content using intelligent scraping
                    enriched_results = asyncio.run(enrich_articles_with_content(raw_articles))
                
                # Archive content extraction results for transparency
                ai_archiver.archive_content_extraction_results(enriched_results)
                
                # Update articles with enriched content
                for article, extraction_result in enriched_results:
                    if extraction_result.success and extraction_result.quality_score > 0.4:
                        article.full_content = extraction_result.full_content
                        article.content_quality_score = extraction_result.quality_score
                        article.extraction_method = extraction_result.extraction_method
                        article.word_count = extraction_result.word_count
                    else:
                        # Keep original summary as fallback
                        article.full_content = article.summary
                        article.content_quality_score = 0.3
                        article.extraction_method = "summary_fallback"
                        article.word_count = len(article.summary.split())
                
                enriched_articles = [article for article, _ in enriched_results]
                
                # Calculate enrichment statistics
                successful_extractions = sum(1 for _, result in enriched_results if result.success and result.quality_score > 0.4)
                avg_quality = sum(result.quality_score for _, result in enriched_results) / len(enriched_results) if enriched_results else 0
                avg_word_count = sum(result.word_count for _, result in enriched_results) / len(enriched_results) if enriched_results else 0
                
                logger.info("Content enrichment completed",
                           pipeline_stage=PipelineStage.PROCESSING,
                           run_id=run_id,
                           structured_data={
                               'original_articles': len(raw_articles),
                               'enriched_articles': len(enriched_articles),
                               'successful_extractions': successful_extractions,
                               'enrichment_success_rate': successful_extractions / len(raw_articles) if raw_articles else 0,
                               'avg_quality_score': avg_quality,
                               'avg_word_count': avg_word_count
                           })
                
                # Use enriched articles for further processing
                raw_articles = enriched_articles
                
            except Exception as e:
                logger.error(f"Content enrichment failed: {e}",
                            pipeline_stage=PipelineStage.PROCESSING,
                            run_id=run_id,
                            error_category=ErrorCategory.PARSING_ERROR,
                            structured_data={'error_details': str(e)})
                # Continue with original articles if enrichment fails
                logger.info("Continuing with original articles due to enrichment failure",
                           pipeline_stage=PipelineStage.PROCESSING,
                           run_id=run_id)

        # Step 2.6: Content Quality Validation
        with PerformanceProfiler.profile_operation("content_quality_validation", logger):
            logger.info("Step 2.6: Validating content quality...",
                       pipeline_stage=PipelineStage.PROCESSING,
                       run_id=run_id,
                       structured_data={'articles_to_validate': len(raw_articles)})

            try:
                # Validate article quality
                validation_results = content_quality_validator.validate_articles(raw_articles)

                # Filter to high-quality articles only
                high_quality_articles = [result.article for result in validation_results if result.is_valid]

                logger.info("Content quality validation completed",
                           pipeline_stage=PipelineStage.PROCESSING,
                           run_id=run_id,
                           structured_data={
                               'original_articles': len(raw_articles),
                               'high_quality_articles': len(high_quality_articles),
                               'filtered_articles': len(raw_articles) - len(high_quality_articles),
                               'quality_retention_rate': len(high_quality_articles) / len(raw_articles) if raw_articles else 0
                           })

                # Use only high-quality articles for further processing
                if len(high_quality_articles) < 5:
                    logger.warning("Low number of high-quality articles available",
                                 pipeline_stage=PipelineStage.PROCESSING,
                                 run_id=run_id,
                                 structured_data={
                                     'high_quality_count': len(high_quality_articles),
                                     'threshold': 5,
                                     'recommendation': 'Consider relaxing quality thresholds or expanding sources'
                                 })

                # Update raw_articles to only include high-quality ones
                raw_articles = high_quality_articles

            except Exception as e:
                logger.error(f"Content quality validation failed: {e}",
                            pipeline_stage=PipelineStage.PROCESSING,
                            run_id=run_id,
                            error_category=ErrorCategory.VALIDATION_ERROR,
                            structured_data={'error_details': str(e)})
                # Continue with original articles if validation fails
                logger.info("Continuing with original articles due to validation failure",
                           pipeline_stage=PipelineStage.PROCESSING,
                           run_id=run_id)

        # Step 3: Process articles (deduplication and scoring - NO CLUSTERING)
        with PerformanceProfiler.profile_operation("article_processing", logger):
            logger.info("Step 3: Processing articles (deduplication and scoring)...",
                       pipeline_stage=PipelineStage.PROCESSING,
                       run_id=run_id,
                       structured_data={'input_articles': len(raw_articles)})

            processing_start = time.time()
            try:
                processor = MainProcessor()
                # Only do deduplication and basic scoring, skip clustering
                deduplicated_articles = processor.deduplicator.deduplicate_articles(raw_articles)
                
                # Apply basic scoring to articles
                scored_articles = processor._score_articles_basic(deduplicated_articles)
                
                processing_time = time.time() - processing_start

                logger.info(f"Processing completed: {len(scored_articles)} articles processed (no clustering)",
                            pipeline_stage=PipelineStage.PROCESSING,
                            run_id=run_id,
                            performance_data={
                                'operation': 'article_processing',
                                'execution_time_seconds': processing_time,
                                'input_count': len(raw_articles),
                                'output_count': len(scored_articles)
                            },
                            structured_data={
                                'articles_processed': len(scored_articles),
                                'articles_after_deduplication': len(deduplicated_articles),
                                'duplicates_removed': len(raw_articles) - len(deduplicated_articles)
                            })

                # Log source distribution for debugging
                source_counts = {}
                for article in scored_articles:
                    source_name = getattr(article, 'source', 'unknown')
                    source_counts[source_name] = source_counts.get(source_name, 0) + 1

                logger.info("Source distribution in processed articles:",
                            pipeline_stage=PipelineStage.PROCESSING,
                            run_id=run_id,
                            structured_data={
                                'source_counts': source_counts,
                                'total_sources': len(source_counts),
                                'top_sources': sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                            })

                if len(scored_articles) < 10:
                    logger.error(f"Insufficient articles after processing: {len(scored_articles)}",
                                pipeline_stage=PipelineStage.PROCESSING,
                                run_id=run_id,
                                error_category=ErrorCategory.VALIDATION_ERROR,
                                structured_data={
                                    'threshold': 10,
                                    'actual': len(scored_articles)
                                })
                    pipeline_tracker.track_pipeline_failure(run_id, ValueError("Insufficient articles"), PipelineStage.PROCESSING)
                    return False

            except Exception as e:
                processing_time = time.time() - processing_start
                logger.error(f"Article processing failed: {e}",
                           pipeline_stage=PipelineStage.PROCESSING,
                           run_id=run_id,
                           error_category=ErrorCategory.PARSING_ERROR,
                           performance_data={
                               'operation': 'article_processing',
                               'execution_time_seconds': processing_time,
                               'failed': True
                           })
                pipeline_tracker.track_pipeline_failure(run_id, e, PipelineStage.PROCESSING)
                return False

        # Collect processing metrics (adapted for articles instead of clusters)
        metrics_collector.collect_processing_metrics(raw_articles, [], processing_time)
        
        # Step 4: Multi-Stage AI Analysis with Transparency
        with PerformanceProfiler.profile_operation("ai_analysis", logger):
            logger.info("Step 4: Running multi-stage AI analysis with full transparency...",
                       pipeline_stage=PipelineStage.AI_ANALYSIS,
                       run_id=run_id,
                       structured_data={
                           'target_stories': 4,
                           'articles_input': len(scored_articles),
                           'analysis_method': 'multi_stage_transparent'
                       })

            # Check if AI analysis should be skipped due to degradation
            if degradation_manager.should_skip_operation("ai_analysis", "ai_analyzer"):
                logger.warning("Skipping AI analysis due to system degradation",
                             pipeline_stage=PipelineStage.AI_ANALYSIS,
                             run_id=run_id,
                             structured_data={
                                 'degradation_level': degradation_manager.overall_degradation_level.value,
                                 'reason': 'graceful_degradation'
                             })
                # Use mock analysis as fallback - create mock articles
                analyses = create_mock_analyses_from_articles(scored_articles[:4])
            else:
                ai_start = time.time()
                try:
                    # Use simplified multi-stage analyzer with SINGLE API call
                    multi_stage_analyzer = SimplifiedMultiStageAnalyzer()
                    analyses = asyncio.run(multi_stage_analyzer.analyze_articles_single_call(scored_articles, target_stories=4))
                    ai_time = time.time() - ai_start

                    if len(analyses) < 3:
                        logger.error(f"Insufficient AI analyses: {len(analyses)}",
                                    pipeline_stage=PipelineStage.AI_ANALYSIS,
                                    run_id=run_id,
                                    error_category=ErrorCategory.VALIDATION_ERROR,
                                    structured_data={
                                        'threshold': 3,
                                        'actual': len(analyses)
                                    })
                        pipeline_tracker.track_pipeline_failure(run_id, ValueError("Insufficient AI analyses"), PipelineStage.AI_ANALYSIS)
                        return False

                    logger.info(f"AI analysis completed: {len(analyses)} stories selected",
                                pipeline_stage=PipelineStage.AI_ANALYSIS,
                                run_id=run_id,
                                performance_data={
                                    'operation': 'ai_analysis',
                                    'execution_time_seconds': ai_time,
                                    'stories_analyzed': len(analyses)
                                },
                                structured_data={
                                    'stories_selected': len(analyses),
                                    'analysis_time_seconds': ai_time
                                })

                    # Log sources in selected stories for debugging
                    selected_source_counts = {}
                    for analysis in analyses:
                        for source_url in analysis.sources:
                            # Extract domain from URL for grouping
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(source_url).netloc
                                if 'bbc' in domain.lower():
                                    domain = 'BBC'
                                selected_source_counts[domain] = selected_source_counts.get(domain, 0) + 1
                            except:
                                selected_source_counts['unknown'] = selected_source_counts.get('unknown', 0) + 1

                    logger.info("Source distribution in selected stories:",
                                pipeline_stage=PipelineStage.AI_ANALYSIS,
                                run_id=run_id,
                                structured_data={
                                    'selected_source_counts': selected_source_counts,
                                    'total_selected_sources': len(selected_source_counts),
                                    'top_selected_sources': sorted(selected_source_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                                })

                    # Collect AI metrics with simplified logging
                    # Rough estimates since we're doing single call
                    estimated_tokens = len(scored_articles) * 50 + len(analyses) * 200
                    estimated_cost = estimated_tokens * 0.00001  # Rough estimate
                    mock_mode = multi_stage_analyzer.mock_mode

                    logger.info(f"Simplified analysis completed - Estimated tokens: {estimated_tokens}, Cost: ~${estimated_cost:.4f}",
                               pipeline_stage=PipelineStage.AI_ANALYSIS,
                               run_id=run_id,
                               structured_data={
                                   'estimated_tokens': estimated_tokens,
                                   'estimated_cost': estimated_cost,
                                   'single_api_call': True,
                                   'mock_mode': mock_mode
                               })

                    metrics_collector.collect_ai_metrics(
                        analyses, ai_time, Config.AI_MODEL, mock_mode, estimated_tokens, estimated_cost
                    )

                except Exception as e:
                    ai_time = time.time() - ai_start
                    logger.error(f"AI analysis failed: {e}",
                               pipeline_stage=PipelineStage.AI_ANALYSIS,
                               run_id=run_id,
                               error_category=ErrorCategory.API_ERROR,
                               performance_data={
                                   'operation': 'ai_analysis',
                                   'execution_time_seconds': ai_time,
                                   'failed': True
                               },
                               structured_data={'error_details': str(e)})

                    # Fallback to mock analyses
                    logger.info("Falling back to mock analyses",
                               pipeline_stage=PipelineStage.AI_ANALYSIS,
                               run_id=run_id,
                               structured_data={'fallback_mode': True})

                    analyses = create_mock_analyses_from_articles(scored_articles[:4])
                    ai_time = time.time() - ai_start

                    # Collect metrics for fallback analysis
                    metrics_collector.collect_ai_metrics(
                        analyses, ai_time, "mock_fallback", True, 0, 0.0
                    )
        
        # Step 5: Generate newsletter
        with PerformanceProfiler.profile_operation("newsletter_generation", logger):
            logger.info("Step 5: Generating newsletter...",
                       pipeline_stage=PipelineStage.GENERATION,
                       run_id=run_id,
                       structured_data={'analyses_count': len(analyses)})

            # Check if newsletter generation should be skipped due to degradation
            if degradation_manager.should_skip_operation("newsletter_generation", "newsletter_generator"):
                logger.warning("Skipping newsletter generation due to system degradation",
                             pipeline_stage=PipelineStage.GENERATION,
                             run_id=run_id,
                             structured_data={
                                 'degradation_level': degradation_manager.overall_degradation_level.value,
                                 'reason': 'graceful_degradation'
                             })
                # Create minimal newsletter as fallback
                newsletter = Newsletter(
                    date=datetime.now(),
                    title=Config.NEWSLETTER_TITLE,
                    stories=analyses[:2] if analyses else [],  # Use first 2 stories
                    intro_text="Newsletter generated with limited functionality due to system constraints.",
                    footer_text="This newsletter was generated under degraded conditions."
                )
                html_content = f"<html><body><h1>{newsletter.title}</h1><p>System operating in degraded mode.</p></body></html>"
                file_path = None
            else:
                try:
                    generator = NewsletterGenerator()
                    newsletter = generator.generate_newsletter(analyses)
                    html_content = generator.generate_html(newsletter)

                    # Save newsletter (legacy format)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"newsletter_{timestamp}.html"
                    file_path = generator.save_html(html_content, filename)

                    logger.info(f"Newsletter saved to: {file_path}",
                               pipeline_stage=PipelineStage.GENERATION,
                               run_id=run_id,
                               structured_data={
                                   'file_path': str(file_path),
                                   'file_size_bytes': len(html_content) if html_content else 0,
                                   'stories_count': len(analyses)
                               })
                    
                    # Archive final newsletter
                    ai_archiver.archive_final_newsletter(html_content, analyses)

                except Exception as e:
                    logger.error(f"Newsletter generation failed: {e}",
                               pipeline_stage=PipelineStage.GENERATION,
                               run_id=run_id,
                               error_category=ErrorCategory.PARSING_ERROR,
                               structured_data={'error_details': str(e)})
                    pipeline_tracker.track_pipeline_failure(run_id, e, PipelineStage.GENERATION)
                    return False
        
        # Step 6: Multi-platform publishing
        with PerformanceProfiler.profile_operation("publishing", logger):
            logger.info("Step 6: Publishing newsletter...",
                       pipeline_stage=PipelineStage.PUBLISHING,
                       run_id=run_id)

            publishing_start = time.time()

            try:
                # GitHub Pages (automatic)
                github_publisher = GitHubPagesPublisher()
                github_url = github_publisher.publish_newsletter(newsletter, analyses)
                logger.info(f"✅ Published to GitHub Pages: {github_url}",
                           pipeline_stage=PipelineStage.PUBLISHING,
                           run_id=run_id,
                           structured_data={
                               'platform': 'github_pages',
                               'url': github_url,
                               'success': bool(github_url)
                           })

                publishing_time = time.time() - publishing_start

                logger.info("Publishing completed",
                           pipeline_stage=PipelineStage.PUBLISHING,
                           run_id=run_id,
                           performance_data={
                               'operation': 'publishing',
                               'execution_time_seconds': publishing_time
                           })

            except Exception as e:
                publishing_time = time.time() - publishing_start
                logger.error(f"Publishing failed: {e}",
                           pipeline_stage=PipelineStage.PUBLISHING,
                           run_id=run_id,
                           error_category=ErrorCategory.API_ERROR,
                           performance_data={
                               'operation': 'publishing',
                               'execution_time_seconds': publishing_time,
                               'failed': True
                           })
                pipeline_tracker.track_pipeline_failure(run_id, e, PipelineStage.PUBLISHING)
                return False

        publishing_summary = {
            "github_pages": github_url,
            "legacy_file": file_path
        }

        # Collect publishing metrics
        metrics_collector.collect_publishing_metrics(
            newsletter, github_url, 0, publishing_time, True
        )
        
        # Step 7: Send admin notification
        with PerformanceProfiler.profile_operation("notification", logger):
            logger.info("Step 7: Sending admin notification...",
                       pipeline_stage=PipelineStage.NOTIFICATION,
                       run_id=run_id)

            try:
                notifier = EmailNotifier()
                notification_sent = notifier.notify_newsletter_ready(newsletter, analyses, publishing_summary)

                if notification_sent:
                    logger.info("✅ Admin notification sent",
                               pipeline_stage=PipelineStage.NOTIFICATION,
                               run_id=run_id,
                               structured_data={'notification_type': 'email'})
                else:
                    logger.info("📧 Admin notification skipped (not configured)",
                               pipeline_stage=PipelineStage.NOTIFICATION,
                               run_id=run_id,
                               structured_data={'reason': 'not_configured'})

                publishing_summary["notification_sent"] = notification_sent

            except Exception as e:
                logger.error(f"Notification failed: {e}",
                           pipeline_stage=PipelineStage.NOTIFICATION,
                           run_id=run_id,
                           error_category=ErrorCategory.API_ERROR,
                           structured_data={'error_details': str(e)})
                # Don't fail the pipeline for notification errors
                publishing_summary["notification_sent"] = False

        # Update publishing metrics with notification count
        if notification_sent:
            # We need to update the existing publishing metrics with notification count
            pass  # This would require a database update method

        # Step 8: Generate summary report
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Get AI cost report
        cost_report = ai_cost_controller.get_cost_report()

        # Track pipeline success
        pipeline_tracker.track_pipeline_success(run_id, total_time)

        logger.info("=== Pipeline Summary ===",
                     pipeline_stage=PipelineStage.CLEANUP,
                     run_id=run_id,
                     performance_data={
                         'operation': 'pipeline_total',
                         'execution_time_seconds': total_time
                     },
                     structured_data={
                         'total_execution_time': total_time,
                         'articles_collected': collection_stats.total_articles_collected,
                         'articles_after_processing': len(scored_articles),  # Use actual scored articles count
                         'clusters_created': 0,  # No clusters in direct article analysis
                         'stories_selected': len(analyses),
                         'github_pages_url': publishing_summary['github_pages'],
                         'legacy_file': publishing_summary['legacy_file'],
                         'processing_success_rate': 1.0,  # Always successful in direct mode
                         'collection_errors': len(collection_stats.errors) if isinstance(collection_stats.errors, list) and collection_stats.errors else 0,
                         'processing_errors': 0,  # No processing errors in direct mode
                         'ai_costs': {
                             'daily_cost': cost_report['current_metrics']['daily_cost'],
                             'monthly_cost': cost_report['current_metrics']['monthly_cost'],
                             'daily_usage_percent': cost_report['budget_limits']['daily_usage_percent'],
                             'monthly_usage_percent': cost_report['budget_limits']['monthly_usage_percent'],
                             'budget_status': cost_report['status']
                         }
                     })

        # Log AI cost summary separately for better visibility
        logger.info("=== AI Cost Summary ===",
                     pipeline_stage=PipelineStage.CLEANUP,
                     run_id=run_id,
                     structured_data={
                         'daily_cost': cost_report['current_metrics']['daily_cost'],
                         'monthly_cost': cost_report['current_metrics']['monthly_cost'],
                         'daily_tokens': cost_report['current_metrics']['daily_tokens'],
                         'monthly_tokens': cost_report['current_metrics']['monthly_tokens'],
                         'daily_limit': cost_report['budget_limits']['daily_limit'],
                         'monthly_limit': cost_report['budget_limits']['monthly_limit'],
                         'daily_usage_percent': cost_report['budget_limits']['daily_usage_percent'],
                         'monthly_usage_percent': cost_report['budget_limits']['monthly_usage_percent'],
                         'budget_status': cost_report['status'],
                         'api_calls_today': cost_report['current_metrics']['daily_api_calls']
                     })

        # Step 9: Run cleanup (only if enabled and not in dry run mode)
        if Config.CLEANUP_ENABLED and not Config.DRY_RUN:
            with PerformanceProfiler.profile_operation("cleanup", logger):
                logger.info("Step 9: Running automatic cleanup...",
                            pipeline_stage=PipelineStage.CLEANUP,
                            run_id=run_id)

                try:
                    cleanup_manager = CleanupManager()
                    cleanup_result = cleanup_manager.run_full_cleanup()

                    logger.info("✅ Cleanup completed",
                                pipeline_stage=PipelineStage.CLEANUP,
                                run_id=run_id,
                                structured_data={
                                    'files_removed': cleanup_result.files_removed,
                                    'bytes_freed': cleanup_result.bytes_freed,
                                    'database_records_removed': cleanup_result.database_records_removed,
                                    'cleanup_errors': len(cleanup_result.errors)
                                })

                    if cleanup_result.errors:
                        logger.warning("Cleanup completed with errors",
                                     pipeline_stage=PipelineStage.CLEANUP,
                                     run_id=run_id,
                                     structured_data={'cleanup_errors': cleanup_result.errors})

                except Exception as e:
                    logger.error(f"Cleanup failed: {e}",
                                pipeline_stage=PipelineStage.CLEANUP,
                                run_id=run_id,
                                error_category=ErrorCategory.UNKNOWN_ERROR,
                                structured_data={'error_details': str(e)})
                    # Don't fail the pipeline for cleanup errors
        elif Config.DRY_RUN:
            logger.info("🧹 Cleanup skipped (dry run mode)",
                        pipeline_stage=PipelineStage.CLEANUP,
                        run_id=run_id)
        else:
            logger.info("🧹 Cleanup disabled",
                        pipeline_stage=PipelineStage.CLEANUP,
                        run_id=run_id)

        logger.info("=== Pipeline Completed Successfully ===",
                   pipeline_stage=PipelineStage.CLEANUP,
                   run_id=run_id,
                   structured_data={
                       'final_status': 'success',
                       'run_id': run_id
                   })

        # Step 10: Generate Enhanced Multi-Stage Dashboard
        with PerformanceProfiler.profile_operation("dashboard_generation", logger):
            logger.info("Step 10: Generating enhanced multi-stage dashboard...",
                       pipeline_stage=PipelineStage.CLEANUP,
                       run_id=run_id)
            
            try:
                dashboard_generator = EnhancedMultiStageDashboard()
                dashboard_path = dashboard_generator.generate_dashboard_for_date(current_date)
                
                logger.info(f"✅ Enhanced dashboard generated: {dashboard_path}",
                           pipeline_stage=PipelineStage.CLEANUP,
                           run_id=run_id,
                           structured_data={
                               'dashboard_path': str(dashboard_path),
                               'dashboard_type': 'enhanced_multi_stage'
                           })
                           
            except Exception as e:
                logger.error(f"Dashboard generation failed: {e}",
                           pipeline_stage=PipelineStage.CLEANUP,
                           run_id=run_id,
                           error_category=ErrorCategory.PARSING_ERROR,
                           structured_data={'error_details': str(e)})
                # Don't fail the pipeline for dashboard errors

        # Create archive run summary
        ai_archiver.create_run_summary()
        
        # End pipeline run successfully
        metrics_collector.end_pipeline_run(success=True)
        return True

    except Exception as e:
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds() if 'start_time' in locals() else 0

        # Track pipeline failure
        pipeline_tracker.track_pipeline_failure(run_id, e, PipelineStage.CLEANUP)

        logger.error(f"Pipeline failed with error: {e}",
                   pipeline_stage=PipelineStage.CLEANUP,
                   run_id=run_id if 'run_id' in locals() else None,
                   error_category=ErrorCategory.UNKNOWN_ERROR,
                   performance_data={
                       'operation': 'pipeline_total',
                       'execution_time_seconds': total_time,
                       'failed': True
                   },
                   structured_data={
                       'error_type': type(e).__name__,
                       'error_message': str(e),
                       'final_status': 'failed'
                   })

        logger.exception("Full error traceback:",
                        pipeline_stage=PipelineStage.CLEANUP,
                        run_id=run_id if 'run_id' in locals() else None,
                        error_category=ErrorCategory.UNKNOWN_ERROR)

        # End pipeline run with failure
        metrics_collector.end_pipeline_run(success=False, errors=[str(e)])
        return False

    finally:
        # Ensure metrics collector is properly closed
        metrics_collector.close()

        # Stop resilience monitoring
        try:
            health_monitor.stop_monitoring()
            logger.info("Health monitoring stopped",
                       pipeline_stage=PipelineStage.CLEANUP,
                       run_id=run_id if 'run_id' in locals() else None,
                       structured_data={'monitoring_status': 'stopped'})
        except Exception as e:
            logger.warning(f"Error stopping health monitoring: {e}",
                          pipeline_stage=PipelineStage.CLEANUP,
                          run_id=run_id if 'run_id' in locals() else None)

        # Log final cleanup
        logger.info("Pipeline cleanup completed",
                   pipeline_stage=PipelineStage.CLEANUP,
                   run_id=run_id if 'run_id' in locals() else None,
                   structured_data={'cleanup_status': 'completed'})

def create_mock_analyses(clusters):
    """Create mock AI analyses for testing/fallback."""
    from .models import AIAnalysis
    
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

def create_mock_analyses_from_articles(articles):
    """Create mock AI analyses for testing/fallback from individual articles."""
    from .models import AIAnalysis, ContentType
    
    mock_analyses = []
    
    for i, article in enumerate(articles[:4]):
        # Generate basic analysis based on article content
        content_lower = f"{article.title} {article.summary}".lower()
        
        # Determine content type based on keywords
        if any(keyword in content_lower for keyword in ['breaking', 'urgent', 'crisis', 'emergency']):
            content_type = ContentType.BREAKING_NEWS
        elif any(keyword in content_lower for keyword in ['trend', 'emerging', 'shift', 'pattern']):
            content_type = ContentType.TREND
        else:
            content_type = ContentType.ANALYSIS
        
        # Basic impact score calculation
        impact_score = 5  # Base score
        if any(keyword in content_lower for keyword in ['china', 'russia', 'taiwan', 'ukraine']):
            impact_score += 2
        if article.source_category.value in ['think_tank', 'analysis']:
            impact_score += 1
        impact_score = min(8, max(4, impact_score))
        
        analysis = AIAnalysis(
            story_title=article.title[:60],
            why_important=f"This story represents a significant development in {article.source_category.value} geopolitics with potential implications for international relations and strategic decision-making.",
            what_overlooked="Mainstream media coverage may be missing the broader strategic implications and second-order effects of this development.",
            prediction="This situation will likely evolve over the coming weeks with potential impacts on regional stability and international partnerships.",
            impact_score=impact_score,
            content_type=content_type,
            urgency_score=5,
            scope_score=5,
            novelty_score=5,
            credibility_score=6 if article.source_category.value in ['think_tank', 'analysis'] else 5,
            impact_dimension_score=impact_score,
            sources=[article.url],
            confidence=0.7
        )
        
        mock_analyses.append(analysis)
    
    return mock_analyses

def main():
    """Main entry point for command-line execution."""
    try:
        logger.info("Starting newsletter pipeline from command line",
                   pipeline_stage=PipelineStage.INITIALIZATION,
                   structured_data={'execution_mode': 'command_line'})

        success = run_complete_pipeline()

        if success:
            logger.info("Newsletter pipeline completed successfully from command line",
                       pipeline_stage=PipelineStage.CLEANUP,
                       structured_data={'exit_code': 0})
            print("✅ Newsletter pipeline completed successfully!")
            sys.exit(0)
        else:
            logger.error("Newsletter pipeline failed from command line",
                        pipeline_stage=PipelineStage.CLEANUP,
                        error_category=ErrorCategory.UNKNOWN_ERROR,
                        structured_data={'exit_code': 1})
            print("❌ Newsletter pipeline failed!")
            sys.exit(1)

    except Exception as e:
        logger.critical(f"Critical error in main execution: {e}",
                       pipeline_stage=PipelineStage.CLEANUP,
                       error_category=ErrorCategory.UNKNOWN_ERROR,
                       structured_data={'execution_mode': 'command_line'})
        print(f"❌ Critical error: {e}")
        sys.exit(1)

    finally:
        # Shutdown metrics integration
        from .logging_system import shutdown_metrics_integration
        shutdown_metrics_integration()

if __name__ == "__main__":
    main()
