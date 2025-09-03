"""
AI Data Archiver - Comprehensive data persistence for AI analysis tracking.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from ..models import Article, ArticleCluster, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)


class AIDataArchiver:
    """Archives all data flowing through the AI analysis pipeline."""
    
    def __init__(self):
        self.archive_base = Path(getattr(Config, 'AI_ARCHIVE_PATH', 'ai_archive'))
        self.current_run_id = None
        self.current_run_path = None
        self.enabled = getattr(Config, 'AI_ARCHIVE_ENABLED', True)
        
    def start_new_run(self) -> str:
        """Initialize a new archive run."""
        print(f"🗄️ AI Archiver: start_new_run called, enabled={self.enabled}")
        if not self.enabled:
            logger.info("AI archiving is disabled")
            print("🗄️ AI Archiver: AI archiving is disabled")
            return "disabled"
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_folder = datetime.now().strftime("%Y-%m-%d")
        
        self.current_run_id = f"run_{timestamp}"
        self.current_run_path = self.archive_base / date_folder / self.current_run_id
        self.current_run_path.mkdir(parents=True, exist_ok=True)
        
        # Create metadata
        metadata = {
            "run_id": self.current_run_id,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "ai_provider": Config.AI_PROVIDER,
                "ai_model": Config.AI_MODEL,
                "ai_max_tokens": Config.AI_MAX_TOKENS,
                "dry_run": Config.DRY_RUN
            },
            "environment": {
                "github_action": os.getenv("GITHUB_ACTION"),
                "github_run_id": os.getenv("GITHUB_RUN_ID"),
                "github_sha": os.getenv("GITHUB_SHA"),
                "github_workflow": os.getenv("GITHUB_WORKFLOW"),
                "github_event_name": os.getenv("GITHUB_EVENT_NAME")
            }
        }
        
        self._save_json("metadata.json", metadata)
        logger.info(f"Archive run started: {self.current_run_id}")
        print(f"🗄️ AI Archiver: Archive run started: {self.current_run_id}")
        return self.current_run_id
    
    def archive_collected_articles(self, articles: List[Article]):
        """Archive all collected articles."""
        print(f"🗄️ AI Archiver: archive_collected_articles called with {len(articles)} articles, enabled={self.enabled}, run_path={self.current_run_path}")
        if not self.enabled or not self.current_run_path:
            print("🗄️ AI Archiver: Skipping article archiving - disabled or no run path")
            return
            
        articles_data = []
        for article in articles:
            articles_data.append({
                "source": article.source,
                "source_category": article.source_category.value if hasattr(article.source_category, 'value') else str(article.source_category),
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "published_date": article.published_date.isoformat() if article.published_date else None,
                "author": article.author,
                "relevance_score": getattr(article, 'relevance_score', None)
            })
        
        self._save_json("collected_articles.json", {
            "total_articles": len(articles),
            "timestamp": datetime.now().isoformat(),
            "articles": articles_data
        })
        
        # Create source distribution summary
        source_dist = {}
        for article in articles:
            source = article.source
            if source not in source_dist:
                source_dist[source] = 0
            source_dist[source] += 1
        
        self._save_json("source_distribution.json", source_dist)
        logger.info(f"Archived {len(articles)} collected articles")
        print(f"🗄️ AI Archiver: Archived {len(articles)} collected articles")
    
    def archive_article(self, article: Article, article_index: int):
        """Archive an individual article before AI analysis."""
        if not self.enabled or not self.current_run_path:
            return
            
        article_data = {
            "article_index": article_index,
            "title": article.title,
            "source": article.source,
            "source_category": article.source_category.value if hasattr(article.source_category, 'value') else str(article.source_category),
            "url": article.url,
            "summary": article.summary[:500] if article.summary else "",
            "published_date": article.published_date.isoformat() if article.published_date else None,
            "author": article.author,
            "relevance_score": getattr(article, 'relevance_score', None)
        }
        
        # Save individual article data
        article_filename = f"candidate_article_{article_index:02d}.json"
        self._save_json(article_filename, article_data)
    
    def archive_cluster(self, cluster: ArticleCluster, cluster_index: int):
        """Archive a cluster before AI analysis."""
        if not self.enabled or not self.current_run_path:
            return
            
        cluster_data = {
            "cluster_index": cluster_index,
            "cluster_score": getattr(cluster, 'cluster_score', 0),
            "main_article": {
                "title": cluster.main_article.title,
                "source": cluster.main_article.source,
                "url": cluster.main_article.url,
                "summary": cluster.main_article.summary[:500] if cluster.main_article.summary else ""
            },
            "articles_count": len(cluster.articles),
            "articles": [
                {
                    "title": art.title,
                    "source": art.source,
                    "url": art.url
                }
                for art in cluster.articles[:10]  # First 10 articles
            ]
        }
        
        clusters_dir = self.current_run_path / "clusters"
        clusters_dir.mkdir(exist_ok=True)
        
        self._save_json(f"clusters/cluster_{cluster_index:03d}.json", cluster_data)
        logger.debug(f"Archived cluster {cluster_index}")
    
    def archive_ai_request(self, prompt: str, articles_summary: str, 
                          cluster_index: int, main_article_title: str) -> str:
        """Archive what's being sent to AI."""
        if not self.enabled or not self.current_run_path:
            return ""
            
        request_data = {
            "cluster_index": cluster_index,
            "timestamp": datetime.now().isoformat(),
            "main_article_title": main_article_title,
            "prompt_template": prompt[:500] if prompt else "",  # First 500 chars of template
            "articles_summary": articles_summary,
            "full_prompt": prompt,
            "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest() if prompt else "",
            "prompt_length": len(prompt) if prompt else 0,
            "estimated_tokens": int(len(prompt.split()) * 1.3) if prompt else 0
        }
        
        requests_dir = self.current_run_path / "ai_requests"
        requests_dir.mkdir(exist_ok=True)
        
        filename = f"ai_requests/request_{cluster_index:03d}.json"
        self._save_json(filename, request_data)
        
        logger.info(f"Archived AI request for cluster {cluster_index} - {len(prompt) if prompt else 0} chars")
        return filename
    
    def archive_ai_response(self, response_text: str, analysis: Optional[AIAnalysis], 
                           cluster_index: int, cost: float, tokens: int):
        """Archive AI response."""
        if not self.enabled or not self.current_run_path:
            return
            
        response_data = {
            "cluster_index": cluster_index,
            "timestamp": datetime.now().isoformat(),
            "raw_response": response_text,
            "response_length": len(response_text) if response_text else 0,
            "tokens_used": tokens,
            "cost": cost,
            "parsed_analysis": None
        }
        
        if analysis:
            response_data["parsed_analysis"] = {
                "story_title": analysis.story_title,
                "content_type": analysis.content_type.value if hasattr(analysis.content_type, 'value') else str(analysis.content_type),
                "why_important": analysis.why_important,
                "what_overlooked": analysis.what_overlooked,
                "prediction": analysis.prediction,
                "impact_score": analysis.impact_score,
                "urgency_score": getattr(analysis, 'urgency_score', None),
                "scope_score": getattr(analysis, 'scope_score', None),
                "novelty_score": getattr(analysis, 'novelty_score', None),
                "credibility_score": getattr(analysis, 'credibility_score', None),
                "confidence": analysis.confidence
            }
        
        responses_dir = self.current_run_path / "ai_responses"
        responses_dir.mkdir(exist_ok=True)
        
        self._save_json(f"ai_responses/response_{cluster_index:03d}.json", response_data)
        logger.info(f"Archived AI response for cluster {cluster_index}")
    
    def archive_final_newsletter(self, newsletter_html: str, analyses: List[AIAnalysis]):
        """Archive the final newsletter."""
        if not self.enabled or not self.current_run_path:
            return
            
        newsletter_data = {
            "timestamp": datetime.now().isoformat(),
            "stories_count": len(analyses),
            "stories": [
                {
                    "title": analysis.story_title,
                    "content_type": analysis.content_type.value if hasattr(analysis.content_type, 'value') else str(analysis.content_type),
                    "impact_score": analysis.impact_score,
                    "sources_count": len(analysis.sources) if analysis.sources else 0
                }
                for analysis in analyses
            ],
            "html_length": len(newsletter_html) if newsletter_html else 0
        }
        
        self._save_json("final_newsletter.json", newsletter_data)
        
        # Also save HTML
        if newsletter_html:
            html_path = self.current_run_path / "final_newsletter.html"
            html_path.write_text(newsletter_html)
        
        logger.info("Archived final newsletter")
    
    def create_run_summary(self) -> Dict:
        """Create a summary of the entire run."""
        if not self.enabled or not self.current_run_path:
            return {}
            
        summary = {
            "run_id": self.current_run_id,
            "timestamp": datetime.now().isoformat(),
            "files_created": [],
            "statistics": {}
        }
        
        # List all created files
        for file_path in self.current_run_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(self.current_run_path)
                summary["files_created"].append({
                    "path": str(relative_path),
                    "size_bytes": file_path.stat().st_size
                })
        
        # Calculate statistics
        collected_file = self.current_run_path / "collected_articles.json"
        if collected_file.exists():
            with open(collected_file) as f:
                data = json.load(f)
                summary["statistics"]["total_articles_collected"] = data.get("total_articles", 0)
        
        clusters_dir = self.current_run_path / "clusters"
        if clusters_dir.exists():
            summary["statistics"]["total_clusters"] = len(list(clusters_dir.glob("*.json")))
        
        ai_requests_dir = self.current_run_path / "ai_requests"
        if ai_requests_dir.exists():
            summary["statistics"]["ai_requests_made"] = len(list(ai_requests_dir.glob("*.json")))
            
            # Calculate total cost
            total_cost = 0
            responses_dir = self.current_run_path / "ai_responses"
            if responses_dir.exists():
                for response_file in responses_dir.glob("*.json"):
                    with open(response_file) as f:
                        response_data = json.load(f)
                        total_cost += response_data.get("cost", 0)
            summary["statistics"]["total_ai_cost"] = total_cost
        
        self._save_json("run_summary.json", summary)
        logger.info(f"Created run summary: {len(summary['files_created'])} files, ${summary['statistics'].get('total_ai_cost', 0):.4f} cost")
        
        return summary
    
    def _save_json(self, filename: str, data: Any):
        """Save data as JSON file."""
        if not self.current_run_path:
            return
            
        file_path = self.current_run_path / filename
        file_path.parent.mkdir(exist_ok=True, parents=True)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def cleanup_old_archives(self, days_to_keep: int = 30):
        """Clean up old archive folders."""
        if not self.enabled:
            return
            
        import shutil
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for date_folder in self.archive_base.iterdir():
            if date_folder.is_dir():
                try:
                    folder_date = datetime.strptime(date_folder.name, "%Y-%m-%d")
                    if folder_date < cutoff_date:
                        shutil.rmtree(date_folder)
                        logger.info(f"Deleted old archive: {date_folder.name}")
                except ValueError:
                    # Not a date folder, skip
                    continue

    def archive_analysis_stage(self, stage: str, input_data: List[Dict], output_data: List[Dict], 
                              reasoning: str, cost: float, tokens: int):
        """Archive a multi-stage analysis stage with complete transparency."""
        if not self.enabled or not self.current_run_path:
            return
            
        stage_data = {
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "input_count": len(input_data),
            "output_count": len(output_data),
            "reasoning": reasoning,
            "cost": cost,
            "tokens_used": tokens,
            "input_data": input_data[:10],  # Limit size, store first 10 for review
            "output_data": output_data,
            "statistics": {
                "input_articles": len(input_data),
                "output_articles": len(output_data),
                "advancement_rate": len(output_data) / len(input_data) if input_data else 0,
                "average_score": sum(item.get('score', 0) for item in output_data) / len(output_data) if output_data else 0
            }
        }
        
        # Save stage analysis
        stage_filename = f"stage_{stage}.json"
        self._save_json(stage_filename, stage_data)
        
        print(f"🗄️ AI Archiver: Archived {stage} stage - {len(input_data)} → {len(output_data)} articles")
        logger.info(f"Archived analysis stage: {stage}")

    def archive_content_extraction_results(self, extraction_results: List[Dict]):
        """Archive content extraction results for transparency."""
        if not self.enabled or not self.current_run_path:
            return
            
        extraction_data = {
            "extraction_timestamp": datetime.now().isoformat(),
            "total_articles": len(extraction_results),
            "extraction_summary": {
                "successful_extractions": sum(1 for r in extraction_results if r.get('success', False)),
                "fallback_used": sum(1 for r in extraction_results if r.get('extraction_method', '').endswith('fallback')),
                "average_word_count": sum(r.get('word_count', 0) for r in extraction_results) / len(extraction_results) if extraction_results else 0,
                "average_quality_score": sum(r.get('quality_score', 0) for r in extraction_results) / len(extraction_results) if extraction_results else 0
            },
            "detailed_results": extraction_results[:20]  # Store first 20 for detailed review
        }
        
        self._save_json("content_extraction_results.json", extraction_data)
        
        print(f"🗄️ AI Archiver: Archived content extraction for {len(extraction_results)} articles")
        logger.info(f"Archived content extraction results")

    def archive_pipeline_transparency(self, pipeline_stages: List[Dict], total_time: float, 
                                    total_cost: float, total_tokens: int):
        """Archive complete pipeline transparency data."""
        if not self.enabled or not self.current_run_path:
            return
            
        transparency_data = {
            "pipeline_completion": datetime.now().isoformat(),
            "total_execution_time": total_time,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "stage_breakdown": pipeline_stages,
            "pipeline_summary": {
                "stages_completed": len(pipeline_stages),
                "total_articles_processed": sum(stage.get('input_count', 0) for stage in pipeline_stages),
                "final_stories_selected": pipeline_stages[-1].get('output_count', 0) if pipeline_stages else 0,
                "overall_advancement_rate": pipeline_stages[-1].get('output_count', 0) / pipeline_stages[0].get('input_count', 1) if pipeline_stages else 0,
                "cost_per_story": total_cost / pipeline_stages[-1].get('output_count', 1) if pipeline_stages and pipeline_stages[-1].get('output_count', 0) > 0 else 0
            },
            "decision_audit_trail": [
                {
                    "stage": stage.get('stage', 'unknown'),
                    "decision_reasoning": stage.get('reasoning', ''),
                    "confidence": stage.get('confidence', 0),
                    "articles_advanced": stage.get('output_count', 0)
                } for stage in pipeline_stages
            ]
        }
        
        self._save_json("pipeline_transparency.json", transparency_data)
        
        print(f"🗄️ AI Archiver: Archived complete pipeline transparency data")
        logger.info(f"Archived pipeline transparency: {len(pipeline_stages)} stages, ${total_cost:.4f} total cost")

    def get_stage_analysis_data(self) -> Optional[Dict]:
        """Retrieve archived stage analysis data for dashboard visualization."""
        if not self.enabled or not self.current_run_path:
            return None
            
        try:
            transparency_file = self.current_run_path / "pipeline_transparency.json"
            if transparency_file.exists():
                with open(transparency_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to retrieve stage analysis data: {e}")
        
        return None


# Global instance
ai_archiver = AIDataArchiver()