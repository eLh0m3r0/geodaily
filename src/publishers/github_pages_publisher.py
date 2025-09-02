"""
GitHub Pages publisher for the newsletter.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Newsletter, AIAnalysis
from ..metrics.dashboard_generator import DashboardGenerator
from ..sitemap_generator import SitemapGenerator
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
            # Check for duplicate newsletter (same date)
            date_str = newsletter.date.strftime('%Y-%m-%d')
            filename = f"newsletter-{date_str}.html"
            newsletter_path = self.output_dir / "newsletters" / filename

            if newsletter_path.exists():
                logger.warning(f"Newsletter for {date_str} already exists. Skipping publication to prevent duplicates.")
                # Still update site pages and return existing URL
                self._update_index_page()
                self._update_archive_page()
                self._update_about_page()
                self._update_rss_feed()
                self._update_dashboard()
                self._update_sitemap()
                self._copy_assets()

                relative_url = f"newsletters/{filename}"
                logger.info(f"Site pages updated, existing newsletter: {relative_url}")
                return relative_url

            # Generate newsletter HTML
            html_content = self._generate_newsletter_html(newsletter, analyses)

            # Save individual newsletter
            with open(newsletter_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Update all site pages
            self._update_index_page()
            self._update_archive_page()
            self._update_about_page()

            # Update RSS feed
            self._update_rss_feed()

            # Generate and update dashboard
            self._update_dashboard()

            # Generate sitemap and robots.txt
            self._update_sitemap()

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
                <a href="../dashboard.html">Dashboard</a>
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
                <a href="dashboard.html">Dashboard</a>
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

    def _update_archive_page(self):
        """Generate archive page with all published newsletters organized by month/year."""

        # Get all newsletters sorted by date (newest first)
        newsletters_dir = self.output_dir / "newsletters"
        newsletter_files = sorted(newsletters_dir.glob("newsletter-*.html"), reverse=True)

        # Group newsletters by year and month
        newsletters_by_period = {}
        for newsletter_file in newsletter_files:
            date_str = newsletter_file.stem.replace('newsletter-', '')
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                year_month = date_obj.strftime('%Y-%m')
                year = date_obj.strftime('%Y')
                month = date_obj.strftime('%B %Y')

                if year not in newsletters_by_period:
                    newsletters_by_period[year] = {}
                if year_month not in newsletters_by_period[year]:
                    newsletters_by_period[year][year_month] = {
                        'month_name': month,
                        'newsletters': []
                    }

                newsletters_by_period[year][year_month]['newsletters'].append({
                    'date': date_obj,
                    'filename': newsletter_file.name,
                    'formatted_date': date_obj.strftime('%B %d, %Y')
                })
            except ValueError:
                continue

        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archive - Geopolitical Daily</title>
    <meta name="description" content="Complete archive of Geopolitical Daily newsletters with strategic analysis">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">Strategic Intelligence Beyond the Headlines</p>
            <nav class="nav">
                <a href="index.html">Home</a>
                <a href="archive.html">Archive</a>
                <a href="about.html">About</a>
                <a href="dashboard.html">Dashboard</a>
                <a href="feed.xml">RSS</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="container">
            <h1>Newsletter Archive</h1>
            <p class="archive-intro">Browse our complete collection of geopolitical analysis newsletters, organized chronologically.</p>
"""

        # Generate archive sections by year
        for year in sorted(newsletters_by_period.keys(), reverse=True):
            html += f"""
            <section class="archive-year">
                <h2>{year}</h2>
"""

            for year_month in sorted(newsletters_by_period[year].keys(), reverse=True):
                month_data = newsletters_by_period[year][year_month]
                html += f"""
                <div class="archive-month">
                    <h3>{month_data['month_name']}</h3>
                    <div class="newsletter-list">
"""

                for newsletter in month_data['newsletters']:
                    html += f"""
                        <article class="newsletter-preview archive-item">
                            <h4><a href="newsletters/{newsletter['filename']}">{newsletter['formatted_date']} Edition</a></h4>
                            <p>Strategic analysis of geopolitical developments</p>
                        </article>
"""

                html += """
                    </div>
                </div>
"""

            html += """
            </section>
"""

        html += """
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p>
                <a href="feed.xml">RSS Feed</a> |
                <a href="index.html">Latest Newsletter</a> |
                <a href="https://github.com/yourusername/geodaily">Source Code</a>
            </p>
        </div>
    </footer>
</body>
</html>"""

        with open(self.output_dir / "archive.html", 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("Archive page updated")

    def _update_about_page(self):
        """Generate about page with project information."""

        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>About - Geopolitical Daily</title>
    <meta name="description" content="Learn about Geopolitical Daily - AI-powered strategic intelligence beyond the headlines">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">Strategic Intelligence Beyond the Headlines</p>
            <nav class="nav">
                <a href="index.html">Home</a>
                <a href="archive.html">Archive</a>
                <a href="about.html">About</a>
                <a href="dashboard.html">Dashboard</a>
                <a href="feed.xml">RSS</a>
            </nav>
        </div>
    </header>

    <main class="main">
        <div class="container">
            <section class="about-hero">
                <h1>About Geopolitical Daily</h1>
                <p class="about-intro">AI-powered analysis of underreported geopolitical developments with strategic significance</p>
            </section>

            <section class="about-content">
                <h2>Our Mission</h2>
                <p>Geopolitical Daily provides strategic intelligence that goes beyond headlines. We focus on underreported stories with significant geopolitical implications, using AI to analyze patterns and predict outcomes that mainstream media might overlook.</p>

                <h2>What Makes Us Different</h2>
                <div class="features-grid">
                    <div class="feature">
                        <h3>🤖 AI-Powered Analysis</h3>
                        <p>Advanced AI algorithms analyze thousands of sources to identify strategic patterns and implications</p>
                    </div>
                    <div class="feature">
                        <h3>🎯 Underreported Focus</h3>
                        <p>We identify stories that deserve attention but aren't getting mainstream coverage</p>
                    </div>
                    <div class="feature">
                        <h3>🔍 Strategic Depth</h3>
                        <p>Beyond headlines to second-order effects, regional power dynamics, and long-term implications</p>
                    </div>
                    <div class="feature">
                        <h3>🌍 Global Sources</h3>
                        <p>Drawing from think tanks, regional outlets, diplomatic cables, and specialized publications worldwide</p>
                    </div>
                    <div class="feature">
                        <h3>⚡ Daily Updates</h3>
                        <p>Fresh analysis delivered every day at 6:00 UTC, keeping you ahead of developing situations</p>
                    </div>
                    <div class="feature">
                        <h3>📊 Impact Scoring</h3>
                        <p>Each story is scored for strategic significance to help prioritize your attention</p>
                    </div>
                </div>

                <h2>How It Works</h2>
                <div class="process">
                    <div class="process-step">
                        <h3>1. Data Collection</h3>
                        <p>Our system continuously monitors geopolitical news from hundreds of sources worldwide</p>
                    </div>
                    <div class="process-step">
                        <h3>2. AI Analysis</h3>
                        <p>Claude AI analyzes articles for strategic significance, identifying underreported stories</p>
                    </div>
                    <div class="process-step">
                        <h3>3. Strategic Assessment</h3>
                        <p>Each story is evaluated for impact, overlooked aspects, and future implications</p>
                    </div>
                    <div class="process-step">
                        <h3>4. Daily Publication</h3>
                        <p>Curated analysis is published daily with clear impact scoring and source links</p>
                    </div>
                </div>

                <h2>Subscribe</h2>
                <div class="subscription-options">
                    <div class="subscription-option">
                        <h3>RSS Feed</h3>
                        <p>Get instant updates in your RSS reader</p>
                        <a href="feed.xml" class="cta-button">Subscribe via RSS</a>
                    </div>
                    <div class="subscription-option">
                        <h3>Email Notifications</h3>
                        <p>Receive email alerts when new analysis is published</p>
                        <p class="note">Coming soon - contact us to be notified when available</p>
                    </div>
                </div>

                <h2>Contact & Feedback</h2>
                <p>We welcome feedback on our analysis and suggestions for improvement. You can:</p>
                <ul>
                    <li><a href="https://github.com/yourusername/geodaily/issues">Open an issue on GitHub</a> for bug reports or feature requests</li>
                    <li><a href="https://github.com/yourusername/geodaily/discussions">Start a discussion</a> for analysis feedback</li>
                    <li>Check our <a href="https://github.com/yourusername/geodaily">source code</a> to understand our methodology</li>
                </ul>
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

        with open(self.output_dir / "about.html", 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("About page updated")
    
    def _update_rss_feed(self):
        """Generate enhanced RSS feed for subscribers with comprehensive metadata and content."""

        try:
            newsletters_dir = self.output_dir / "newsletters"
            newsletter_files = sorted(newsletters_dir.glob("newsletter-*.html"), reverse=True)

            rss_items = []
            for newsletter_file in newsletter_files[:20]:  # Last 20 newsletters
                try:
                    date_str = newsletter_file.stem.replace('newsletter-', '')
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

                    # Generate unique GUID based on date
                    guid = f"geodaily-{date_obj.strftime('%Y%m%d')}"

                    # Create enhanced item with proper content formatting
                    item_content = self._generate_rss_item(newsletter_file, date_obj, guid)
                    rss_items.append(item_content)

                except ValueError as e:
                    logger.warning(f"Failed to process newsletter file {newsletter_file.name}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing {newsletter_file.name}: {e}")
                    continue

            # Generate enhanced RSS feed with comprehensive metadata
            rss_content = self._generate_enhanced_rss_feed(rss_items)

            # Validate XML before writing
            if self._validate_rss_xml(rss_content):
                with open(self.output_dir / "feed.xml", 'w', encoding='utf-8') as f:
                    f.write(rss_content)
                logger.info("Enhanced RSS feed updated successfully")
            else:
                logger.error("RSS feed validation failed - feed not updated")
                raise ValueError("Generated RSS feed failed XML validation")

        except Exception as e:
            logger.error(f"Failed to update RSS feed: {e}")
            raise

    def _generate_rss_item(self, newsletter_file: Path, date_obj: datetime, guid: str) -> str:
        """Generate a comprehensive RSS item with enhanced metadata and content."""

        try:
            # Read newsletter HTML to extract content for RSS
            newsletter_content = self._extract_newsletter_content(newsletter_file)

            # Format title with date
            title = f"Geopolitical Daily - {date_obj.strftime('%B %d, %Y')}"

            # Create enhanced description with newsletter summary
            description = self._create_rss_description(newsletter_content, date_obj)

            # Generate categories based on content analysis
            categories = self._generate_categories(newsletter_content)

            # Build RSS item with all required and optional elements
            item_parts = [
                f"<item>",
                f"<title><![CDATA[{self._escape_for_cdata(title)}]]></title>",
                f"<link>https://yourusername.github.io/geodaily/newsletters/{newsletter_file.name}</link>",
                f"<description><![CDATA[{description}]]></description>",
                f"<pubDate>{date_obj.strftime('%a, %d %b %Y 06:00:00 GMT')}</pubDate>",
                f"<guid isPermaLink=\"false\">{guid}</guid>",
                f"<author>Geopolitical Daily Editorial Team</author>",
            ]

            # Add categories
            for category in categories:
                item_parts.append(f"<category><![CDATA[{self._escape_for_cdata(category)}]]></category>")

            # Add additional metadata
            item_parts.extend([
                f"<comments>https://yourusername.github.io/geodaily/newsletters/{newsletter_file.name}#comments</comments>",
                f"<source url=\"https://yourusername.github.io/geodaily/feed.xml\">Geopolitical Daily</source>",
            ])

            item_parts.append("</item>")

            return "\n        ".join(item_parts)

        except Exception as e:
            logger.error(f"Failed to generate RSS item for {newsletter_file.name}: {e}")
            # Return basic item as fallback
            return f"""
        <item>
            <title><![CDATA[{self._escape_for_cdata(title)}]]></title>
            <link>https://yourusername.github.io/geodaily/newsletters/{newsletter_file.name}</link>
            <description><![CDATA[Daily geopolitical analysis focusing on underreported stories with strategic significance]]></description>
            <pubDate>{date_obj.strftime('%a, %d %b %Y 06:00:00 GMT')}</pubDate>
            <guid isPermaLink="false">{guid}</guid>
        </item>"""

    def _extract_newsletter_content(self, newsletter_file: Path) -> dict:
        """Extract relevant content from newsletter HTML for RSS generation."""

        try:
            with open(newsletter_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Simple content extraction (could be enhanced with BeautifulSoup)
            content = {
                'stories': [],
                'intro': '',
                'highlights': []
            }

            # Extract story titles and content (basic regex-based extraction)
            import re

            # Find story sections
            story_pattern = r'<section class="story"[^>]*>.*?<h2[^>]*>(.*?)</h2>.*?<p>(.*?)</p>.*?</section>'
            stories = re.findall(story_pattern, html_content, re.DOTALL | re.IGNORECASE)

            for title, summary in stories[:5]:  # Limit to top 5 stories
                content['stories'].append({
                    'title': self._clean_html_text(title),
                    'summary': self._clean_html_text(summary)[:200] + "..." if len(self._clean_html_text(summary)) > 200 else self._clean_html_text(summary)
                })

            # Extract intro text
            intro_pattern = r'<p class="newsletter-intro">(.*?)</p>'
            intro_match = re.search(intro_pattern, html_content, re.DOTALL | re.IGNORECASE)
            if intro_match:
                content['intro'] = self._clean_html_text(intro_match.group(1))

            return content

        except Exception as e:
            logger.warning(f"Failed to extract content from {newsletter_file.name}: {e}")
            return {'stories': [], 'intro': '', 'highlights': []}

    def _create_rss_description(self, content: dict, date_obj: datetime) -> str:
        """Create comprehensive RSS description from newsletter content."""

        try:
            description_parts = []

            # Add intro if available
            if content.get('intro'):
                description_parts.append(f"<p><strong>Daily Briefing:</strong> {content['intro']}</p>")

            # Add key stories
            if content.get('stories'):
                description_parts.append("<h3>Today's Key Stories:</h3><ul>")
                for story in content['stories'][:3]:  # Top 3 stories
                    description_parts.append(f"<li><strong>{story['title']}</strong>: {story['summary']}</li>")
                description_parts.append("</ul>")

            # Add metadata
            description_parts.append(f"<p><em>Published: {date_obj.strftime('%B %d, %Y')}</em></p>")
            description_parts.append("<p>Strategic analysis of underreported geopolitical developments with significant implications.</p>")

            return "".join(description_parts)

        except Exception as e:
            logger.warning(f"Failed to create RSS description: {e}")
            return "Daily geopolitical analysis focusing on underreported stories with strategic significance"

    def _generate_categories(self, content: dict) -> list:
        """Generate RSS categories based on newsletter content."""

        categories = ["Geopolitics", "Strategic Analysis", "International Relations"]

        try:
            # Analyze content for specific categories
            all_text = " ".join([
                content.get('intro', ''),
                " ".join([story.get('title', '') + " " + story.get('summary', '') for story in content.get('stories', [])])
            ]).lower()

            # Add specific categories based on content keywords
            if any(keyword in all_text for keyword in ['china', 'beijing', 'xi', 'taiwan']):
                categories.append("China")
            if any(keyword in all_text for keyword in ['russia', 'moscow', 'putin', 'ukraine']):
                categories.append("Russia")
            if any(keyword in all_text for keyword in ['middle east', 'iran', 'saudi', 'israel']):
                categories.append("Middle East")
            if any(keyword in all_text for keyword in ['united states', 'america', 'washington', 'biden']):
                categories.append("United States")
            if any(keyword in all_text for keyword in ['europe', 'eu', 'nato', 'brexit']):
                categories.append("Europe")
            if any(keyword in all_text for keyword in ['economy', 'trade', 'finance', 'market']):
                categories.append("Economy")
            if any(keyword in all_text for keyword in ['military', 'defense', 'security', 'conflict']):
                categories.append("Security")

        except Exception as e:
            logger.warning(f"Failed to generate categories: {e}")

        return categories[:10]  # Limit to 10 categories

    def _generate_enhanced_rss_feed(self, rss_items: list) -> str:
        """Generate enhanced RSS feed with comprehensive metadata."""

        now = datetime.now()

        rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel>
        <title><![CDATA[Geopolitical Daily - Strategic Intelligence Beyond the Headlines]]></title>
        <link>https://yourusername.github.io/geodaily/</link>
        <atom:link href="https://yourusername.github.io/geodaily/feed.xml" rel="self" type="application/rss+xml" />
        <description><![CDATA[AI-powered analysis of underreported geopolitical developments with strategic significance. Daily insights on international relations, security, and global power dynamics.]]></description>
        <language>en-us</language>
        <managingEditor>editor@geodaily.example.com (Geopolitical Daily Editorial Team)</managingEditor>
        <webMaster>tech@geodaily.example.com (Geopolitical Daily Tech Team)</webMaster>
        <pubDate>{now.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
        <lastBuildDate>{now.strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
        <generator>Geopolitical Daily Newsletter System v2.0</generator>
        <docs>https://www.rssboard.org/rss-specification</docs>
        <ttl>60</ttl>

        <!-- Feed optimization -->
        <skipHours>
            <hour>1</hour>
            <hour>2</hour>
            <hour>3</hour>
            <hour>4</hour>
            <hour>5</hour>
            <hour>7</hour>
            <hour>8</hour>
            <hour>9</hour>
            <hour>10</hour>
            <hour>11</hour>
            <hour>12</hour>
            <hour>13</hour>
            <hour>14</hour>
            <hour>15</hour>
            <hour>16</hour>
            <hour>17</hour>
            <hour>18</hour>
            <hour>19</hour>
            <hour>20</hour>
            <hour>21</hour>
            <hour>22</hour>
            <hour>23</hour>
        </skipHours>

        <skipDays>
            <day>Saturday</day>
            <day>Sunday</day>
        </skipDays>

        <!-- Dublin Core metadata -->
        <dc:creator>Geopolitical Daily Editorial Team</dc:creator>
        <dc:publisher>Geopolitical Daily</dc:publisher>
        <dc:language>en-US</dc:language>
        <dc:rights>© 2025 Geopolitical Daily. All rights reserved.</dc:rights>

        <!-- Image for feed readers that support it -->
        <image>
            <url>https://yourusername.github.io/geodaily/assets/logo.png</url>
            <title>Geopolitical Daily</title>
            <link>https://yourusername.github.io/geodaily/</link>
            <description>Strategic Intelligence Beyond the Headlines</description>
        </image>

        {''.join(rss_items)}
    </channel>
</rss>"""

        return rss_content

    def _validate_rss_xml(self, rss_content: str) -> bool:
        """Validate RSS XML structure and content."""

        try:
            import xml.etree.ElementTree as ET
            from xml.etree.ElementTree import ParseError

            # Parse XML to check for well-formedness
            root = ET.fromstring(rss_content)

            # Basic validation checks
            if root.tag != 'rss':
                logger.error("Root element is not 'rss'")
                return False

            if root.get('version') != '2.0':
                logger.error("RSS version is not 2.0")
                return False

            channel = root.find('channel')
            if channel is None:
                logger.error("No channel element found")
                return False

            # Check required channel elements
            required_elements = ['title', 'link', 'description']
            for elem in required_elements:
                if channel.find(elem) is None:
                    logger.error(f"Required channel element '{elem}' missing")
                    return False

            # Check items
            items = channel.findall('item')
            if not items:
                logger.warning("No items found in RSS feed")
                # This is not a fatal error for validation

            logger.info("RSS XML validation passed")
            return True

        except ParseError as e:
            logger.error(f"RSS XML parsing error: {e}")
            return False
        except Exception as e:
            logger.error(f"RSS validation error: {e}")
            return False

    def _escape_for_cdata(self, text: str) -> str:
        """Escape text for use within CDATA sections."""

        if not text:
            return ""

        # CDATA sections handle most characters, but we should escape ]]>
        # which would prematurely end the CDATA section
        return text.replace("]]>", "]]]]><![CDATA[>")

    def _clean_html_text(self, html_text: str) -> str:
        """Clean HTML tags from text for plain text extraction."""

        try:
            import re
            # Remove HTML tags
            clean_text = re.sub(r'<[^>]+>', '', html_text)
            # Decode HTML entities
            import html
            clean_text = html.unescape(clean_text)
            # Clean up whitespace
            clean_text = ' '.join(clean_text.split())
            return clean_text
        except Exception as e:
            logger.warning(f"Failed to clean HTML text: {e}")
            return html_text
    
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

/* Archive page specific */
.archive-intro {
    font-size: 1.1rem;
    color: var(--text-light);
    margin-bottom: 2rem;
    text-align: center;
}

.archive-year {
    margin-bottom: 3rem;
}

.archive-year h2 {
    color: var(--primary-color);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 0.5rem;
    margin-bottom: 2rem;
}

.archive-month {
    margin-bottom: 2rem;
}

.archive-month h3 {
    color: var(--secondary-color);
    font-size: 1.2rem;
    margin-bottom: 1rem;
}

.archive-item {
    padding: 1rem 1.5rem;
    margin-bottom: 0.5rem;
}

.archive-item h4 {
    margin-bottom: 0.25rem;
    font-size: 1rem;
}

.archive-item h4 a {
    color: var(--primary-color);
    text-decoration: none;
}

.archive-item h4 a:hover {
    text-decoration: underline;
}

.archive-item p {
    font-size: 0.9rem;
    color: var(--text-light);
    margin: 0;
}

/* About page specific */
.about-hero {
    text-align: center;
    margin-bottom: 3rem;
    padding: 2rem 0;
}

.about-hero h1 {
    color: var(--primary-color);
    margin-bottom: 1rem;
}

.about-intro {
    font-size: 1.2rem;
    color: var(--text-light);
    max-width: 600px;
    margin: 0 auto;
}

.about-content h2 {
    color: var(--primary-color);
    margin: 2rem 0 1rem 0;
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 0.5rem;
}

.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.feature {
    background: var(--bg-light);
    padding: 1.5rem;
    border-radius: 8px;
    border-left: 4px solid var(--accent-color);
}

.feature h3 {
    color: var(--primary-color);
    margin-bottom: 0.5rem;
    font-size: 1.1rem;
}

.feature p {
    margin: 0;
    line-height: 1.6;
}

.process {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.process-step {
    background: var(--bg-light);
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
}

.process-step h3 {
    color: var(--primary-color);
    margin-bottom: 0.5rem;
    font-size: 1.1rem;
}

.process-step p {
    margin: 0;
    line-height: 1.6;
}

.subscription-options {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
    margin: 2rem 0;
}

.subscription-option {
    background: var(--bg-light);
    padding: 2rem;
    border-radius: 8px;
    text-align: center;
}

.subscription-option h3 {
    color: var(--primary-color);
    margin-bottom: 1rem;
}

.subscription-option p {
    margin-bottom: 1rem;
    line-height: 1.6;
}

.note {
    font-style: italic;
    color: var(--text-light);
    font-size: 0.9rem;
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
    
    def _update_dashboard(self):
        """Generate and update the metrics dashboard."""
        try:
            dashboard_generator = DashboardGenerator()
            dashboard_path = self.output_dir / "dashboard.html"
            dashboard_generator.generate_dashboard(str(dashboard_path))
            logger.info("Dashboard updated with latest metrics")
        except Exception as e:
            logger.error(f"Failed to update dashboard: {e}")

    def _update_sitemap(self):
        """Generate and update sitemap and robots.txt."""
        try:
            sitemap_generator = SitemapGenerator(str(self.output_dir))
            sitemap_path = sitemap_generator.generate_sitemap()
            logger.info(f"Sitemap updated: {sitemap_path}")
        except Exception as e:
            logger.error(f"Failed to update sitemap: {e}")
            # Don't raise exception to avoid breaking the publishing process

    def get_stats(self) -> dict:
        """Get publishing statistics."""
        newsletters_dir = self.output_dir / "newsletters"
        newsletter_count = len(list(newsletters_dir.glob("newsletter-*.html")))

        return {
            "total_newsletters": newsletter_count,
            "output_directory": str(self.output_dir),
            "last_updated": datetime.now().isoformat()
        }