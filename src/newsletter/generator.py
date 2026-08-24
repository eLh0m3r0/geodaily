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
                            quick_hits=None, big_number=None,
                            perspective_grid=None, signals=None) -> Newsletter:
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
            big_number=big_number,
            perspective_grid=perspective_grid,
            signals=signals or []
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
        
        # Generate stories — the perspective grid and signals live inside the
        # big story's flow, not as trailing boxes after it
        grid_block = self._generate_perspective_grid_html(newsletter)
        signals_block = self._generate_signals_html(newsletter)
        stories_html = ""
        for i, story in enumerate(newsletter.stories):
            if i == 0:
                stories_html += '<div class="section-label">The Big Story</div>'
            stories_html += self._generate_story_html(
                story,
                mid_block=grid_block if i == 0 else "",
                after_watch_block=signals_block if i == 0 else "")

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
            buttons.forEach(btn => btn.style.backgroundColor = '#1F6FEB');

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
    
    def _generate_story_html(self, story: AIAnalysis, mid_block: str = "",
                             after_watch_block: str = "") -> str:
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

            {mid_block}

            <div class="story-section">
                <div class="section-title">What Others Are Missing</div>
                <div class="section-content">{story.what_overlooked}</div>
            </div>

            <div class="story-section">
                <div class="section-title">What to Watch</div>
                <div class="section-content">{story.prediction}</div>
            </div>

            {after_watch_block}

            {sources_html}
        </div>
        """

        return story_html
    
    def _generate_perspective_grid_html(self, newsletter: Newsletter) -> str:
        """Render the How the World Covers It block (web)."""
        grid = getattr(newsletter, 'perspective_grid', None)
        if not grid or not grid.counts:
            return ""
        from ..perspectives import summarize_grid
        parts, _legend = summarize_grid(grid)

        bar_spans = "".join(
            f'<span style="flex:{p["count"]};background-color:{p["color"]};" title="{p["label"]}: {p["count"]}"></span>'
            for p in parts
        )
        legend_html = " &middot; ".join(f'{p["pct"]}% {p["label"]}' for p in parts)

        rows = ""
        for view in grid.views:
            if not view.framing:
                continue
            from ..perspectives import GROUP_COLORS, label_of
            color = GROUP_COLORS.get(view.perspective, "#6B7280")
            state = ' <span class="state-label">state-affiliated</span>' if view.state_affiliated else ""
            quote_html = ""
            if view.quote:
                outlet = view.quote_outlet or ""
                link = (f'<a href="{view.quote_url}" target="_blank" rel="noopener">{outlet}</a>'
                        if view.quote_url else outlet)
                quote_html = f'<div class="persp-quote">&ldquo;{view.quote}&rdquo; &mdash; {link}</div>'
            rows += f"""
                <div class="persp-row">
                    <span class="persp-dot" style="background-color:{color};"></span>
                    <div>
                        <span class="persp-name">{label_of(view.perspective)} ({view.article_count})</span>{state}
                        &mdash; {view.framing}
                        {quote_html}
                    </div>
                </div>"""

        blindspot_html = ""
        if grid.blindspot:
            arrow = (f' <a href="{grid.blindspot_url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>'
                     if grid.blindspot_url else "")
            blindspot_html = f'<div class="blindspot">&#9888; <strong>Blindspot:</strong> {grid.blindspot}{arrow}</div>'

        return f"""
        <div class="perspective-grid">
            <div class="section-heading">How the World Covers It</div>
            <div class="coverage-bar">{bar_spans}</div>
            <div class="coverage-legend">{grid.total_outlets} outlets &middot; {legend_html}</div>
            {rows}
            {blindspot_html}
        </div>
"""

    def _generate_signals_html(self, newsletter: Newsletter) -> str:
        """Render the Signals block (web)."""
        signals = getattr(newsletter, 'signals', None) or []
        if not signals:
            return ""
        items = ""
        for signal in signals:
            arrow = (f' <a href="{signal.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>'
                     if signal.url else "")
            items += f'<li>{signal.text}{arrow}</li>\n'
        return f"""
        <div class="signals">
            <div class="section-heading">Signals</div>
            <ul class="quick-hits">
{items}            </ul>
        </div>
"""

    def _generate_extras_html(self, newsletter: Newsletter) -> str:
        """Render Also Today and Big Number after the stories (web).

        The perspective grid and signals render inside the big story, not here.
        """
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.65;
            color: #14181D;
            max-width: 640px;
            margin: 0 auto;
            padding: 20px;
            background-color: #EEF1F4;
        }
        
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header {
            text-align: center;
            border-bottom: 3px solid #14181D;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #14181D;
            font-size: 28px;
            margin: 0;
            font-weight: bold;
        }
        
        .header .date {
            color: #9AA3AB;
            font-size: 14px;
            margin-top: 5px;
        }
        
        .intro {
            background-color: #ecf0f1;
            padding: 20px;
            border-left: 4px solid #1F6FEB;
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
            color: #14181D;
            font-size: 20px;
            font-weight: bold;
            margin: 0 0 10px 0;
            line-height: 1.3;
        }
        
        .story-meta {
            color: #9AA3AB;
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
        .scope-score { background-color: #1F6FEB; }
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
        .content-type-badge.analysis { background-color: #1F6FEB; }
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
            background: #14181D;
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
        .story.analysis { border-left: 4px solid #1F6FEB; }
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
            color: #14181D;
            line-height: 1.6;
        }
        
        .sources {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #ecf0f1;
        }
        
        .sources-title {
            color: #9AA3AB;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .source-link {
            display: block;
            color: #1F6FEB;
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
            color: #9AA3AB;
            font-size: 12px;
        }
        
        .footer a {
            color: #1F6FEB;
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
            color: #14181D;
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
            background-color: #1F6FEB;
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

        .section-label {
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #14181D;
            border-top: 3px solid #14181D;
            display: inline-block;
            padding-top: 7px;
            margin: 34px 0 10px 0;
        }
        .big-number { text-align: center; }

        /* Perspective grid */
        .perspective-grid, .signals {
            margin: 30px 0;
            padding: 20px 24px;
            background-color: #f7f8fa;
            border-radius: 8px;
        }
        .coverage-bar {
            display: flex;
            height: 6px;
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        .coverage-legend {
            font-size: 12px;
            color: #9AA3AB;
            margin-bottom: 16px;
        }
        .persp-row {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            margin-bottom: 12px;
            line-height: 1.5;
        }
        .persp-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-top: 6px;
            flex-shrink: 0;
        }
        .persp-name { font-weight: bold; }
        .state-label {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background-color: #f5e6c8;
            color: #8a6d1a;
            border-radius: 8px;
            padding: 1px 7px;
            margin-left: 4px;
        }
        .persp-quote {
            font-style: italic;
            color: #4a5568;
            margin-top: 4px;
            font-size: 14px;
        }
        .blindspot {
            background-color: #fdf3e3;
            color: #8a5a17;
            border-radius: 6px;
            padding: 10px 14px;
            margin-top: 14px;
            font-size: 14px;
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
            color: #9AA3AB;
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
            color: #1F6FEB;
            margin-right: 6px;
        }
        .quick-hit-link { text-decoration: none; color: #1F6FEB; }
        .big-number-value {
            font-size: 40px;
            font-weight: bold;
            color: #14181D;
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
            color: #1F6FEB;
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

        Design language: ink on white, the perspective spectrum as the only
        brand color, system sans stack. No serif-briefing cosplay, no beige.
        All styles inline so they survive email-client head-stripping.
        """
        INK    = "#14181D"
        SUB    = "#57616B"
        FAINT  = "#9AA3AB"
        LINE   = "#E6E9EC"
        WASH   = "#F5F7F9"
        ACCENT = "#1F6FEB"
        RED    = "#D6453A"
        SANS   = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;"

        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"

        # Body <style>: Buttondown strips <head>, body styles pass through.
        # Fixes iOS data detectors and downsizes type on small screens.
        style_block = """<style>
a[x-apple-data-detectors]{color:inherit !important;text-decoration:none !important;font-size:inherit !important;font-family:inherit !important;font-weight:inherit !important;line-height:inherit !important;}
body,div,h1,h2,p{-webkit-hyphens:none !important;-ms-hyphens:none !important;hyphens:none !important;}
@media only screen and (max-width:480px){
  .nl-body{padding:6px !important;}
  .nl-content{padding-left:18px !important;padding-right:18px !important;}
  .nl-h1{font-size:23px !important;}
  .nl-box{padding:12px 14px !important;}
  .nl-num{font-size:42px !important;}
}
</style>"""

        from ..perspectives import spectrum_bar_html
        header_html = f"""{spectrum_bar_html(5)}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:22px 24px 0 24px;">
  <tr>
    <td style="{SANS}font-size:14px;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:{INK};">{newsletter.title}</td>
    <td align="right" style="{SANS}font-size:12px;color:{FAINT};">{newsletter.date.strftime('%a, %b %-d, %Y')}</td>
  </tr>
  <tr>
    <td colspan="2" style="{SANS}font-size:12px;color:{FAINT};padding-top:3px;">{Config.NEWSLETTER_TAGLINE}</td>
  </tr>
</table>"""

        intro_html = ""
        if newsletter.intro_text:
            paras = [p.strip() for p in newsletter.intro_text.split("\n\n") if p.strip()]
            paragraphs = "".join(
                f'<p style="margin:{"0" if i == len(paras) - 1 else "0 0 10px 0"};">{p}</p>'
                for i, p in enumerate(paras)
            )
            intro_html = (f'<div style="{SANS}font-size:15px;line-height:1.65;color:{SUB};'
                          f'margin:20px 0 6px 0;{NO_HYPHENS}">{paragraphs}</div>')

        def kicker(text):
            return (f'<div style="margin-top:28px;">'
                    f'<div style="width:28px;height:3px;background-color:{INK};margin-bottom:7px;font-size:0;line-height:0;">&nbsp;</div>'
                    f'<div style="{SANS}font-size:11px;font-weight:800;letter-spacing:2px;'
                    f'text-transform:uppercase;color:{INK};margin-bottom:12px;">{text}</div></div>')

        grid_block = self._email_grid_block(newsletter, INK, SUB, FAINT, LINE, WASH, ACCENT, SANS)
        signals_block = self._email_signals_block(newsletter, SUB, FAINT, ACCENT, SANS)

        stories_html = ""
        for i, story in enumerate(newsletter.stories):
            if i == 0:
                stories_html += kicker("The Big Story")
            stories_html += self._generate_email_story_html(
                story, INK, SUB, FAINT, LINE, WASH, ACCENT, RED, SANS,
                mid_block=grid_block if i == 0 else "",
                after_watch_block=signals_block if i == 0 else ""
            )
        stories_html += self._generate_email_extras_html(
            newsletter, INK, SUB, FAINT, LINE, ACCENT, SANS, kicker
        )

        footer_html = f"""<div style="border-top:1px solid {LINE};margin-top:30px;padding-top:18px;{SANS}font-size:12px;color:{FAINT};line-height:1.8;">
  <p style="margin:0 0 8px 0;color:{SUB};">{newsletter.footer_text}</p>
  <p style="margin:0 0 4px 0;">Too much email? Reply with the word "weekly" and we'll switch you to the Sunday digest.</p>
  <p style="margin:0;">You are receiving this because you subscribed to {newsletter.title}.</p>
</div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{newsletter.title} — {newsletter.date.strftime('%B %-d, %Y')}</title>
</head>
<body class="nl-body" style="margin:0;padding:14px;background-color:#EEF1F4;{SANS}">
{style_block}
<div style="max-width:600px;margin:0 auto;background-color:#ffffff;border:1px solid {LINE};border-radius:8px;overflow:hidden;">
  {header_html}
  <div class="nl-content" style="padding:0 24px 26px 24px;">
    {intro_html}
    {stories_html}
    {footer_html}
  </div>
</div>
</body>
</html>"""
    def _generate_email_story_html(
        self, story, INK: str, SUB: str, FAINT: str, LINE: str, WASH: str,
        ACCENT: str, RED: str, SANS: str,
        mid_block: str = "", after_watch_block: str = ""
    ) -> str:
        """Inline-styled HTML for one story in the email."""
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"

        content_type_val = story.content_type.value
        type_display = {
            "breaking_news": "Breaking",
            "analysis": "Analysis",
            "trend": "Trend",
        }.get(content_type_val, content_type_val.replace("_", " ").title())
        type_color = RED if content_type_val == "breaking_news" else FAINT
        region_display = story.region.replace("_", " ").title()
        meta_line = (f'<div style="{SANS}font-size:11px;font-weight:700;letter-spacing:1.5px;'
                     f'text-transform:uppercase;margin-bottom:8px;">'
                     f'<span style="color:{type_color};">{type_display}</span>'
                     f'<span style="color:{FAINT};"> &middot; {region_display}</span></div>')

        def label(text):
            return (f'<div style="{SANS}font-size:10.5px;font-weight:700;letter-spacing:1.2px;'
                    f'text-transform:uppercase;color:{FAINT};margin-bottom:5px;">{text}</div>')

        body_style = f'{SANS}font-size:15px;line-height:1.65;color:{INK};{NO_HYPHENS}'

        sources_html = ""
        from .source_display import dedupe_sources
        named_sources = dedupe_sources(story.sources)
        if named_sources:
            links = f'<span style="color:{FAINT};"> &middot; </span>'.join(
                f'<a href="{src}" style="color:{ACCENT};text-decoration:none;">{name}</a>'
                for src, name in named_sources
            )
            sources_html = (f'<div style="margin-top:16px;">{label("Sources")}'
                            f'<div style="{SANS}font-size:13.5px;line-height:1.7;">{links}</div></div>')

        return f"""<div style="margin-bottom:6px;">
  {meta_line}
  <h1 class="nl-h1" style="{SANS}font-size:26px;font-weight:800;letter-spacing:-0.3px;color:{INK};margin:0 0 14px 0;line-height:1.25;{NO_HYPHENS}">{story.story_title}</h1>
  <div style="margin-bottom:16px;">
    {label("Why This Matters")}
    <div style="{body_style}">{story.why_important}</div>
  </div>
  {mid_block}
  <div class="nl-box" style="margin-bottom:16px;background-color:{WASH};border-radius:6px;padding:12px 14px;">
    {label("What Others Are Missing")}
    <div style="{body_style}">{story.what_overlooked}</div>
  </div>
  <div style="margin-bottom:14px;">
    {label("What to Watch")}
    <div style="{body_style}">{story.prediction}</div>
  </div>
  {after_watch_block}
  {sources_html}
</div>"""
    def _email_grid_block(self, newsletter: Newsletter, INK: str, SUB: str,
                          FAINT: str, LINE: str, WASH: str, ACCENT: str, SANS: str) -> str:
        """How the World Covers It — inside the big story's flow."""
        grid = getattr(newsletter, 'perspective_grid', None)
        if not grid or not grid.counts:
            return ""
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"
        from ..perspectives import summarize_grid, GROUP_COLORS, label_of
        parts, legend = summarize_grid(grid)

        total = sum(p["count"] for p in parts) or 1
        bar = "".join(
            f'<span style="display:inline-block;width:{max(4, round(100 * p["count"] / total, 1))}%;'
            f'height:6px;background-color:{p["color"]};"></span>'
            for p in parts
        )

        rows = ""
        for view in grid.views:
            if not view.framing:
                continue
            color = GROUP_COLORS.get(view.perspective, "#6B7280")
            state = (f' <span style="{SANS}font-size:9px;font-weight:700;letter-spacing:0.5px;'
                     f'text-transform:uppercase;color:{SUB};border:1px solid {LINE};'
                     f'border-radius:3px;padding:1px 5px;">state media</span>') if view.state_affiliated else ""
            quote_html = ""
            if view.quote:
                outlet = view.quote_outlet or ""
                link = (f'<a href="{view.quote_url}" style="color:{ACCENT};text-decoration:none;">{outlet}</a>'
                        if view.quote_url else outlet)
                quote_html = (f'<div style="{SANS}font-size:13.5px;line-height:1.6;color:{SUB};'
                              f'border-left:2px solid {color};padding-left:10px;margin:5px 0 0 15px;{NO_HYPHENS}">'
                              f'&ldquo;{view.quote}&rdquo; &mdash; {link}</div>')
            rows += (f'<div style="margin-bottom:12px;{SANS}font-size:14px;'
                     f'line-height:1.6;color:{INK};{NO_HYPHENS}">'
                     f'<span style="color:{color};">&#9679;</span> '
                     f'<strong>{label_of(view.perspective)} ({view.article_count})</strong>{state}'
                     f' &mdash; <span style="color:{SUB};">{view.framing}</span>{quote_html}</div>')

        blindspot_html = ""
        if grid.blindspot:
            arrow = (f' <a href="{grid.blindspot_url}" style="color:{ACCENT};text-decoration:none;">&rarr;</a>'
                     if grid.blindspot_url else "")
            blindspot_html = (f'<div style="border-left:3px solid #B26B00;padding:2px 0 2px 12px;margin-top:14px;">'
                              f'<span style="{SANS}font-size:10px;font-weight:800;letter-spacing:1.5px;'
                              f'text-transform:uppercase;color:#B26B00;">Blindspot</span>'
                              f'<div style="{SANS}font-size:13.5px;line-height:1.6;color:{INK};'
                              f'margin-top:3px;{NO_HYPHENS}">{grid.blindspot}{arrow}</div></div>')

        return (f'<div style="margin:0 0 18px 0;border-top:1px solid {LINE};padding-top:14px;">'
                f'<div style="{SANS}font-size:10.5px;font-weight:700;letter-spacing:1.2px;'
                f'text-transform:uppercase;color:{FAINT};margin-bottom:8px;">How the World Covers It</div>'
                f'<div style="font-size:0;line-height:0;margin-bottom:6px;">{bar}</div>'
                f'<div style="{SANS}font-size:12px;color:{FAINT};margin-bottom:14px;">'
                f'{grid.total_outlets} outlets &middot; {legend}</div>'
                f'{rows}{blindspot_html}'
                f'<div style="border-bottom:1px solid {LINE};margin-top:16px;font-size:0;">&nbsp;</div></div>')
    def _email_signals_block(self, newsletter: Newsletter, SUB: str,
                             FAINT: str, ACCENT: str, SANS: str) -> str:
        """Signals — compact lines directly under What to Watch."""
        signals = getattr(newsletter, 'signals', None) or []
        if not signals:
            return ""
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"
        items = ""
        for signal in signals:
            arrow = (f' <a href="{signal.url}" style="color:{ACCENT};text-decoration:none;">&rarr;</a>'
                     if signal.url else "")
            items += (f'<div style="margin-bottom:5px;{SANS}font-size:13.5px;'
                      f'line-height:1.6;color:{SUB};{NO_HYPHENS}">'
                      f'<span style="color:{FAINT};">&#9656;</span> {signal.text}{arrow}</div>')
        return f'<div style="margin:-4px 0 14px 0;">{items}</div>'
    def _generate_email_extras_html(
        self, newsletter: Newsletter, INK: str, SUB: str, FAINT: str,
        LINE: str, ACCENT: str, SANS: str, kicker
    ) -> str:
        """Also Today (hairline list) + Big Number (centered) after the story."""
        NO_HYPHENS = "-webkit-hyphens:none;-ms-hyphens:none;hyphens:none;"
        html = ""
        if newsletter.quick_hits:
            items = ""
            for i, hit in enumerate(newsletter.quick_hits):
                region = hit.region.replace("_", " ").title()
                arrow = (f' <a href="{hit.url}" style="color:{ACCENT};text-decoration:none;">&rarr;</a>'
                         if hit.url else "")
                border = "" if i == len(newsletter.quick_hits) - 1 else f"border-bottom:1px solid {LINE};"
                items += (f'<div style="padding:9px 0;{border}{SANS}font-size:14.5px;'
                          f'line-height:1.6;color:{INK};{NO_HYPHENS}">'
                          f'<span style="font-size:10px;font-weight:800;text-transform:uppercase;'
                          f'letter-spacing:1px;color:{ACCENT};margin-right:7px;">{region}</span>'
                          f'{hit.text}{arrow}</div>')
            html += f'{kicker("Also Today")}<div style="margin-bottom:8px;">{items}</div>'
        if newsletter.big_number:
            bn = newsletter.big_number
            arrow = (f' <a href="{bn.url}" style="color:{ACCENT};text-decoration:none;">&rarr;</a>'
                     if bn.url else "")
            html += (f'{kicker("The Big Number")}'
                     f'<div style="text-align:center;margin:6px 0 10px 0;">'
                     f'<div class="nl-num" style="{SANS}font-size:54px;font-weight:800;'
                     f'letter-spacing:-1px;color:{INK};line-height:1.05;">{bn.value}</div>'
                     f'<div style="{SANS}font-size:14px;line-height:1.6;color:{SUB};'
                     f'margin-top:8px;{NO_HYPHENS}">{bn.context}{arrow}</div>'
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
