"""
GitHub Pages publisher for the newsletter.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Newsletter, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

class GitHubPagesPublisher:
    """Publishes newsletters to GitHub Pages site."""
    
    def __init__(self, output_dir: str = "docs"):
        """Initialize GitHub Pages publisher."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create necessary subdirectories
        (self.output_dir / "newsletters").mkdir(exist_ok=True)
        (self.output_dir / "assets").mkdir(exist_ok=True)
        
        logger.info(f"GitHub Pages publisher initialized: {self.output_dir}")
    
    def publish_newsletter(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> str:
        """
        Publish newsletter to GitHub Pages.
        
        Args:
            newsletter: Newsletter data
            analyses: AI analysis results
            
        Returns:
            URL of published newsletter
        """
        try:
            # Generate newsletter HTML
            html_content = self._generate_newsletter_html(newsletter, analyses)
            
            # Save individual newsletter
            date_str = newsletter.date.strftime('%Y-%m-%d')
            filename = f"newsletter-{date_str}.html"
            newsletter_path = self.output_dir / "newsletters" / filename
            
            with open(newsletter_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Update index page
            self._update_index_page()
            
            # Update RSS feed
            self._update_rss_feed()
            
            # Copy CSS assets
            self._copy_assets()
            
            relative_url = f"newsletters/{filename}"
            logger.info(f"Newsletter published to: {relative_url}")
            
            return relative_url
            
        except Exception as e:
            logger.error(f"Failed to publish newsletter: {e}")
            raise
    
    def _generate_newsletter_html(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> str:
        """Generate HTML content for newsletter."""
        
        # Header
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{newsletter.title} - {newsletter.date.strftime('%B %d, %Y')}</title>
    <meta name="description" content="Daily geopolitical analysis focusing on underreported stories with strategic significance">
    <link rel="stylesheet" href="../assets/style.css">
    <link rel="canonical" href="https://yourusername.github.io/geodaily/newsletters/newsletter-{newsletter.date.strftime('%Y-%m-%d')}.html">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">Strategic Intelligence Beyond the Headlines</p>
            <nav class="nav">
                <a href="../index.html">Home</a>
                <a href="../archive.html">Archive</a>
                <a href="../about.html">About</a>
                <a href="../feed.xml">RSS</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="container">
            <article class="newsletter">
                <header class="newsletter-header">
                    <h1 class="newsletter-title">{newsletter.title}</h1>
                    <time class="newsletter-date" datetime="{newsletter.date.isoformat()}">{newsletter.date.strftime('%B %d, %Y')}</time>
                    <p class="newsletter-intro">{newsletter.intro_text or "Today's edition focuses on underreported geopolitical developments with significant strategic implications."}</p>
                </header>

                <div class="stories">
"""
        
        # Stories
        for i, analysis in enumerate(analyses, 1):
            impact_class = self._get_impact_class(analysis.impact_score)
            
            html += f"""
                    <section class="story" id="story-{i}">
                        <header class="story-header">
                            <h2 class="story-title">{analysis.story_title}</h2>
                            <div class="story-meta">
                                <span class="impact-score impact-{impact_class}" title="Impact Score">{analysis.impact_score}/10</span>
                                <span class="confidence" title="Analysis Confidence">{int(analysis.confidence * 100)}%</span>
                            </div>
                        </header>

                        <div class="story-content">
                            <div class="analysis-section">
                                <h3>Why This Matters</h3>
                                <p>{analysis.why_important}</p>
                            </div>

                            <div class="analysis-section">
                                <h3>What Others Are Missing</h3>
                                <p>{analysis.what_overlooked}</p>
                            </div>

                            <div class="analysis-section">
                                <h3>What to Watch</h3>
                                <p>{analysis.prediction}</p>
                            </div>

                            <div class="sources">
                                <h4>Sources</h4>
                                <ul>"""
            
            for url in analysis.sources[:3]:  # Limit to 3 sources for readability
                html += f'                                    <li><a href="{url}" target="_blank">{self._extract_domain(url)}</a></li>\n'
            
            html += """                                </ul>
                            </div>
                        </div>
                    </section>
"""
        
        # Footer
        html += f"""
                </div>

                <footer class="newsletter-footer">
                    <p>{newsletter.footer_text or 'This newsletter is generated using AI analysis of geopolitical news sources.'}</p>
                    <p class="timestamp">Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}</p>
                </footer>
            </article>
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p>
                <a href="../feed.xml">RSS Feed</a> |
                <a href="../archive.html">Archive</a> |
                <a href="https://github.com/yourusername/geodaily">Source Code</a>
            </p>
        </div>
    </footer>
</body>
</html>"""
        
        return html
    
    def _get_impact_class(self, score: int) -> str:
        """Get CSS class based on impact score."""
        if score >= 8:
            return "high"
        elif score >= 6:
            return "medium"
        else:
            return "low"
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for display."""
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc
            return domain.replace('www.', '')
        except:
            return url[:50] + "..." if len(url) > 50 else url
    
    def _update_index_page(self):
        """Update the main index page with recent newsletters."""
        
        # Get list of newsletters sorted by date (newest first)
        newsletters_dir = self.output_dir / "newsletters"
        newsletter_files = sorted(newsletters_dir.glob("newsletter-*.html"), reverse=True)
        
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geopolitical Daily - Strategic Intelligence Beyond the Headlines</title>
    <meta name="description" content="Daily geopolitical analysis focusing on underreported stories with strategic significance">
    <link rel="stylesheet" href="assets/style.css">
    <link rel="alternate" type="application/rss+xml" title="Geopolitical Daily RSS" href="feed.xml">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">Strategic Intelligence Beyond the Headlines</p>
            <p class="description">AI-powered analysis of underreported geopolitical developments with strategic significance</p>
            <nav class="nav">
                <a href="index.html">Home</a>
                <a href="archive.html">Archive</a>
                <a href="about.html">About</a>
                <a href="feed.xml">RSS</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="container">
            <section class="recent-newsletters">
                <h2>Recent Newsletters</h2>
                <div class="newsletter-list">
"""
        
        # Add recent newsletters (last 10)
        for newsletter_file in newsletter_files[:10]:
            date_str = newsletter_file.stem.replace('newsletter-', '')
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%B %d, %Y')
                
                html += f"""
                    <article class="newsletter-preview">
                        <h3><a href="newsletters/{newsletter_file.name}">{formatted_date} Edition</a></h3>
                        <p class="newsletter-date">{formatted_date}</p>
                        <p>Strategic analysis of today's most significant underreported geopolitical developments.</p>
                    </article>
"""
            except ValueError:
                continue
        
        html += """
                </div>
            </section>

            <section class="about-section">
                <h2>About This Newsletter</h2>
                <p>Geopolitical Daily provides AI-powered analysis of underreported stories with strategic significance. Our focus is on second-order effects, regional power dynamics, and developments that mainstream media might overlook.</p>
                
                <h3>What Makes Us Different</h3>
                <ul>
                    <li><strong>Underreported Focus:</strong> We identify stories that deserve more attention</li>
                    <li><strong>Strategic Analysis:</strong> Beyond headlines to implications and predictions</li>
                    <li><strong>Multiple Sources:</strong> Drawing from think tanks, regional outlets, and specialized publications</li>
                    <li><strong>Daily Updates:</strong> Fresh analysis every day at 6:00 UTC</li>
                </ul>
                
                <p><a href="feed.xml" class="cta-button">Subscribe via RSS</a></p>
            </section>
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p>
                <a href="feed.xml">RSS Feed</a> |
                <a href="archive.html">Archive</a> |
                <a href="https://github.com/yourusername/geodaily">Source Code</a>
            </p>
        </div>
    </footer>
</body>
</html>"""
        
        with open(self.output_dir / "index.html", 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info("Index page updated")
    
    def _update_rss_feed(self):
        """Generate RSS feed for subscribers."""
        
        newsletters_dir = self.output_dir / "newsletters" 
        newsletter_files = sorted(newsletters_dir.glob("newsletter-*.html"), reverse=True)
        
        rss_items = []
        for newsletter_file in newsletter_files[:20]:  # Last 20 newsletters
            date_str = newsletter_file.stem.replace('newsletter-', '')
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                
                rss_items.append(f"""
        <item>
            <title>Geopolitical Daily - {date_obj.strftime('%B %d, %Y')}</title>
            <link>https://yourusername.github.io/geodaily/newsletters/{newsletter_file.name}</link>
            <description>Daily geopolitical analysis focusing on underreported stories with strategic significance</description>
            <pubDate>{date_obj.strftime('%a, %d %b %Y 06:00:00 GMT')}</pubDate>
            <guid>https://yourusername.github.io/geodaily/newsletters/{newsletter_file.name}</guid>
        </item>""")
            except ValueError:
                continue
        
        rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Geopolitical Daily</title>
        <link>https://yourusername.github.io/geodaily/</link>
        <description>Strategic Intelligence Beyond the Headlines - AI-powered analysis of underreported geopolitical developments</description>
        <language>en-us</language>
        <pubDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
        <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
        <generator>Geopolitical Daily Newsletter System</generator>
        {''.join(rss_items)}
    </channel>
</rss>"""
        
        with open(self.output_dir / "feed.xml", 'w', encoding='utf-8') as f:
            f.write(rss_content)
        
        logger.info("RSS feed updated")
    
    def _copy_assets(self):
        """Copy CSS and other assets to output directory."""
        
        css_content = """/* Geopolitical Daily Newsletter Styles */

:root {
    --primary-color: #1a365d;
    --secondary-color: #2d3748;
    --accent-color: #3182ce;
    --text-color: #2d3748;
    --text-light: #4a5568;
    --border-color: #e2e8f0;
    --bg-light: #f7fafc;
    --impact-high: #e53e3e;
    --impact-medium: #dd6b20;
    --impact-low: #38a169;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
    color: var(--text-color);
    background: white;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 20px;
}

/* Header */
.header {
    background: var(--primary-color);
    color: white;
    padding: 2rem 0;
    text-align: center;
}

.site-title {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}

.tagline {
    font-size: 1.2rem;
    margin-bottom: 0.5rem;
    opacity: 0.9;
}

.description {
    font-size: 1rem;
    opacity: 0.8;
    margin-bottom: 1rem;
}

.nav {
    margin-top: 1rem;
}

.nav a {
    color: white;
    text-decoration: none;
    margin: 0 1rem;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    transition: background 0.3s;
}

.nav a:hover {
    background: rgba(255,255,255,0.1);
}

/* Main content */
.main {
    padding: 2rem 0;
}

/* Newsletter */
.newsletter {
    background: white;
    border-radius: 8px;
    overflow: hidden;
}

.newsletter-header {
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 2rem;
    border-bottom: 2px solid var(--border-color);
}

.newsletter-title {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}

.newsletter-date {
    color: var(--text-light);
    font-size: 1.1rem;
    margin-bottom: 1rem;
    display: block;
}

.newsletter-intro {
    font-size: 1.1rem;
    color: var(--text-light);
    max-width: 600px;
    margin: 0 auto;
}

/* Stories */
.stories {
    display: grid;
    gap: 2rem;
}

.story {
    background: var(--bg-light);
    border-radius: 8px;
    padding: 2rem;
    border-left: 4px solid var(--accent-color);
}

.story-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.5rem;
    gap: 1rem;
}

.story-title {
    font-size: 1.5rem;
    font-weight: 600;
    flex: 1;
}

.story-meta {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
}

.impact-score {
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.9rem;
    color: white;
}

.impact-high { background: var(--impact-high); }
.impact-medium { background: var(--impact-medium); }
.impact-low { background: var(--impact-low); }

.confidence {
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    background: var(--secondary-color);
    color: white;
    font-size: 0.9rem;
}

.story-content {
    display: grid;
    gap: 1.5rem;
}

.analysis-section h3 {
    color: var(--primary-color);
    font-size: 1.1rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
}

.analysis-section p {
    line-height: 1.7;
}

.sources h4 {
    color: var(--primary-color);
    font-size: 1rem;
    margin-bottom: 0.5rem;
}

.sources ul {
    list-style: none;
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
}

.sources a {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.9rem;
}

.sources a:hover {
    text-decoration: underline;
}

/* Newsletter footer */
.newsletter-footer {
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 2px solid var(--border-color);
    text-align: center;
    color: var(--text-light);
    font-size: 0.9rem;
}

.timestamp {
    margin-top: 0.5rem;
    font-size: 0.8rem;
    opacity: 0.7;
}

/* Site footer */
.site-footer {
    background: var(--secondary-color);
    color: white;
    padding: 2rem 0;
    text-align: center;
    margin-top: 3rem;
}

.site-footer a {
    color: white;
    text-decoration: none;
}

.site-footer a:hover {
    text-decoration: underline;
}

/* Home page specific */
.recent-newsletters {
    margin-bottom: 3rem;
}

.newsletter-list {
    display: grid;
    gap: 1rem;
}

.newsletter-preview {
    background: var(--bg-light);
    padding: 1.5rem;
    border-radius: 8px;
    border-left: 4px solid var(--accent-color);
}

.newsletter-preview h3 {
    margin-bottom: 0.5rem;
}

.newsletter-preview h3 a {
    color: var(--primary-color);
    text-decoration: none;
}

.newsletter-preview h3 a:hover {
    text-decoration: underline;
}

.newsletter-preview .newsletter-date {
    color: var(--text-light);
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
}

.about-section {
    background: var(--bg-light);
    padding: 2rem;
    border-radius: 8px;
}

.about-section h2, .about-section h3 {
    color: var(--primary-color);
    margin-bottom: 1rem;
}

.about-section ul {
    margin: 1rem 0;
    padding-left: 1.5rem;
}

.about-section li {
    margin-bottom: 0.5rem;
}

.cta-button {
    display: inline-block;
    background: var(--accent-color);
    color: white !important;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 600;
    margin-top: 1rem;
    transition: background 0.3s;
}

.cta-button:hover {
    background: var(--primary-color);
}

/* Responsive design */
@media (max-width: 768px) {
    .container {
        padding: 0 15px;
    }
    
    .story-header {
        flex-direction: column;
        align-items: flex-start;
    }
    
    .story-meta {
        align-self: flex-end;
    }
    
    .site-title {
        font-size: 2rem;
    }
    
    .sources ul {
        flex-direction: column;
        gap: 0.5rem;
    }
}"""
        
        assets_dir = self.output_dir / "assets"
        with open(assets_dir / "style.css", 'w', encoding='utf-8') as f:
            f.write(css_content)
        
        logger.info("Assets copied")
    
    def get_stats(self) -> dict:
        """Get publishing statistics."""
        newsletters_dir = self.output_dir / "newsletters"
        newsletter_count = len(list(newsletters_dir.glob("newsletter-*.html")))
        
        return {
            "total_newsletters": newsletter_count,
            "output_directory": str(self.output_dir),
            "last_updated": datetime.now().isoformat()
        }