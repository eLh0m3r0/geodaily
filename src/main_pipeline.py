#!/usr/bin/env python3
"""
Main pipeline for the Geopolitical Daily newsletter.
Orchestrates the complete workflow from data collection to publishing.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from .collectors.main_collector import MainCollector
from .processors.main_processor import MainProcessor
from .ai.claude_analyzer import ClaudeAnalyzer
from .newsletter.generator import NewsletterGenerator
from .publishers.github_pages_publisher import GitHubPagesPublisher
from .publishers.substack_exporter import SubstackExporter
from .notifications.email_notifier import EmailNotifier
from .metrics.collector import MetricsCollector
from .config import Config
from .logging_system import (
    setup_structured_logging, get_metrics_aware_logger,
    PipelineStage, ErrorCategory, PerformanceProfiler,
    PipelineTracker, error_handler, retry_on_error
)
from .cleanup import CleanupManager

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

    try:
        # Step 0: Check for duplicate newsletter (same date)
        current_date = datetime.now().date()
        from pathlib import Path
        docs_dir = Path("docs")
        newsletter_filename = f"newsletter-{current_date.strftime('%Y-%m-%d')}.html"
        newsletter_path = docs_dir / "newsletters" / newsletter_filename

        if newsletter_path.exists():
            logger.warning(f"Newsletter for {current_date.strftime('%Y-%m-%d')} already exists. Skipping pipeline execution to prevent duplicates.",
                          pipeline_stage=PipelineStage.INITIALIZATION,
                          run_id=run_id,
                          structured_data={
                              'existing_file': str(newsletter_path),
                              'reason': 'duplicate_prevention'
                          })
            pipeline_tracker.track_pipeline_success(run_id, 0)  # Mark as successful with 0 execution time
            return True  # Return True since this is expected behavior

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
        
        # Step 2: Collect articles
        with PerformanceProfiler.profile_operation("article_collection", logger):
            logger.info("Step 2: Collecting articles from all sources...",
                       pipeline_stage=PipelineStage.COLLECTION,
                       run_id=run_id)

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
        
        # Step 3: Process articles (deduplication, clustering, scoring)
        with PerformanceProfiler.profile_operation("article_processing", logger):
            logger.info("Step 3: Processing articles...",
                       pipeline_stage=PipelineStage.PROCESSING,
                       run_id=run_id,
                       structured_data={'input_articles': len(raw_articles)})

            processing_start = time.time()
            try:
                processor = MainProcessor()
                clusters = processor.process_articles(raw_articles)
                processing_time = time.time() - processing_start

                processing_stats = processor.get_stats()
                logger.info(f"Processing completed: {len(clusters)} clusters created",
                           pipeline_stage=PipelineStage.PROCESSING,
                           run_id=run_id,
                           performance_data={
                               'operation': 'article_processing',
                               'execution_time_seconds': processing_time,
                               'input_count': len(raw_articles),
                               'output_count': len(clusters)
                           },
                           structured_data={
                               'clusters_created': len(clusters),
                               'articles_after_deduplication': processing_stats.articles_after_deduplication,
                               'duplicates_removed': len(raw_articles) - processing_stats.articles_after_deduplication
                           })

                if len(clusters) < 5:
                    logger.error(f"Insufficient clusters created: {len(clusters)}",
                               pipeline_stage=PipelineStage.PROCESSING,
                               run_id=run_id,
                               error_category=ErrorCategory.VALIDATION_ERROR,
                               structured_data={
                                   'threshold': 5,
                                   'actual': len(clusters)
                               })
                    pipeline_tracker.track_pipeline_failure(run_id, ValueError("Insufficient clusters"), PipelineStage.PROCESSING)
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

        # Collect processing metrics
        metrics_collector.collect_processing_metrics(raw_articles, clusters, processing_time)
        
        # Step 4: AI Analysis
        with PerformanceProfiler.profile_operation("ai_analysis", logger):
            logger.info("Step 4: Running AI analysis...",
                       pipeline_stage=PipelineStage.AI_ANALYSIS,
                       run_id=run_id,
                       structured_data={
                           'target_stories': 4,
                           'clusters_input': len(clusters)
                       })

            ai_start = time.time()
            try:
                analyzer = ClaudeAnalyzer()
                analyses = analyzer.analyze_clusters(clusters, target_stories=4)
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

                # Collect AI metrics with enhanced logging
                tokens_used = 0
                cost = 0.0
                mock_mode = analyzer.mock_mode

                if Config.DRY_RUN and hasattr(analyzer, 'get_simulation_stats'):
                    sim_stats = analyzer.get_simulation_stats()
                    tokens_used = sim_stats['simulated_tokens_used']
                    cost = sim_stats['simulated_cost']
                    logger.info(f"DRY RUN - Simulated tokens: {tokens_used}, Cost: ${cost:.4f}",
                               pipeline_stage=PipelineStage.AI_ANALYSIS,
                               run_id=run_id,
                               structured_data={
                                   'simulated_tokens': tokens_used,
                                   'simulated_cost': cost
                               })

                metrics_collector.collect_ai_metrics(
                    analyses, ai_time, Config.AI_MODEL, mock_mode, tokens_used, cost
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

                analyses = create_mock_analyses(clusters[:4])
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

                # Substack export (for manual publishing)
                substack_exporter = SubstackExporter()
                substack_files = substack_exporter.save_substack_files(newsletter, analyses)
                logger.info(f"✅ Substack exports ready: {substack_files['markdown_file']}",
                           pipeline_stage=PipelineStage.PUBLISHING,
                           run_id=run_id,
                           structured_data={
                               'platform': 'substack',
                               'markdown_file': substack_files.get('markdown_file'),
                               'html_file': substack_files.get('html_file')
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
            "substack_exports": substack_files,
            "legacy_file": file_path
        }

        # Collect publishing metrics
        substack_file_list = [substack_files.get('markdown_file'), substack_files.get('html_file')]
        substack_file_list = [f for f in substack_file_list if f]  # Filter out None values

        metrics_collector.collect_publishing_metrics(
            newsletter, github_url, substack_file_list, 0, publishing_time, True
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
                        'articles_after_processing': processing_stats.articles_after_deduplication,
                        'clusters_created': len(clusters),
                        'stories_selected': len(analyses),
                        'github_pages_url': publishing_summary['github_pages'],
                        'substack_markdown': publishing_summary['substack_exports']['markdown_file'],
                        'legacy_file': publishing_summary['legacy_file'],
                        'processing_success_rate': processing_stats.success_rate,
                        'collection_errors': len(collection_stats.errors) if isinstance(collection_stats.errors, list) and collection_stats.errors else 0,
                        'processing_errors': len(processing_stats.errors) if isinstance(processing_stats.errors, list) and processing_stats.errors else 0
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
