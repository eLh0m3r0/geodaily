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
    
    def generate_newsletter(self, analyses: List[AIAnalysis], date: Optional[datetime] = None,
                            quick_hits=None, big_number=None) -> Newsletter:
        """
        Generate newsletter from AI analyses with balanced content types.

        Args:
            analyses: List of AI analysis results (deep stories)
            date: Newsletter date (defaults to current date)
            quick_hits: optional list of QuickHit roundup items
            big_number: optional BigNumber delight element

        Returns:
            Newsletter object with generated content
        """
        if date is None:
            date = datetime.now()

        quick_hits = quick_hits or []
        logger.info(f"Generating newsletter with {len(analyses)} stories and "
                    f"{len(quick_hits)} quick hits for {date.strftime('%Y-%m-%d')}")

        # Balance content types: aim for 20-30% breaking news, rest analysis/trends
        selected_stories = self._select_balanced_stories(analyses)

        # Create newsletter object
        newsletter = Newsletter(
            date=date,
            title=Config.NEWSLETTER_TITLE,
            stories=selected_stories,
            intro_text=self._generate_intro_text(date, len(selected_stories), len(quick_hits)),
            footer_text=self._generate_footer_text(),
            quick_hits=quick_hits,
            big_number=big_number
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

        # "Also today" roundup + "The big number" delight element
        stories_html += self._generate_extras_html(newsletter)
        
        # Build optional Buttondown subscribe form (username resolved from the
        # API when the env var is missing, so the form can't silently vanish)
        from ..publishers.buttondown_util import resolve_buttondown_username, build_subscribe_form_html
        subscribe_html = ""
        username = resolve_buttondown_username()
        if username:
            subscribe_html = f"""
            <!-- Subscribe Section -->
            <div class="subscribe-section">
                <h4>Get this briefing in your inbox</h4>
                <p>World news from every side — daily or once a week, your choice.</p>
                {build_subscribe_form_html(username)}
            </div>
"""

        # Generate footer with enhanced feedback mechanisms
        footer = f"""
        <div class="footer">
            <p>{newsletter.title} - Geopolitical Intelligence for Decision Makers</p>
            {f'<p>{newsletter.footer_text}</p>' if newsletter.footer_text else ''}

            {subscribe_html}

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
                <a href="#archive">Archive</a> |
                <a href="#preferences">Update Preferences</a>
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

        # Content type styling
        content_type_class = story.content_type.value
        content_type_display = {
            "breaking_news": "Breaking News",
            "analysis": "Analysis",
            "trend": "Trend"
        }.get(story.content_type.value, story.content_type.value.replace("_", " ").title())

        # Generate sources as named outlet links, one per outlet
        from .source_display import dedupe_sources
        sources_html = ""
        named_sources = dedupe_sources(story.sources)
        if named_sources:
            sources_html = '<div class="sources"><div class="sources-title">Sources:</div>'
            for url, name in named_sources:
                sources_html += f'<a href="{url}" class="source-link" target="_blank" rel="noopener">{name}</a>'
            sources_html += '</div>'

        # Region and event type display
        region_display = story.region.replace("_", " ").title()
        event_type_display = story.event_type.replace("_", " ").title()

        # Story metadata: type + region + event only. Numeric scores stay
        # internal — unexplained "9/10 82%" chips read as pseudo-quantitative
        # noise to readers; priority is expressed by story order instead.
        scores_html = f"""
        <div class="story-meta">
            <div class="content-type-badge {content_type_class}">{content_type_display}</div>
            <div class="geo-tag region-tag">{region_display}</div>
            <div class="geo-tag event-tag">{event_type_display}</div>
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
    
    def _generate_extras_html(self, newsletter: Newsletter) -> str:
        """Render the Also Today roundup and Big Number sections (web)."""
        html = ""
        if newsletter.quick_hits:
            items = ""
            for hit in newsletter.quick_hits:
                region = hit.region.replace("_", " ").title()
                text = hit.text
                if hit.url:
                    text = f'{text} <a href="{hit.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>'
                items += f'<li><span class="quick-hit-region">{region}</span> {text}</li>\n'
            html += f"""
        <div class="also-today">
            <div class="section-heading">Also Today</div>
            <ul class="quick-hits">
{items}            </ul>
        </div>
"""
        if newsletter.big_number:
            bn = newsletter.big_number
            link = f' <a href="{bn.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>' if bn.url else ""
            html += f"""
        <div class="big-number">
            <div class="section-heading">The Big Number</div>
            <div class="big-number-value">{bn.value}</div>
            <div class="big-number-context">{bn.context}{link}</div>
        </div>
"""
        return html

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

        .geo-tag {
            display: inline-block;
            padding: 2px 7px;
            border-radius: 10px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin-bottom: 4px;
        }
        .region-tag { background-color: #ecf0f1; color: #34495e; border: 1px solid #bdc3c7; }
        .event-tag { background-color: #fef9e7; color: #7d6608; border: 1px solid #f9e79f; }

        /* Subscribe Section */
        .subscribe-section {
            background: linear-gradient(135deg, #1a2a4a 0%, #2c3e50 100%);
            color: white;
            padding: 24px;
            border-radius: 8px;
            margin: 24px 0;
            text-align: center;
        }
        .subscribe-section h4 {
            color: white;
            margin: 0 0 8px 0;
            font-size: 18px;
        }
        .subscribe-section p {
            color: #bdc3c7;
            margin: 0 0 16px 0;
            font-size: 13px;
        }
        .subscribe-form {
            display: flex;
            gap: 8px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .subscribe-form input[type="email"] {
            padding: 10px 14px;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            width: 240px;
            max-width: 100%;
        }
        .subscribe-btn {
            background-color: #e74c3c;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
        }
        .subscribe-btn:hover { background-color: #c0392b; }

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

        /* Also Today roundup */
        .also-today, .big-number {
            margin: 30px 0;
            padding: 20px 24px;
            background-color: #f7f8fa;
            border-radius: 8px;
        }
        .section-heading {
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #7f8c8d;
            margin-bottom: 12px;
        }
        .quick-hits { margin: 0; padding-left: 18px; }
        .quick-hits li { margin-bottom: 10px; line-height: 1.5; }
        .quick-hit-region {
            display: inline-block;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #2c5282;
            margin-right: 6px;
        }
        .quick-hit-link { text-decoration: none; color: #3498db; }
        .big-number-value {
            font-size: 40px;
            font-weight: bold;
            color: #2c3e50;
            line-height: 1.1;
        }
        .big-number-context { color: #4a5568; margin-top: 6px; }

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
    
    def _generate_intro_text(self, date: datetime, story_count: int, quick_hit_count: int = 0) -> str:
        """Generate intro text for newsletter.

        Kept to two short sentences — on mobile a long boilerplate intro fills
        the entire first screen before any actual content.
        """
        day_name = date.strftime('%A')
        date_str = date.strftime('%B %d, %Y')

        if quick_hit_count:
            return (f"Good morning. It's {day_name}, {date_str} — one story worth your "
                    f"full attention today, plus {quick_hit_count} quick updates from "
                    f"around the world.")
        return (f"Good morning. It's {day_name}, {date_str} — today's briefing covers "
                f"{story_count} developments shaping global affairs.")
    
    def _generate_footer_text(self) -> str:
        """Generate footer text for newsletter.

        Honest human-in-the-loop framing: readers accept AI-assisted news when
        a named human is visibly responsible (Reuters Institute DNR 2025) —
        never an anonymous "generated by AI" line pointing at a fake team.
        """
        curator = Config.NEWSLETTER_EDITOR_NAME
        if curator:
            drafted = f"Drafted with AI from the sources linked above, curated and reviewed by {curator}."
        else:
            drafted = "Drafted with AI from the sources linked above, with human review before sending."
        return f"{drafted} Spotted an error or have a tip? Just reply — a human reads every response."
    
    def generate_email_html(self, newsletter: Newsletter) -> str:
        """Generate email-safe HTML with inline styles for Buttondown delivery.

        Unlike generate_html(), this version embeds all styles inline so they
        survive email client rendering and Buttondown's head-stripping template.
        """
        C_NAVY   = "#1a2744"
        C_GOLD   = "#c9a84c"
        C_TEXT   = "#2d3748"
        C_MUTED  = "#718096"
        C_LIGHT  = "#f7f8fa"
        C_BORDER = "#e2e8f0"
        C_LINK   = "#2c5282"
        C_WHITE  = "#ffffff"
        TYPE_COLORS = {
            "breaking_news": "#e74c3c",
            "analysis": "#2b6cb0",
            "trend": "#6b46c1",
        }

        # No hyphenation anywhere — email clients (and Buttondown's wrapper CSS)
        # otherwise hyphenate aggressively on narrow screens ("immedi-ate").
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"

        # This <style> block lives in the BODY on purpose: Buttondown strips the
        # <head>, but body content is passed through. It fixes two mobile issues
        # inline styles cannot: iOS data detectors turning "9/10" into a blue
        # link, and font/padding downscaling on small screens (!important is
        # required to beat the inline styles).
        style_block = """<style>
a[x-apple-data-detectors]{color:inherit !important;text-decoration:none !important;font-size:inherit !important;font-family:inherit !important;font-weight:inherit !important;line-height:inherit !important;}
body,div,h1,h2,p{-webkit-hyphens:none !important;-ms-hyphens:none !important;hyphens:none !important;}
@media only screen and (max-width:480px){
  .nl-body{padding:6px !important;}
  .nl-content{padding-left:16px !important;padding-right:16px !important;}
  .nl-header{padding:24px 16px !important;}
  .nl-h1{font-size:23px !important;}
  .nl-h2{font-size:19px !important;}
  .nl-intro{padding:14px 14px !important;}
  .nl-box{padding:12px 14px !important;}
}
</style>"""

        header_html = f"""<div class="nl-header" style="background-color:{C_NAVY};padding:30px 24px;text-align:center;">
  <div style="font-family:Georgia,'Times New Roman',serif;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:{C_GOLD};margin-bottom:10px;">Intelligence Briefing</div>
  <h1 class="nl-h1" style="font-family:Georgia,'Times New Roman',serif;font-size:26px;font-weight:bold;color:{C_WHITE};margin:0 0 8px 0;line-height:1.25;{NO_HYPHENS}">{newsletter.title}</h1>
  <div style="font-family:Georgia,'Times New Roman',serif;font-size:13px;color:#94a3b8;margin-bottom:8px;font-style:italic;">Strategic Intelligence Beyond the Headlines</div>
  <div style="font-family:Georgia,'Times New Roman',serif;font-size:13px;color:#64748b;">{newsletter.date.strftime('%A, %B %-d, %Y')}</div>
</div>
<div style="background-color:{C_GOLD};height:3px;"></div>"""

        intro_html = ""
        if newsletter.intro_text:
            # Render paragraphs explicitly instead of relying on white-space:
            # pre-line, which turns any stray newline into a ragged mobile mess.
            paras = [p.strip() for p in newsletter.intro_text.split("\n\n") if p.strip()]
            paragraphs = "".join(
                f'<p style="margin:{"0" if i == len(paras) - 1 else "0 0 12px 0"};">{p}</p>'
                for i, p in enumerate(paras)
            )
            intro_html = f"""<div class="nl-intro" style="background-color:{C_LIGHT};border-left:4px solid {C_GOLD};padding:16px 18px;margin:24px 0;font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.7;color:{C_TEXT};{NO_HYPHENS}">{paragraphs}</div>"""

        stories_html = ""
        for i, story in enumerate(newsletter.stories):
            is_last = (i == len(newsletter.stories) - 1)
            stories_html += self._generate_email_story_html(
                story, is_last, TYPE_COLORS, C_NAVY, C_TEXT, C_MUTED, C_LIGHT, C_BORDER, C_GOLD, C_LINK
            )
        stories_html += self._generate_email_extras_html(
            newsletter, C_NAVY, C_TEXT, C_MUTED, C_LIGHT, C_BORDER, C_GOLD, C_LINK
        )

        footer_html = f"""<div style="border-top:2px solid {C_BORDER};margin-top:32px;padding-top:24px;text-align:center;font-family:Georgia,'Times New Roman',serif;font-size:12px;color:{C_MUTED};line-height:1.8;">
  <p style="margin:0 0 6px 0;font-weight:bold;color:{C_TEXT};">{newsletter.title}</p>
  <p style="margin:0 0 12px 0;">Geopolitical Intelligence for Decision Makers</p>
  {f'<p style="margin:0 0 12px 0;">{newsletter.footer_text}</p>' if newsletter.footer_text else ''}
  <p style="margin:0 0 6px 0;font-size:11px;color:{C_MUTED};">Too much email? Reply with the word "weekly" and we'll switch you to the Sunday digest.</p>
  <p style="margin:0;font-size:11px;color:{C_MUTED};">You are receiving this because you subscribed to {newsletter.title}.</p>
</div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{newsletter.title} — {newsletter.date.strftime('%B %-d, %Y')}</title>
</head>
<body class="nl-body" style="margin:0;padding:12px;background-color:#f0f2f5;font-family:Georgia,'Times New Roman',serif;">
{style_block}
<div style="max-width:600px;margin:0 auto;background-color:{C_WHITE};border-radius:6px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
  {header_html}
  <div class="nl-content" style="padding:0 24px 28px 24px;">
    {intro_html}
    {stories_html}
    {footer_html}
  </div>
</div>
</body>
</html>"""

    def _generate_email_story_html(
        self, story, is_last: bool,
        type_colors: dict, C_NAVY: str, C_TEXT: str, C_MUTED: str,
        C_LIGHT: str, C_BORDER: str, C_GOLD: str, C_LINK: str
    ) -> str:
        """Generate inline-styled HTML for a single story in email format."""
        content_type_val = story.content_type.value
        content_type_color = type_colors.get(content_type_val, "#718096")
        content_type_display = {
            "breaking_news": "Breaking News",
            "analysis": "Analysis",
            "trend": "Trend",
        }.get(content_type_val, content_type_val.replace("_", " ").title())

        region_display = story.region.replace("_", " ").title()

        sources_html = ""
        from .source_display import dedupe_sources
        named_sources = dedupe_sources(story.sources)
        if named_sources:
            source_links = "".join(
                f'<a href="{src}" style="color:{C_LINK};text-decoration:none;font-size:13px;display:inline-block;margin-right:12px;margin-bottom:4px;">{name}</a>'
                for src, name in named_sources
            )
            sources_html = f"""<div style="border-top:1px solid {C_BORDER};margin-top:20px;padding-top:14px;">
  <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;color:{C_MUTED};margin-bottom:8px;">Sources</div>
  <div>{source_links}</div>
</div>"""

        border_bottom = "" if is_last else f"border-bottom:1px solid {C_BORDER};"
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"

        return f"""<div style="{border_bottom}margin-bottom:28px;padding-bottom:28px;padding-top:24px;">
  <div style="margin-bottom:12px;">
    <span style="display:inline-block;background-color:{content_type_color};color:#ffffff;font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;padding:4px 10px;border-radius:12px;margin-right:6px;margin-bottom:4px;">{content_type_display}</span>
    <span style="display:inline-block;background-color:{C_LIGHT};color:#4a5568;font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;padding:4px 8px;border-radius:10px;border:1px solid {C_BORDER};margin-right:6px;margin-bottom:4px;">{region_display}</span>
  </div>
  <h2 class="nl-h2" style="font-family:Georgia,'Times New Roman',serif;font-size:21px;font-weight:bold;color:{C_NAVY};margin:0 0 16px 0;line-height:1.35;{NO_HYPHENS}">{story.story_title}</h2>
  <div style="margin-bottom:18px;">
    <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;color:{C_MUTED};margin-bottom:6px;">Why This Matters</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.7;color:{C_TEXT};{NO_HYPHENS}">{story.why_important}</div>
  </div>
  <div class="nl-box" style="margin-bottom:18px;background-color:{C_LIGHT};padding:14px 16px;border-left:3px solid {C_GOLD};">
    <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;color:{C_MUTED};margin-bottom:6px;">What Others Are Missing</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.7;color:{C_TEXT};{NO_HYPHENS}">{story.what_overlooked}</div>
  </div>
  <div style="margin-bottom:18px;">
    <div style="font-size:10px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;color:{C_MUTED};margin-bottom:6px;">What to Watch</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.7;color:{C_TEXT};{NO_HYPHENS}">{story.prediction}</div>
  </div>
  {sources_html}
</div>"""

    def _generate_email_extras_html(
        self, newsletter: Newsletter,
        C_NAVY: str, C_TEXT: str, C_MUTED: str, C_LIGHT: str,
        C_BORDER: str, C_GOLD: str, C_LINK: str
    ) -> str:
        """Inline-styled Also Today + Big Number sections for the email."""
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"
        heading_style = (f"font-size:10px;font-weight:bold;text-transform:uppercase;"
                         f"letter-spacing:2px;color:{C_MUTED};margin-bottom:12px;")
        html = ""
        if newsletter.quick_hits:
            items = ""
            for hit in newsletter.quick_hits:
                region = hit.region.replace("_", " ").title()
                arrow = (f' <a href="{hit.url}" style="color:{C_LINK};text-decoration:none;">&rarr;</a>'
                         if hit.url else "")
                items += (f'<div style="margin-bottom:10px;font-family:Georgia,\'Times New Roman\',serif;'
                          f'font-size:14px;line-height:1.6;color:{C_TEXT};{NO_HYPHENS}">'
                          f'<span style="font-size:10px;font-weight:bold;text-transform:uppercase;'
                          f'letter-spacing:0.5px;color:{C_LINK};margin-right:6px;">{region}</span>'
                          f'{hit.text}{arrow}</div>')
            html += (f'<div class="nl-box" style="margin:26px 0;background-color:{C_LIGHT};'
                     f'padding:16px 18px;border-left:3px solid {C_NAVY};">'
                     f'<div style="{heading_style}">Also Today</div>{items}</div>')
        if newsletter.big_number:
            bn = newsletter.big_number
            arrow = (f' <a href="{bn.url}" style="color:{C_LINK};text-decoration:none;">&rarr;</a>'
                     if bn.url else "")
            html += (f'<div class="nl-box" style="margin:26px 0;background-color:{C_LIGHT};'
                     f'padding:16px 18px;border-left:3px solid {C_GOLD};">'
                     f'<div style="{heading_style}">The Big Number</div>'
                     f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:34px;'
                     f'font-weight:bold;color:{C_NAVY};line-height:1.1;">{bn.value}</div>'
                     f'<div style="font-family:Georgia,\'Times New Roman\',serif;font-size:14px;'
                     f'line-height:1.6;color:{C_TEXT};margin-top:6px;{NO_HYPHENS}">{bn.context}{arrow}</div>'
                     f'</div>')
        return html

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
