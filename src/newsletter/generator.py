"""
Newsletter HTML generation functionality.
"""

from datetime import datetime
from typing import List, Optional
from pathlib import Path

from ..models import Newsletter, AIAnalysis
from ..config import Config
from ..logger import get_logger
from ..ux.personalization import personalization_engine, feedback_collector

logger = get_logger(__name__)

class NewsletterGenerator:
    """Generates HTML newsletters from AI analysis results."""
    
    def __init__(self):
        """Initialize newsletter generator."""
        pass
    
    def generate_newsletter(self, analyses: List[AIAnalysis], date: Optional[datetime] = None) -> Newsletter:
        """
        Generate newsletter from AI analyses with balanced content types.

        Args:
            analyses: List of AI analysis results
            date: Newsletter date (defaults to current date)

        Returns:
            Newsletter object with generated content
        """
        if date is None:
            date = datetime.now()

        logger.info(f"Generating newsletter with {len(analyses)} stories for {date.strftime('%Y-%m-%d')}")

        # Balance content types: aim for 20-30% breaking news, rest analysis/trends
        selected_stories = self._select_balanced_stories(analyses)

        # Create newsletter object
        newsletter = Newsletter(
            date=date,
            title=Config.NEWSLETTER_TITLE,
            stories=selected_stories,
            intro_text=self._generate_intro_text(date, len(selected_stories)),
            footer_text=self._generate_footer_text()
        )

        return newsletter

    def _select_balanced_stories(self, analyses: List[AIAnalysis]) -> List[AIAnalysis]:
        """Select stories with balanced content types (20-30% breaking news)."""
        from ..models import ContentType

        # Separate stories by content type
        breaking_news = [a for a in analyses if a.content_type == ContentType.BREAKING_NEWS]
        analysis = [a for a in analyses if a.content_type == ContentType.ANALYSIS]
        trends = [a for a in analyses if a.content_type == ContentType.TREND]

        # Sort each category by impact score
        breaking_news.sort(key=lambda a: a.impact_score, reverse=True)
        analysis.sort(key=lambda a: a.impact_score, reverse=True)
        trends.sort(key=lambda a: a.impact_score, reverse=True)

        selected_stories = []
        target_breaking = max(1, int(len(analyses) * 0.25))  # 25% breaking news

        # Add breaking news stories (up to target)
        selected_stories.extend(breaking_news[:target_breaking])

        # Fill remaining slots with analysis and trends
        remaining_slots = len(analyses) - len(selected_stories)
        if remaining_slots > 0:
            # Combine analysis and trends, prioritizing by impact
            other_stories = analysis + trends
            other_stories.sort(key=lambda a: a.impact_score, reverse=True)
            selected_stories.extend(other_stories[:remaining_slots])

        # If we don't have enough stories, fill with highest impact from all
        if len(selected_stories) < len(analyses):
            all_sorted = sorted(analyses, key=lambda a: a.impact_score, reverse=True)
            for story in all_sorted:
                if story not in selected_stories:
                    selected_stories.append(story)
                    if len(selected_stories) >= len(analyses):
                        break

        return selected_stories[:len(analyses)]  # Ensure we don't exceed original count

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
        
        # Generate footer with enhanced feedback mechanisms
        footer = f"""
        <div class="footer">
            <p>{newsletter.title} - Geopolitical Intelligence for Decision Makers</p>
            {f'<p>{newsletter.footer_text}</p>' if newsletter.footer_text else ''}

            <!-- Feedback Section -->
            <div class="feedback-section">
                <h4>Help us improve this newsletter</h4>
                <p>How relevant was today's content to your work?</p>
                <div class="feedback-buttons">
                    <button class="feedback-btn" onclick="submitFeedback('relevance', 1)">Not Relevant</button>
                    <button class="feedback-btn" onclick="submitFeedback('relevance', 0.5)">Somewhat</button>
                    <button class="feedback-btn" onclick="submitFeedback('relevance', 1)">Very Relevant</button>
                </div>

                <p>How was the quality of analysis?</p>
                <div class="feedback-buttons">
                    <button class="feedback-btn" onclick="submitFeedback('quality', 0.3)">Poor</button>
                    <button class="feedback-btn" onclick="submitFeedback('quality', 0.7)">Good</button>
                    <button class="feedback-btn" onclick="submitFeedback('quality', 1)">Excellent</button>
                </div>

                <div class="feedback-form">
                    <textarea id="feedback-comment" placeholder="Additional comments (optional)" rows="2"></textarea>
                    <button class="submit-feedback-btn" onclick="submitDetailedFeedback()">Submit Feedback</button>
                </div>
            </div>

            <div class="newsletter-actions">
                <a href="#unsubscribe">Unsubscribe</a> |
                <a href="#archive">Archive</a> |
                <a href="#preferences">Update Preferences</a> |
                <a href="#recommendations">Get Recommendations</a>
            </div>
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
    <script>
        function submitFeedback(type, rating) {{
            // In a real implementation, this would send data to your backend
            console.log('Feedback submitted:', {{ type: type, rating: rating }});

            // Visual feedback
            const buttons = document.querySelectorAll('.feedback-btn');
            buttons.forEach(btn => btn.style.backgroundColor = '#3498db');

            // Show thank you message
            const feedbackSection = document.querySelector('.feedback-section');
            const thankYou = document.createElement('p');
            thankYou.textContent = 'Thank you for your feedback!';
            thankYou.style.color = '#27ae60';
            thankYou.style.fontWeight = 'bold';
            feedbackSection.appendChild(thankYou);

            // Disable buttons after submission
            setTimeout(() => {{
                buttons.forEach(btn => btn.disabled = true);
            }}, 1000);
        }}

        function submitDetailedFeedback() {{
            const comment = document.getElementById('feedback-comment').value;
            if (comment.trim()) {{
                console.log('Detailed feedback:', comment);
                alert('Thank you for your detailed feedback!');
                document.getElementById('feedback-comment').value = '';
            }}
        }}

        // Track content engagement
        document.addEventListener('DOMContentLoaded', function() {{
            // Track story views
            const stories = document.querySelectorAll('.story');
            stories.forEach((story, index) => {{
                const observer = new IntersectionObserver((entries) => {{
                    entries.forEach(entry => {{
                        if (entry.isIntersecting) {{
                            console.log('Story viewed:', index + 1);
                            // In real implementation, send view tracking data
                        }}
                    }});
                }}, {{ threshold: 0.5 }});

                observer.observe(story);
            }});
        }});
    </script>
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

        # Content type styling
        content_type_class = story.content_type.value
        content_type_display = {
            "breaking_news": "Breaking News",
            "analysis": "Analysis",
            "trend": "Trend"
        }.get(story.content_type.value, story.content_type.value.replace("_", " ").title())

        # Generate sources
        sources_html = ""
        if story.sources:
            sources_html = '<div class="sources"><div class="sources-title">Sources:</div>'
            for source in story.sources:
                sources_html += f'<a href="{source}" class="source-link" target="_blank">{source}</a>'
            sources_html += '</div>'

        # Generate multi-dimensional scores
        scores_html = f"""
        <div class="story-meta">
            <div class="content-type-badge {content_type_class}">{content_type_display}</div>
            <div class="score-row">
                <span class="score-label">Impact:</span>
                <span class="impact-score {impact_class}">{story.impact_score}/10</span>
            </div>
            <div class="score-row">
                <span class="score-label">Urgency:</span>
                <span class="urgency-score">{story.urgency_score}/10</span>
            </div>
            <div class="score-row">
                <span class="score-label">Scope:</span>
                <span class="scope-score">{story.scope_score}/10</span>
            </div>
            <div class="score-row">
                <span class="score-label">Novelty:</span>
                <span class="novelty-score">{story.novelty_score}/10</span>
            </div>
            <div class="score-row">
                <span class="score-label">Credibility:</span>
                <span class="credibility-score">{story.credibility_score}/10</span>
            </div>
            <div class="score-row">
                <span class="score-label">Impact Dim.:</span>
                <span class="impact-dimension-score">{story.impact_dimension_score}/10</span>
            </div>
        </div>
        """

        story_html = f"""
        <div class="story {content_type_class}">
            <div class="story-header">
                <h2 class="story-title">{story.story_title}</h2>
                {scores_html}
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
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .score-row {
            display: flex;
            align-items: center;
            margin-right: 15px;
        }

        .score-label {
            margin-right: 5px;
            font-weight: bold;
        }

        .impact-score, .urgency-score, .scope-score, .novelty-score, .credibility-score, .impact-dimension-score {
            display: inline-block;
            color: white;
            padding: 2px 6px;
            border-radius: 8px;
            font-size: 10px;
            font-weight: bold;
        }

        .impact-score.high { background-color: #e74c3c; }
        .impact-score.medium { background-color: #f39c12; }
        .impact-score.low { background-color: #27ae60; }

        .urgency-score { background-color: #9b59b6; }
        .scope-score { background-color: #3498db; }
        .novelty-score { background-color: #e67e22; }
        .credibility-score { background-color: #2ecc71; }
        .impact-dimension-score { background-color: #95a5a6; }

        .content-type-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            color: white;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .content-type-badge.breaking_news { background-color: #e74c3c; }
        .content-type-badge.analysis { background-color: #3498db; }
        .content-type-badge.trend { background-color: #9b59b6; }

        .story.breaking_news { border-left: 4px solid #e74c3c; }
        .story.analysis { border-left: 4px solid #3498db; }
        .story.trend { border-left: 4px solid #9b59b6; }
        
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

        /* Feedback Section Styles */
        .feedback-section {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border: 1px solid #ecf0f1;
        }

        .feedback-section h4 {
            color: #2c3e50;
            margin: 0 0 15px 0;
            font-size: 16px;
        }

        .feedback-section p {
            margin: 10px 0;
            color: #34495e;
            font-size: 14px;
        }

        .feedback-buttons {
            display: flex;
            gap: 10px;
            margin: 10px 0 20px 0;
            flex-wrap: wrap;
        }

        .feedback-btn {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background-color 0.3s;
        }

        .feedback-btn:hover {
            background-color: #2980b9;
        }

        .feedback-btn:disabled {
            background-color: #bdc3c7;
            cursor: not-allowed;
        }

        .feedback-form {
            margin-top: 15px;
        }

        .feedback-form textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
            font-size: 12px;
            resize: vertical;
        }

        .submit-feedback-btn {
            background-color: #27ae60;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            margin-top: 8px;
            transition: background-color 0.3s;
        }

        .submit-feedback-btn:hover {
            background-color: #229954;
        }

        .newsletter-actions {
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #ecf0f1;
            text-align: center;
        }

        .newsletter-actions a {
            margin: 0 10px;
            color: #3498db;
            text-decoration: none;
            font-size: 12px;
        }

        .newsletter-actions a:hover {
            text-decoration: underline;
        }

        /* Responsive design for feedback section */
        @media (max-width: 600px) {
            .feedback-buttons {
                flex-direction: column;
            }

            .feedback-btn {
                width: 100%;
                margin-bottom: 5px;
            }
        }
        """
    
    def _generate_intro_text(self, date: datetime, story_count: int) -> str:
        """Generate intro text for newsletter."""
        day_name = date.strftime('%A')
        date_str = date.strftime('%B %d, %Y')

        intro = f"""Good morning. Today is {day_name}, {date_str}.

Your daily geopolitical briefing covers {story_count} key developments shaping global affairs. We've balanced breaking news with in-depth analysis and emerging trends to provide comprehensive coverage for decision-makers.

Today's briefing includes immediate developments requiring attention, strategic analysis of ongoing situations, and emerging patterns that will influence international relations in the coming weeks."""

        return intro
    
    def _generate_footer_text(self) -> str:
        """Generate footer text for newsletter."""
        return """This daily briefing is generated using AI analysis of global news sources, providing balanced coverage of breaking developments, strategic analysis, and emerging trends. For questions or feedback, please contact our editorial team."""
    
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
        <p><strong>Scores:</strong> Impact: {story.impact_score}/10 | Urgency: {story.urgency_score}/10 | Scope: {story.scope_score}/10 | Novelty: {story.novelty_score}/10 | Credibility: {story.credibility_score}/10 | Impact Dim: {story.impact_dimension_score}/10</p>

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
