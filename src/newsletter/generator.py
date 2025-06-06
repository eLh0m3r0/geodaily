"""
Newsletter HTML generation functionality.
"""

from datetime import datetime
from typing import List, Optional
from pathlib import Path

try:
    from ..models import Newsletter, AIAnalysis
    from ..config import Config
    from ..logger import get_logger
except ImportError:
    from models import Newsletter, AIAnalysis
    from config import Config
    from logger import get_logger

logger = get_logger(__name__)

class NewsletterGenerator:
    """Generates HTML newsletters from AI analysis results."""
    
    def __init__(self):
        """Initialize newsletter generator."""
        pass
    
    def generate_newsletter(self, analyses: List[AIAnalysis], date: Optional[datetime] = None) -> Newsletter:
        """
        Generate newsletter from AI analyses.
        
        Args:
            analyses: List of AI analysis results
            date: Newsletter date (defaults to current date)
            
        Returns:
            Newsletter object with generated content
        """
        if date is None:
            date = datetime.now()
        
        logger.info(f"Generating newsletter with {len(analyses)} stories for {date.strftime('%Y-%m-%d')}")
        
        # Sort analyses by impact score
        sorted_analyses = sorted(analyses, key=lambda a: a.impact_score, reverse=True)
        
        # Create newsletter object
        newsletter = Newsletter(
            date=date,
            title=Config.NEWSLETTER_TITLE,
            stories=sorted_analyses,
            intro_text=self._generate_intro_text(date, len(sorted_analyses)),
            footer_text=self._generate_footer_text()
        )
        
        return newsletter
    
    def generate_html(self, newsletter: Newsletter) -> str:
        """
        Generate HTML content for newsletter.
        
        Args:
            newsletter: Newsletter object
            
        Returns:
            HTML content as string
        """
        logger.info("Generating HTML content for newsletter")
        
        try:
            html_content = self._generate_newsletter_html(newsletter)
            logger.info("HTML content generated successfully")
            return html_content
            
        except Exception as e:
            logger.error(f"Error generating HTML: {e}")
            return self._generate_fallback_html(newsletter)
    
    def save_html(self, html_content: str, filename: Optional[str] = None) -> Path:
        """
        Save HTML content to file.
        
        Args:
            html_content: HTML content to save
            filename: Optional filename (defaults to date-based name)
            
        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"newsletter_{timestamp}.html"
        
        # Ensure output directory exists
        output_dir = Config.PROJECT_ROOT / "output"
        output_dir.mkdir(exist_ok=True)
        
        file_path = output_dir / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Newsletter saved to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving newsletter: {e}")
            raise
    
    def _generate_newsletter_html(self, newsletter: Newsletter) -> str:
        """Generate complete newsletter HTML."""
        
        # Generate CSS styles
        css = self._get_newsletter_css()
        
        # Generate header
        header = f"""
        <div class="header">
            <h1>{newsletter.title}</h1>
            <div class="date">{newsletter.date.strftime('%B %d, %Y')}</div>
        </div>
        """
        
        # Generate intro
        intro = ""
        if newsletter.intro_text:
            intro = f'<div class="intro">{newsletter.intro_text}</div>'
        
        # Generate stories
        stories_html = ""
        for story in newsletter.stories:
            stories_html += self._generate_story_html(story)
        
        # Generate footer
        footer = f"""
        <div class="footer">
            <p>{newsletter.title} - Geopolitical Intelligence for Decision Makers</p>
            {f'<p>{newsletter.footer_text}</p>' if newsletter.footer_text else ''}
            <p>
                <a href="#unsubscribe">Unsubscribe</a> | 
                <a href="#archive">Archive</a> | 
                <a href="#feedback">Feedback</a>
            </p>
        </div>
        """
        
        # Combine all parts
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{newsletter.title} - {newsletter.date.strftime('%Y-%m-%d')}</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        {header}
        {intro}
        {stories_html}
        {footer}
    </div>
</body>
</html>"""
        
        return html
    
    def _generate_story_html(self, story: AIAnalysis) -> str:
        """Generate HTML for a single story."""
        
        # Determine impact score class
        if story.impact_score >= 8:
            impact_class = "high"
        elif story.impact_score >= 6:
            impact_class = "medium"
        else:
            impact_class = "low"
        
        # Generate sources
        sources_html = ""
        if story.sources:
            sources_html = '<div class="sources"><div class="sources-title">Sources:</div>'
            for source in story.sources:
                sources_html += f'<a href="{source}" class="source-link" target="_blank">{source}</a>'
            sources_html += '</div>'
        
        story_html = f"""
        <div class="story">
            <div class="story-header">
                <h2 class="story-title">{story.story_title}</h2>
                <div class="story-meta">
                    Impact Score: 
                    <span class="impact-score {impact_class}">
                        {story.impact_score}/10
                    </span>
                </div>
            </div>
            
            <div class="story-section">
                <div class="section-title">Why This Matters</div>
                <div class="section-content">{story.why_important}</div>
            </div>
            
            <div class="story-section">
                <div class="section-title">What Others Are Missing</div>
                <div class="section-content">{story.what_overlooked}</div>
            </div>
            
            <div class="story-section">
                <div class="section-title">What to Watch</div>
                <div class="section-content">{story.prediction}</div>
            </div>
            
            {sources_html}
        </div>
        """
        
        return story_html
    
    def _get_newsletter_css(self) -> str:
        """Get CSS styles for newsletter."""
        return """
        body {
            font-family: 'Georgia', 'Times New Roman', serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header {
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #2c3e50;
            font-size: 28px;
            margin: 0;
            font-weight: bold;
        }
        
        .header .date {
            color: #7f8c8d;
            font-size: 14px;
            margin-top: 5px;
        }
        
        .intro {
            background-color: #ecf0f1;
            padding: 20px;
            border-left: 4px solid #3498db;
            margin-bottom: 30px;
            font-style: italic;
            white-space: pre-line;
        }
        
        .story {
            margin-bottom: 40px;
            border-bottom: 1px solid #ecf0f1;
            padding-bottom: 30px;
        }
        
        .story:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }
        
        .story-title {
            color: #2c3e50;
            font-size: 20px;
            font-weight: bold;
            margin: 0 0 10px 0;
            line-height: 1.3;
        }
        
        .story-meta {
            color: #7f8c8d;
            font-size: 12px;
            margin-bottom: 15px;
        }
        
        .impact-score {
            display: inline-block;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 10px;
        }
        
        .impact-score.high { background-color: #e74c3c; }
        .impact-score.medium { background-color: #f39c12; }
        .impact-score.low { background-color: #27ae60; }
        
        .story-section {
            margin-bottom: 15px;
        }
        
        .section-title {
            color: #34495e;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .section-content {
            color: #2c3e50;
            line-height: 1.6;
        }
        
        .sources {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #ecf0f1;
        }
        
        .sources-title {
            color: #7f8c8d;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .source-link {
            display: block;
            color: #3498db;
            text-decoration: none;
            font-size: 12px;
            margin-bottom: 3px;
            word-break: break-all;
        }
        
        .source-link:hover {
            text-decoration: underline;
        }
        
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
        }
        
        .footer a {
            color: #3498db;
            text-decoration: none;
        }
        
        .footer a:hover {
            text-decoration: underline;
        }
        """
    
    def _generate_intro_text(self, date: datetime, story_count: int) -> str:
        """Generate intro text for newsletter."""
        day_name = date.strftime('%A')
        date_str = date.strftime('%B %d, %Y')
        
        intro = f"""Good morning. Today is {day_name}, {date_str}.

This edition analyzes {story_count} underreported geopolitical developments that mainstream media is overlooking or underemphasizing. Each story has been selected for its potential second-order effects and strategic implications for decision-makers.

Our focus today spans emerging power dynamics, resource geopolitics, and strategic developments that could reshape international relations in the coming weeks."""
        
        return intro
    
    def _generate_footer_text(self) -> str:
        """Generate footer text for newsletter."""
        return """This newsletter is generated using AI analysis of global news sources, focusing on underreported stories with significant geopolitical implications. For questions or feedback, please contact our editorial team."""
    
    def _generate_fallback_html(self, newsletter: Newsletter) -> str:
        """Generate basic HTML if main generation fails."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{newsletter.title} - {newsletter.date.strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .story {{ margin-bottom: 30px; border-bottom: 1px solid #ccc; padding-bottom: 20px; }}
        .story-title {{ color: #333; font-size: 18px; font-weight: bold; }}
        .section {{ margin: 10px 0; }}
        .section-title {{ font-weight: bold; color: #666; }}
    </style>
</head>
<body>
    <h1>{newsletter.title}</h1>
    <p><strong>Date:</strong> {newsletter.date.strftime('%B %d, %Y')}</p>
    
    {f'<div class="intro">{newsletter.intro_text}</div>' if newsletter.intro_text else ''}
    
"""
        
        for story in newsletter.stories:
            html += f"""
    <div class="story">
        <h2 class="story-title">{story.story_title}</h2>
        <p><strong>Impact Score:</strong> {story.impact_score}/10</p>
        
        <div class="section">
            <div class="section-title">Why This Matters:</div>
            <p>{story.why_important}</p>
        </div>
        
        <div class="section">
            <div class="section-title">What Others Are Missing:</div>
            <p>{story.what_overlooked}</p>
        </div>
        
        <div class="section">
            <div class="section-title">What to Watch:</div>
            <p>{story.prediction}</p>
        </div>
        
        {'<div class="section"><div class="section-title">Sources:</div><ul>' + "".join(f"<li><a href='{source}'>{source}</a></li>" for source in story.sources) + '</ul></div>' if story.sources else ''}
    </div>
"""
        
        html += f"""
    {f'<div class="footer">{newsletter.footer_text}</div>' if newsletter.footer_text else ''}
</body>
</html>
"""
        
        return html
