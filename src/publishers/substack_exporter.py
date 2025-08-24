"""
Substack-optimized export formatter.
"""

from datetime import datetime
from typing import List
from pathlib import Path

from ..models import Newsletter, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

class SubstackExporter:
    """Exports newsletter content in Substack-friendly formats."""
    
    def __init__(self):
        """Initialize Substack exporter."""
        logger.info("Substack exporter initialized")
    
    def export_markdown(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> str:
        """
        Export newsletter as Substack-ready markdown.
        
        Args:
            newsletter: Newsletter data
            analyses: AI analysis results
            
        Returns:
            Markdown content ready for copy-paste to Substack
        """
        
        # Header
        intro_text = newsletter.intro_text or "Today's edition focuses on underreported geopolitical developments with significant strategic implications."
        
        markdown = f"""# {newsletter.title}
*{newsletter.date.strftime('%B %d, %Y')}*

{intro_text}

---

"""
        
        # Stories
        for i, analysis in enumerate(analyses, 1):
            markdown += f"""## {i}. {analysis.story_title}

**Impact Score: {analysis.impact_score}/10** | **Confidence: {int(analysis.confidence * 100)}%**

### Why This Matters
{analysis.why_important}

### What Others Are Missing
{analysis.what_overlooked}

### What to Watch
{analysis.prediction}

**Sources:** {', '.join([self._format_source_link(url) for url in analysis.sources[:3]])}

---

"""
        
        # Footer
        footer_text = newsletter.footer_text or 'This newsletter is generated using AI analysis of geopolitical news sources.'
        
        markdown += f"""
*{footer_text}*

Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}
"""
        
        return markdown
    
    def export_html(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> str:
        """
        Export newsletter as clean HTML for Substack.
        
        Args:
            newsletter: Newsletter data
            analyses: AI analysis results
            
        Returns:
            Clean HTML content for Substack
        """
        
        # Header with Substack-friendly styling
        intro_text = newsletter.intro_text or "Today's edition focuses on underreported geopolitical developments with significant strategic implications."
        
        html = f"""<h1>{newsletter.title}</h1>
<p><em>{newsletter.date.strftime('%B %d, %Y')}</em></p>

<p>{intro_text}</p>

<hr>

"""
        
        # Stories with Substack-optimized formatting
        for i, analysis in enumerate(analyses, 1):
            impact_emoji = self._get_impact_emoji(analysis.impact_score)
            
            html += f"""<h2>{i}. {analysis.story_title}</h2>

<p><strong>Impact Score: {impact_emoji} {analysis.impact_score}/10</strong> | <strong>Confidence: {int(analysis.confidence * 100)}%</strong></p>

<h3>🎯 Why This Matters</h3>
<p>{analysis.why_important}</p>

<h3>👁️ What Others Are Missing</h3>
<p>{analysis.what_overlooked}</p>

<h3>🔮 What to Watch</h3>
<p>{analysis.prediction}</p>

<p><strong>Sources:</strong> {', '.join([f'<a href="{url}">{self._extract_domain(url)}</a>' for url in analysis.sources[:3]])}</p>

<hr>

"""
        
        # Footer
        footer_text = newsletter.footer_text or 'This newsletter is generated using AI analysis of geopolitical news sources.'
        
        html += f"""<p><em>{footer_text}</em></p>

<p><small>Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}</small></p>"""
        
        return html
    
    def save_substack_files(self, newsletter: Newsletter, analyses: List[AIAnalysis], output_dir: str = "substack_exports") -> dict:
        """
        Save both markdown and HTML versions for Substack.
        
        Args:
            newsletter: Newsletter data
            analyses: AI analysis results
            output_dir: Directory to save exports
            
        Returns:
            Dictionary with file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        date_str = newsletter.date.strftime('%Y-%m-%d')
        
        # Save markdown version
        markdown_content = self.export_markdown(newsletter, analyses)
        markdown_file = output_path / f"substack-{date_str}.md"
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Save HTML version
        html_content = self.export_html(newsletter, analyses)
        html_file = output_path / f"substack-{date_str}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Save publishing instructions
        instructions = self._generate_publishing_instructions(newsletter, analyses)
        instructions_file = output_path / f"instructions-{date_str}.txt"
        with open(instructions_file, 'w', encoding='utf-8') as f:
            f.write(instructions)
        
        result = {
            "markdown_file": str(markdown_file),
            "html_file": str(html_file),
            "instructions_file": str(instructions_file),
            "estimated_reading_time": self._estimate_reading_time(markdown_content)
        }
        
        logger.info(f"Substack exports saved: {result}")
        return result
    
    def _format_source_link(self, url: str) -> str:
        """Format source link for markdown."""
        domain = self._extract_domain(url)
        return f"[{domain}]({url})"
    
    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL."""
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc
            return domain.replace('www.', '')
        except:
            return url[:30] + "..." if len(url) > 30 else url
    
    def _get_impact_emoji(self, score: int) -> str:
        """Get emoji based on impact score."""
        if score >= 8:
            return "🔥"
        elif score >= 6:
            return "⚡"
        else:
            return "📊"
    
    def _estimate_reading_time(self, content: str) -> str:
        """Estimate reading time for content."""
        word_count = len(content.split())
        minutes = max(1, round(word_count / 200))  # 200 WPM average
        return f"{minutes} min read"
    
    def _generate_publishing_instructions(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> str:
        """Generate step-by-step Substack publishing instructions."""
        
        date_str = newsletter.date.strftime('%B %d, %Y')
        
        return f"""SUBSTACK PUBLISHING INSTRUCTIONS
{newsletter.title} - {date_str}

QUICK CHECKLIST:
□ Copy content from substack-{newsletter.date.strftime('%Y-%m-%d')}.html
□ Set title: "{newsletter.title} - {date_str}"
□ Add subtitle: "Strategic Intelligence Beyond the Headlines"
□ Schedule/publish for 6:00 AM your timezone
□ Add tags: geopolitics, analysis, newsletter, intelligence

STEP-BY-STEP:

1. Go to your Substack dashboard
2. Click "New post"
3. Title: "{newsletter.title} - {date_str}"
4. Subtitle: "Strategic Intelligence Beyond the Headlines"
5. Copy-paste HTML content from the .html file
6. Preview to ensure formatting looks good
7. Add these tags: geopolitics, analysis, newsletter, intelligence
8. Set publication time (recommend 6:00 AM)
9. Publish or schedule

CONTENT SUMMARY:
- {len(analyses)} strategic stories analyzed
- Average impact score: {sum(a.impact_score for a in analyses) / len(analyses):.1f}/10
- Estimated reading time: {self._estimate_reading_time(' '.join([a.why_important + a.what_overlooked + a.prediction for a in analyses]))}

TOP STORY: {analyses[0].story_title if analyses else 'N/A'}

ENGAGEMENT TIPS:
- Pin the post for higher visibility
- Share on Twitter with #geopolitics #strategy hashtags
- Consider creating a thread with key insights
- Engage with comments to build community

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"""