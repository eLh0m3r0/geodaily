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
from .newsletter_archive_manager import NewsletterArchiveManager

logger = get_logger(__name__)

class GitHubPagesPublisher:
    """Publishes newsletters to GitHub Pages site."""

    SITE_BASE_URL = Config.SITE_BASE_URL.rstrip("/")
    GITHUB_REPO_URL = Config.GITHUB_REPO_URL.rstrip("/")

    def __init__(self, output_dir: str = "docs", max_newsletters: int = 10):
        """Initialize GitHub Pages publisher."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize newsletter archive manager
        self.archive_manager = NewsletterArchiveManager(output_dir, max_newsletters)
        
        # Create necessary subdirectories
        (self.output_dir / "newsletters").mkdir(exist_ok=True)
        (self.output_dir / "assets").mkdir(exist_ok=True)
        
        logger.info(f"GitHub Pages publisher initialized: {self.output_dir}, max_newsletters: {max_newsletters}")
    
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

            # Use Archive Manager to add newsletter (handles rotation automatically)
            newsletter_path = self.archive_manager.add_newsletter(html_content, newsletter.date)

            logger.info(f"Newsletter added to archive: {newsletter_path}")

            # Persist the machine-readable issue (feeds the weekly digest and
            # story pages) and drop JSONs for rotated-out issues
            try:
                from ..newsletter.issue_store import save_issue_json, prune_orphaned_json
                save_issue_json(newsletter, self.output_dir / "newsletters")
                prune_orphaned_json(self.output_dir / "newsletters")
            except Exception as e:
                logger.warning(f"Issue JSON persistence failed: {e}")

            # Evergreen per-story SEO page with the perspective grid
            try:
                self._publish_story_page(newsletter, analyses)
            except Exception as e:
                logger.warning(f"Story page generation failed: {e}")

            # Update all site pages with archive-aware content
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

            # Extract filename for return URL
            filename = Path(newsletter_path).name
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
    <meta name="description" content="World news from every side: how Western, Asian, Middle Eastern, African and Latin American media cover the same stories - every source linked, state media labeled.">
    <link rel="stylesheet" href="../assets/style.css">
    <link rel="canonical" href="{self.SITE_BASE_URL}/newsletters/newsletter-{newsletter.date.strftime('%Y-%m-%d')}.html">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">{Config.NEWSLETTER_TAGLINE}</p>
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
        
        # Stories — grid and signals render inside the big story's flow
        grid_block = self._build_grid_html(newsletter)
        signals_block = self._build_signals_html(newsletter)
        for i, analysis in enumerate(analyses, 1):
            if i == 1:
                html += '                    <div class="section-label">The Big Story</div>\n'
            html += f"""
                    <section class="story" id="story-{i}">
                        <header class="story-header">
                            <h2 class="story-title">{analysis.story_title}</h2>
                            <div class="story-meta">
                                <span class="geo-tag region-tag">{getattr(analysis, 'region', 'global').replace('_', ' ').title()}</span>
                                <span class="geo-tag event-tag">{getattr(analysis, 'event_type', 'political').replace('_', ' ').title()}</span>
                            </div>
                        </header>

                        <div class="story-content">
                            <div class="analysis-section">
                                <h3>Why This Matters</h3>
                                <p>{analysis.why_important}</p>
                            </div>

                            {grid_block if i == 1 else ""}

                            <div class="analysis-section">
                                <h3>What Others Are Missing</h3>
                                <p>{analysis.what_overlooked}</p>
                            </div>

                            <div class="analysis-section">
                                <h3>What to Watch</h3>
                                <p>{analysis.prediction}</p>
                            </div>

                            {signals_block if i == 1 else ""}

                            <div class="sources">
                                <h4>Sources</h4>
                                <ul>"""
            
            from ..newsletter.source_display import dedupe_sources
            for url, name in dedupe_sources(analysis.sources, limit=4):
                html += f'                                    <li><a href="{url}" target="_blank" rel="noopener">{name}</a></li>\n'
            
            html += """                                </ul>
                            </div>
                        </div>
                    </section>
"""
        
        # Also Today roundup + Big Number
        html += self._build_extras_html(newsletter)

        # Footer
        html += f"""
                </div>

                <footer class="newsletter-footer">
                    <p>{newsletter.footer_text or 'Drafted with AI from the sources linked above, with human review. Spotted an error? Open an issue or reply to the email — a human reads every response.'}</p>
                    <p class="timestamp">Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M UTC')}</p>
                    {self._build_subscribe_html()}
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
                <a href="{self.GITHUB_REPO_URL}">Source Code</a>
            </p>
        </div>
    </footer>
</body>
</html>"""
        
        return html
    
    def _build_grid_html(self, newsletter: Newsletter) -> str:
        """How the World Covers It block (grid + blindspot) for page output."""
        grid = getattr(newsletter, 'perspective_grid', None)
        if not grid or not grid.counts:
            return ""
        from ..perspectives import summarize_grid, GROUP_COLORS, label_of
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
                            <div><span class="persp-name">{label_of(view.perspective)} ({view.article_count})</span>{state}
                            &mdash; {view.framing}{quote_html}</div>
                        </div>"""
        blindspot_html = ""
        if grid.blindspot:
            arrow = (f' <a href="{grid.blindspot_url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>'
                     if grid.blindspot_url else "")
            blindspot_html = f'<div class="blindspot">&#9888; <strong>Blindspot:</strong> {grid.blindspot}{arrow}</div>'
        return f"""
                    <div class="perspective-grid">
                        <h3 class="section-heading">How the World Covers It</h3>
                        <div class="coverage-bar">{bar_spans}</div>
                        <div class="coverage-legend">{grid.total_outlets} outlets &middot; {legend_html}</div>
                        {rows}
                        {blindspot_html}
                    </div>
"""

    def _build_signals_html(self, newsletter: Newsletter) -> str:
        """Signals lines under What to Watch."""
        signals = getattr(newsletter, 'signals', None) or []
        if not signals:
            return ""
        items = ""
        for signal in signals:
            arrow = (f' <a href="{signal.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>'
                     if signal.url else "")
            items += f'                        <li>{signal.text}{arrow}</li>\n'
        return f"""
                    <div class="signals-inline">
                        <ul class="quick-hits">
{items}                        </ul>
                    </div>
"""

    def _build_extras_html(self, newsletter: Newsletter) -> str:
        """Also Today roundup + Big Number after the stories.

        The perspective grid and signals render inside the big story instead.
        """
        html = ""
        quick_hits = getattr(newsletter, 'quick_hits', None) or []
        big_number = getattr(newsletter, 'big_number', None)
        if quick_hits:
            items = ""
            for hit in quick_hits:
                region = hit.region.replace("_", " ").title()
                arrow = f' <a href="{hit.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>' if hit.url else ""
                items += (f'                        <li><span class="quick-hit-region">{region}</span> '
                          f'{hit.text}{arrow}</li>\n')
            html += f"""
                    <section class="also-today">
                        <h2 class="section-label">Also Today</h2>
                        <ul class="quick-hits">
{items}                        </ul>
                    </section>
"""
        if big_number:
            arrow = f' <a href="{big_number.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>' if big_number.url else ""
            html += f"""
                    <section class="big-number">
                        <h2 class="section-label">The Big Number</h2>
                        <div class="big-number-value">{big_number.value}</div>
                        <p class="big-number-context">{big_number.context}{arrow}</p>
                    </section>
"""
        return html

    def _publish_story_page(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> Optional[str]:
        """Write an evergreen per-story SEO page for the big story.

        Unlike the newsletter archive (rotated, max N issues), story pages
        accumulate: each carries the perspective grid — content no other
        outlet publishes — which is the SEO play.
        """
        if not analyses:
            return None
        from ..newsletter.issue_store import story_slug
        story = analyses[0]
        date_str = newsletter.date.strftime('%Y-%m-%d')
        slug = f"{date_str}-{story_slug(story.story_title)}"
        stories_dir = self.output_dir / "stories"
        stories_dir.mkdir(exist_ok=True)

        from ..newsletter.source_display import dedupe_sources
        sources_html = "".join(
            f'<li><a href="{url}" target="_blank" rel="noopener">{name}</a></li>\n'
            for url, name in dedupe_sources(story.sources, limit=4)
        )
        description = (story.why_important or "")[:155].replace('"', "'")

        grid_html = self._build_grid_html(newsletter)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{story.story_title} - {newsletter.title}</title>
    <meta name="description" content="{description}">
    <link rel="stylesheet" href="../assets/style.css">
    <link rel="canonical" href="{self.SITE_BASE_URL}/stories/{slug}.html">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">{newsletter.title}</h1>
            <p class="tagline">{Config.NEWSLETTER_TAGLINE}</p>
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
                    <h1 class="newsletter-title">{story.story_title}</h1>
                    <time class="newsletter-date" datetime="{newsletter.date.isoformat()}">{newsletter.date.strftime('%B %d, %Y')}</time>
                </header>
                <div class="stories">
                    <section class="story">
                        <div class="story-content">
                            <div class="analysis-section"><h3>Why This Matters</h3><p>{story.why_important}</p></div>
                            <div class="analysis-section"><h3>What Others Are Missing</h3><p>{story.what_overlooked}</p></div>
                            <div class="analysis-section"><h3>What to Watch</h3><p>{story.prediction}</p></div>
                            <div class="sources"><h4>Sources</h4><ul>{sources_html}</ul></div>
                        </div>
                    </section>
{grid_html}
                </div>
                <footer class="newsletter-footer">
                    <p>From the <a href="../newsletters/newsletter-{date_str}.html">{newsletter.date.strftime('%B %d, %Y')} edition</a> of {newsletter.title}.</p>
                    {self._build_subscribe_html()}
                </footer>
            </article>
        </div>
    </main>
</body>
</html>"""
        path = stories_dir / f"{slug}.html"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Story page published: stories/{slug}.html")
        return f"stories/{slug}.html"

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

    def _build_subscribe_html(self) -> str:
        """Build subscribe CTA HTML — Substack preferred, falls back to Buttondown."""
        substack_url = Config.SUBSTACK_URL
        if substack_url:
            return f"""
                    <div class="subscribe-box">
                        <h3>Get this briefing in your inbox</h3>
                        <p>Daily geopolitical intelligence, delivered every morning.</p>
                        <a href="{substack_url}?utm_source=newsletter" class="subscribe-btn" target="_blank">Subscribe on Substack</a>
                    </div>"""
        from .buttondown_util import resolve_buttondown_username, build_subscribe_form_html
        username = resolve_buttondown_username()
        if username:
            return f"""
                    <div class="subscribe-box">
                        <h3>Get this briefing in your inbox</h3>
                        <p>World news from every side — daily or once a week, your choice.</p>
                        {build_subscribe_form_html(username)}
                    </div>"""
        return ""
    
    def _build_about_subscribe_html(self) -> str:
        """Subscribe CTA for the about page."""
        substack_url = Config.SUBSTACK_URL
        if substack_url:
            return f'<a href="{substack_url}" class="cta-button" target="_blank">Subscribe on Substack</a>'
        from .buttondown_util import resolve_buttondown_username, build_subscribe_form_html
        username = resolve_buttondown_username()
        if username:
            return build_subscribe_form_html(username)
        return '<p class="note">Email newsletter coming soon</p>'

    def _update_index_page(self):
        """Update the main index page with recent newsletters."""
        
        # Get list of newsletters from Archive Manager (already sorted, newest first)
        newsletter_list = self.archive_manager.get_newsletter_list(limit=10)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geopolitical Daily - The World's News From Every Side</title>
    <meta name="description" content="World news from every side: how Western, Asian, Middle Eastern, African and Latin American media cover the same stories - every source linked, state media labeled.">
    <link rel="stylesheet" href="assets/style.css">
    <link rel="alternate" type="application/rss+xml" title="Geopolitical Daily RSS" href="feed.xml">
</head>
<body>
    <header class="header">
        <div class="container">
            <h1 class="site-title">Geopolitical Daily</h1>
            <p class="tagline">{Config.NEWSLETTER_TAGLINE}</p>
            <p class="description">World news from every side: how Western, Asian, Middle Eastern, African and Latin American media cover the same stories - every source linked, state media labeled.</p>
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
        
        # Add recent newsletters (up to 10)
        for newsletter in newsletter_list:
            html += f"""
                    <article class="newsletter-preview">
                        <h3><a href="{newsletter['relative_path']}">{newsletter['formatted_date']} Edition</a></h3>
                        <p class="newsletter-date">{newsletter['formatted_date']}</p>
                        <p>Strategic analysis of today's most significant underreported geopolitical developments.</p>
                    </article>
"""
        
        html += f"""
                </div>
            </section>

            <section class="about-section">
                <h2>About This Newsletter</h2>
                <p>Most world-news briefs show you one lens. Geopolitical Daily reads 60+ sources across Western, Asian, Middle Eastern, African and Latin American media every day &mdash; and shows you how each part of the world covers the same story, with every source linked and state media clearly labeled.</p>
                
                <h3>What Makes Us Different</h3>
                <ul>
                    <li><strong>Every side of the story:</strong> How Western, Chinese, Russian, regional and Global South media frame the same event &mdash; quoted, not paraphrased</li>
                    <li><strong>Blindspots:</strong> Stories one part of the world covers heavily while the rest ignores them</li>
                    <li><strong>Receipts included:</strong> Every claim links to its source; state-affiliated outlets are labeled</li>
                    <li><strong>Five minutes, daily or weekly:</strong> One big story, a world roundup, and one number worth knowing</li>
                </ul>
                
            </section>
{self._build_subscribe_html()}
            <p class="rss-alt">Prefer a feed reader? <a href="feed.xml">Subscribe via RSS</a>.</p>
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p>
                <a href="feed.xml">RSS Feed</a> |
                <a href="archive.html">Archive</a> |
                <a href="{self.GITHUB_REPO_URL}">Source Code</a>
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

        # Get all newsletters from Archive Manager
        newsletter_list = self.archive_manager.get_newsletter_list()

        # Group newsletters by year and month
        newsletters_by_period = {}
        for newsletter in newsletter_list:
            date_obj = newsletter['date']
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
                'filename': newsletter['filename'],
                'formatted_date': newsletter['formatted_date'],
                'relative_path': newsletter['relative_path']
            })

        html = f"""<!DOCTYPE html>
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
            <p class="tagline">{Config.NEWSLETTER_TAGLINE}</p>
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
                            <h4><a href="{newsletter['relative_path']}">{newsletter['formatted_date']} Edition</a></h4>
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

        html += f"""
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>&copy; 2025 Geopolitical Daily. Strategic analysis beyond the headlines.</p>
            <p>
                <a href="feed.xml">RSS Feed</a> |
                <a href="index.html">Latest Newsletter</a> |
                <a href="{self.GITHUB_REPO_URL}">Source Code</a>
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

        html = f"""<!DOCTYPE html>
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
            <p class="tagline">{Config.NEWSLETTER_TAGLINE}</p>
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
                <p class="about-intro">World news from every side: how Western, Asian, Middle Eastern, African and Latin American media cover the same stories - every source linked, state media labeled.</p>
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
                        <h3>Email Newsletter</h3>
                        <p>Receive daily analysis directly in your inbox</p>
                        {self._build_about_subscribe_html()}
                    </div>
                </div>

                <h2>Contact & Feedback</h2>
                <p>We welcome feedback on our analysis and suggestions for improvement. You can:</p>
                <ul>
                    <li><a href="{self.GITHUB_REPO_URL}/issues">Open an issue on GitHub</a> for bug reports or feature requests</li>
                    <li><a href="{self.GITHUB_REPO_URL}/discussions">Start a discussion</a> for analysis feedback</li>
                    <li>Check our <a href="{self.GITHUB_REPO_URL}">source code</a> to understand our methodology</li>
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
                <a href="{self.GITHUB_REPO_URL}">Source Code</a>
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
            # Get newsletters from Archive Manager (up to 20 for RSS)
            newsletter_list = self.archive_manager.get_newsletter_list(limit=20)

            rss_items = []
            for newsletter in newsletter_list:
                try:
                    newsletter_file = Path(newsletter['path'])
                    date_obj = newsletter['date']

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
                f"<link>{self.SITE_BASE_URL}/newsletters/{newsletter_file.name}</link>",
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
                f"<comments>{self.SITE_BASE_URL}/newsletters/{newsletter_file.name}#comments</comments>",
                f"<source url=\"{self.SITE_BASE_URL}/feed.xml\">Geopolitical Daily</source>",
            ])

            item_parts.append("</item>")

            return "\n        ".join(item_parts)

        except Exception as e:
            logger.error(f"Failed to generate RSS item for {newsletter_file.name}: {e}")
            # Return basic item as fallback
            return f"""
        <item>
            <title><![CDATA[{self._escape_for_cdata(title)}]]></title>
            <link>{self.SITE_BASE_URL}/newsletters/{newsletter_file.name}</link>
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
        <title><![CDATA[Geopolitical Daily - The World's News From Every Side]]></title>
        <link>{self.SITE_BASE_URL}/</link>
        <atom:link href="{self.SITE_BASE_URL}/feed.xml" rel="self" type="application/rss+xml" />
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
            <url>{self.SITE_BASE_URL}/assets/logo.png</url>
            <title>Geopolitical Daily</title>
            <link>{self.SITE_BASE_URL}/</link>
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

.geo-tag {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.region-tag { background: #edf2f7; color: #2d3748; border: 1px solid #cbd5e0; }
.event-tag  { background: #fefce8; color: #713f12; border: 1px solid #fde68a; }

.subscribe-box {
    margin-top: 2rem;
    padding: 1.5rem 2rem;
    background: linear-gradient(135deg, #1a2a4a 0%, #2c3e50 100%);
    border-radius: 8px;
    text-align: center;
    color: white;
}
.subscribe-box h3 { color: white; margin: 0 0 0.4rem 0; font-size: 1.1rem; }
.subscribe-box p  { color: #a0aec0; margin: 0 0 1rem 0; font-size: 0.9rem; }
.subscribe-form   { display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; }
.subscribe-form input[type="email"] {
    padding: 0.5rem 0.9rem; border: none; border-radius: 4px;
    font-size: 0.9rem; width: 220px; max-width: 100%;
}
.subscribe-btn {
    background: #e53e3e; color: white; border: none;
    padding: 0.5rem 1.2rem; border-radius: 4px;
    font-size: 0.9rem; font-weight: 600; cursor: pointer;
}
.subscribe-btn:hover { background: #c53030; }
.perspective-grid, .signals {
    margin: 2rem 0; padding: 1.25rem 1.5rem;
    background: var(--bg-light); border-radius: 8px;
}
.coverage-bar { display: flex; height: 6px; border-radius: 3px; overflow: hidden; margin-bottom: 0.5rem; }
.coverage-legend { font-size: 0.75rem; color: var(--text-light); margin-bottom: 1rem; }
.persp-row { display: flex; gap: 0.6rem; align-items: flex-start; margin-bottom: 0.75rem; line-height: 1.5; }
.persp-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 0.4rem; flex-shrink: 0; }
.persp-name { font-weight: 700; }
.state-label {
    font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.5px;
    background: #f5e6c8; color: #8a6d1a; border-radius: 8px; padding: 1px 7px; margin-left: 4px;
}
.persp-quote { font-style: italic; color: var(--text-light); margin-top: 0.25rem; font-size: 0.9rem; }
.blindspot {
    background: #fdf3e3; color: #8a5a17; border-radius: 6px;
    padding: 0.6rem 0.9rem; margin-top: 0.9rem; font-size: 0.9rem;
}
.section-label {
    font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 3px; color: #b8962e; text-align: center;
    border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;
    margin: 2.25rem 0 0.75rem 0;
}
.big-number { text-align: center; }
.signals-inline { margin: -0.5rem 0 1.25rem 0; }
.signals-inline .quick-hits { list-style: none; padding-left: 0.25rem; }
.also-today, .big-number {
    margin: 2rem 0; padding: 1.25rem 1.5rem;
    background: var(--bg-light); border-radius: 8px;
}
.section-heading {
    font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 2px; color: var(--text-light); margin: 0 0 0.75rem 0;
}
.quick-hits { margin: 0; padding-left: 1.1rem; }
.quick-hits li { margin-bottom: 0.6rem; line-height: 1.5; }
.quick-hit-region {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--accent-color); margin-right: 0.35rem;
}
.quick-hit-link { text-decoration: none; color: var(--accent-color); }
.big-number-value { font-size: 2.5rem; font-weight: 700; color: var(--primary-color); line-height: 1.1; }
.big-number-context { color: var(--text-light); margin: 0.4rem 0 0 0; }
.subscribe-frequency {
    display: flex; gap: 1.25rem; justify-content: center; flex-wrap: wrap;
    width: 100%; margin: 0.35rem 0; color: #cbd5e0; font-size: 0.85rem;
}
.subscribe-frequency label { cursor: pointer; }
.subscribe-frequency input { margin-right: 0.3rem; }
.rss-alt { text-align: center; font-size: 0.85rem; color: var(--text-light); margin-top: 0.75rem; }

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
        # Use Archive Manager for statistics
        archive_stats = self.archive_manager.get_stats()
        
        return {
            "total_newsletters": archive_stats['total_newsletters'],
            "max_newsletters": archive_stats['max_newsletters'],
            "output_directory": str(self.output_dir),
            "archive_at_capacity": archive_stats['is_at_capacity'],
            "oldest_newsletter": archive_stats['oldest_newsletter'],
            "newest_newsletter": archive_stats['newest_newsletter'],
            "total_size_bytes": archive_stats['total_size_bytes'],
            "last_updated": datetime.now().isoformat()
        }
