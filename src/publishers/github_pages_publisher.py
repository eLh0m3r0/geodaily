"""
GitHub Pages publisher for the newsletter.
"""

import json
import shutil
from html import escape as html_escape
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models import Newsletter, AIAnalysis
from .site_pages import (page_shell, write_css, load_issues, source_stats, latest_funnel,
                         funnel_strip_html, build_pipeline_page, build_dashboard_page,
                         DEFAULT_DESCRIPTION)
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
            self._update_pipeline_page()

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
    
    def _shell(self, **kwargs) -> str:
        """Shared masthead/nav/footer around a page body."""
        return page_shell(repo_url=self.GITHUB_REPO_URL,
                          tagline=Config.NEWSLETTER_TAGLINE, **kwargs)

    @staticmethod
    def _story_tags_html(analysis: AIAnalysis) -> str:
        region = getattr(analysis, 'region', 'global').replace('_', ' ').title()
        event = getattr(analysis, 'event_type', 'political').replace('_', ' ').title()
        return (f'<div class="story-meta"><span class="geo-tag region-tag">{region}</span>'
                f'<span class="geo-tag event-tag">{event}</span></div>')

    def _generate_newsletter_html(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> str:
        """Generate HTML content for newsletter."""
        from ..newsletter.source_display import dedupe_sources
        date_str = newsletter.date.strftime('%Y-%m-%d')

        # "In this issue": the stories, then the sections that exist today
        grid = getattr(newsletter, 'perspective_grid', None)
        toc_items = "".join(
            f'<li><a href="#story-{i}">{a.story_title}</a></li>'
            for i, a in enumerate(analyses, 1))
        more = []
        if getattr(newsletter, 'developing', None):
            more.append('<a href="#developing">Developing</a>')
        if getattr(newsletter, 'quick_hits', None):
            more.append('<a href="#also-today">Also today</a>')
        if grid and grid.blindspot:
            more.append('<a href="#blindspot">The blindspot</a>')
        if getattr(newsletter, 'big_number', None):
            more.append('<a href="#big-number">The big number</a>')
        toc_more = f'<div class="toc-more">{"".join(more)}</div>' if more else ""
        toc = (f'<nav class="issue-toc" aria-label="In this issue"><h2>In this issue</h2>'
               f'<ol>{toc_items}</ol>{toc_more}</nav>') if toc_items else ""

        html = f"""            <article class="newsletter">
                <header class="newsletter-header">
                    <p class="eyebrow">Daily briefing</p>
                    <h1 class="newsletter-title"><time datetime="{newsletter.date.isoformat()}">{newsletter.date.strftime('%A, %B %-d, %Y')}</time></h1>
                    <p class="newsletter-intro">{newsletter.intro_text or "Today's edition: the stories that matter most, from every side of the world."}</p>
                    {toc}
                </header>

                <div class="stories">
"""

        # Stories — grid and signals render inside the big story's flow
        grid_block = self._build_grid_html(newsletter)
        signals_block = self._build_signals_html(newsletter)
        for i, analysis in enumerate(analyses, 1):
            if i == 1:
                html += '                    <div class="section-label">The Big Story</div>\n'
            elif i == 2:
                html += '                    <div class="section-label">More Top Stories</div>\n'
            compact_class = "" if i == 1 else " compact"
            coverage_mini = "" if i == 1 else self._build_coverage_mini_html(analysis)
            sources_html = "".join(
                f'<li><a href="{url}" target="_blank" rel="noopener">{name}</a></li>'
                for url, name in dedupe_sources(analysis.sources, limit=4))
            html += f"""
                    <section class="story{compact_class}" id="story-{i}">
                        <header class="story-header">
                            <h2 class="story-title">{analysis.story_title}</h2>
                            {self._story_tags_html(analysis)}
                            {coverage_mini}
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
                                <ul>{sources_html}</ul>
                            </div>
                        </div>
                    </section>
"""

        # Developing + Also Today + Blindspot + Big Number
        html += self._build_extras_html(newsletter)

        # Link to the previous issue when it is still on the site
        previous = ""
        try:
            older = sorted(p.stem.replace('newsletter-', '')
                           for p in (self.output_dir / "newsletters").glob("newsletter-*.html")
                           if p.stem.replace('newsletter-', '') < date_str)
            if older:
                prev_date = datetime.strptime(older[-1], '%Y-%m-%d')
                previous = (f'<a href="newsletter-{older[-1]}.html">&larr; '
                            f'{prev_date.strftime("%B %-d")} issue</a>')
        except Exception:
            previous = ""

        html += f"""
                </div>

                <nav class="issue-nav" aria-label="Issues">
                    <span>{previous}</span>
                    <a href="../archive.html">All issues &rarr;</a>
                </nav>

                <footer class="newsletter-footer">
                    <p>{newsletter.footer_text or 'Written with AI from the sources linked above and published automatically; every claim links to its source. Spotted an error? Open an issue or reply to the email — a human reads every response.'}</p>
                    <p class="timestamp">Generated on {getattr(self, 'generated_at_override', None) or datetime.now().strftime('%Y-%m-%d at %H:%M UTC')} &middot; <a href="../how-it-works.html">How this issue was made</a></p>
                    {self._build_subscribe_html()}
                </footer>
            </article>"""

        return self._shell(
            title=f"{newsletter.title} - {newsletter.date.strftime('%B %d, %Y')}",
            description=DEFAULT_DESCRIPTION,
            body=html, depth=1,
            canonical=f"{self.SITE_BASE_URL}/newsletters/newsletter-{date_str}.html",
        )

    def _build_grid_html(self, newsletter: Newsletter) -> str:
        """How the World Covers It block (grid + blindspot) for page output."""
        grid = getattr(newsletter, 'perspective_grid', None)
        if not grid or not grid.counts:
            return ""
        from ..perspectives import (summarize_grid, GROUP_COLORS, label_of, is_wire_view,
                                    wire_copy_line, coverage_summary)
        parts, _legend = summarize_grid(grid)
        bar_spans = "".join(
            f'<span style="flex:{p["count"]};background-color:{p["color"]};" title="{p["label"]}: {p["count"]}"></span>'
            for p in parts
        )
        legend_html = " &middot; ".join(f'{p["pct"]}% {p["label"]}' for p in parts)
        rows = ""
        for view in grid.views:
            if not view.framing or is_wire_view(view):
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
        wire = wire_copy_line(grid.views)
        wire_html = f'<div class="persp-wire">{wire}</div>' if wire else ""
        return f"""
                    <div class="perspective-grid">
                        <h3 class="section-heading">How the World Covers It</h3>
                        <div class="coverage-bar">{bar_spans}</div>
                        <div class="coverage-legend">{coverage_summary(grid.total_outlets, grid.counts)} &middot; {legend_html}</div>
                        {rows}
                        {wire_html}
                    </div>
"""

    def _build_coverage_mini_html(self, analysis: AIAnalysis) -> str:
        """Coverage DNA mini-bar for stories without the full grid."""
        return self._coverage_bar_html(getattr(analysis, 'coverage_counts', None) or {},
                                       getattr(analysis, 'coverage_outlets', 0) or 0)

    def _coverage_bar_html(self, counts: dict, outlets: int) -> str:
        """Coverage bar + 'N reports from M outlets' legend from group counts."""
        if not counts or outlets < 2:
            return ""
        from ..perspectives import GROUP_COLORS, GROUP_ORDER, label_of
        ordered = sorted(counts.items(),
                         key=lambda kv: GROUP_ORDER.index(kv[0]) if kv[0] in GROUP_ORDER else 99)
        bar_spans = "".join(
            f'<span style="flex:{c};background-color:{GROUP_COLORS.get(g, "#6B7280")};" title="{label_of(g)}: {c}"></span>'
            for g, c in ordered
        )
        from ..perspectives import coverage_summary
        legend = " &middot; ".join(f'{label_of(g)} {c}' for g, c in ordered)
        return (f'<div class="coverage-mini"><div class="coverage-bar">{bar_spans}</div>'
                f'<div class="coverage-legend">{coverage_summary(outlets, counts)} &middot; {legend}</div></div>')

    def _build_blindspot_html(self, newsletter: Newsletter) -> str:
        """The Blindspot as its own section — a different event by design,
        so it must not sit inside the big story's flow."""
        grid = getattr(newsletter, 'perspective_grid', None)
        if not grid or not grid.blindspot:
            return ""
        from ..perspectives import blindspot_sources_line
        arrow = (f' <a href="{grid.blindspot_url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>'
                 if grid.blindspot_url else "")
        sources = blindspot_sources_line(getattr(grid, 'blindspot_outlets', None) or [])
        sources_html = f'<p class="blindspot-sources">{sources}</p>' if sources else ""
        return f"""
                    <section class="blindspot-section" id="blindspot">
                        <h2 class="section-label">The Blindspot</h2>
                        <p class="blindspot-note">A story covered heavily in one part of the world &mdash; and barely mentioned in the rest.</p>
                        <div class="blindspot">{grid.blindspot}{arrow}</div>
                        {sources_html}
                    </section>
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
        """Also Today roundup + Blindspot + Big Number after the stories.

        The perspective grid and signals render inside the big story instead.
        """
        html = ""
        quick_hits = getattr(newsletter, 'quick_hits', None) or []
        developing = getattr(newsletter, 'developing', None) or []
        big_number = getattr(newsletter, 'big_number', None)
        if developing:
            items = ""
            for d in developing:
                arrow = f' <a href="{d.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>' if d.url else ""
                items += (f'                        <li><strong class="developing-label">{d.storyline}:</strong> '
                          f'{d.text}{arrow}</li>\n')
            html += f"""
                    <section class="developing" id="developing">
                        <h2 class="section-label">Developing</h2>
                        <p class="developing-note">What changed today in stories you have been following.</p>
                        <ul class="quick-hits">
{items}                        </ul>
                    </section>
"""
        if quick_hits:
            items = ""
            for hit in quick_hits:
                region = hit.region.replace("_", " ").title()
                arrow = f' <a href="{hit.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>' if hit.url else ""
                items += (f'                        <li><span class="quick-hit-region">{region}</span> '
                          f'{hit.text}{arrow}</li>\n')
            html += f"""
                    <section class="also-today" id="also-today">
                        <h2 class="section-label">Also Today</h2>
                        <ul class="quick-hits">
{items}                        </ul>
                    </section>
"""
        html += self._build_blindspot_html(newsletter)
        if big_number:
            arrow = f' <a href="{big_number.url}" target="_blank" rel="noopener" class="quick-hit-link">&rarr;</a>' if big_number.url else ""
            html += f"""
                    <section class="big-number" id="big-number">
                        <h2 class="section-label">The Big Number</h2>
                        <div class="big-number-value">{big_number.value}</div>
                        <p class="big-number-context">{big_number.context}{arrow}</p>
                    </section>
"""
        return html

    def _publish_story_page(self, newsletter: Newsletter, analyses: List[AIAnalysis]) -> Optional[str]:
        """Write an evergreen per-story SEO page for EVERY selected story.

        Unlike the newsletter archive (rotated, max N issues), story pages
        accumulate — each day's topics stay indexable. The big story's page
        carries the perspective grid; secondary stories carry the coverage
        mini-bar. Three stories a day means three indexable topic pages.
        """
        if not analyses:
            return None
        from ..newsletter.issue_store import story_slug
        from ..newsletter.source_display import dedupe_sources
        date_str = newsletter.date.strftime('%Y-%m-%d')
        stories_dir = self.output_dir / "stories"
        stories_dir.mkdir(exist_ok=True)

        first_path = None
        for i, story in enumerate(analyses):
            slug = f"{date_str}-{story_slug(story.story_title)}"
            sources_html = "".join(
                f'<li><a href="{url}" target="_blank" rel="noopener">{name}</a></li>'
                for url, name in dedupe_sources(story.sources, limit=4)
            )
            description = (story.why_important or "")[:155]
            grid_block = self._build_grid_html(newsletter) if i == 0 else ""
            coverage_mini = "" if i == 0 else self._build_coverage_mini_html(story)

            body = f"""            <article class="newsletter">
                <div class="stories">
                    <section class="story">
                        <header class="story-header">
                            <p class="eyebrow"><time datetime="{newsletter.date.isoformat()}">{newsletter.date.strftime('%B %-d, %Y')}</time></p>
                            <h1 class="story-title">{story.story_title}</h1>
                            {coverage_mini}
                        </header>
                        <div class="story-content">
                            <div class="analysis-section"><h3>Why This Matters</h3><p>{story.why_important}</p></div>
                            {grid_block}
                            <div class="analysis-section"><h3>What Others Are Missing</h3><p>{story.what_overlooked}</p></div>
                            <div class="analysis-section"><h3>What to Watch</h3><p>{story.prediction}</p></div>
                            <div class="sources"><h4>Sources</h4><ul>{sources_html}</ul></div>
                        </div>
                    </section>
                </div>
                <footer class="newsletter-footer">
                    <p>From the <a href="../newsletters/newsletter-{date_str}.html">{newsletter.date.strftime('%B %-d, %Y')} edition</a> of {newsletter.title}.</p>
                    {self._build_subscribe_html()}
                </footer>
            </article>"""
            html = self._shell(
                title=f"{story.story_title} - {newsletter.title}",
                description=description, body=body, depth=1,
                canonical=f"{self.SITE_BASE_URL}/stories/{slug}.html",
            )
            path = stories_dir / f"{slug}.html"
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"Story page published: stories/{slug}.html")
            if first_path is None:
                first_path = f"stories/{slug}.html"
        return first_path

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
    
    def _issue_data(self, newsletter: dict) -> dict:
        """The issue JSON that belongs to an archive-list entry ({} if none)."""
        try:
            json_path = (self.output_dir / "newsletters" /
                         Path(newsletter['filename']).with_suffix('.json').name)
            return json.loads(json_path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _issue_titles(self, newsletter: dict) -> List[str]:
        return [s.get('story_title', '') for s in (self._issue_data(newsletter).get('stories') or [])
                if s.get('story_title')]

    def _issue_lead(self, newsletter: dict) -> str:
        """Headline strip for an index card: the issue's story titles from its
        JSON (every card used to carry the same filler sentence)."""
        titles = self._issue_titles(newsletter)
        if not titles:
            return "Three stories that matter, from every side of the world."
        return " &middot; ".join(html_escape(t) for t in titles[:3])

    def _issue_row_html(self, newsletter: dict) -> str:
        """One archive row: date, the big story as the link, the rest below."""
        titles = self._issue_titles(newsletter)
        date_obj = newsletter['date']
        headline = html_escape(titles[0]) if titles else f"{newsletter['formatted_date']} edition"
        rest = " &middot; ".join(html_escape(t) for t in titles[1:3])
        rest_html = f"<p>{rest}</p>" if rest else ""
        return f"""
                    <li class="issue-row">
                        <time datetime="{date_obj.strftime('%Y-%m-%d')}">{date_obj.strftime('%b %-d, %Y')}</time>
                        <div><h3><a href="{newsletter['relative_path']}">{headline}</a></h3>{rest_html}</div>
                    </li>"""

    def _build_about_subscribe_html(self) -> str:
        """Subscribe CTA for the about page."""
        return self._build_subscribe_html() or '<p class="note">Email newsletter coming soon</p>'

    def _update_index_page(self):
        """Update the main index page: pitch, latest issue, how it is made, recent issues."""

        newsletter_list = self.archive_manager.get_newsletter_list(limit=10)
        sources = source_stats()
        outlets_point = (f"{sources['total']} outlets across {sources['perspectives']} perspectives, every source linked"
                         if sources.get('total') else "Outlets from every region, every source linked")

        latest_html = ""
        if newsletter_list:
            latest = newsletter_list[0]
            data = self._issue_data(latest)
            stories = data.get('stories') or []
            href = latest['relative_path']
            if stories:
                lead = stories[0]
                grid = data.get('perspective_grid') or {}
                coverage = self._coverage_bar_html(grid.get('counts') or {}, grid.get('total_outlets') or 0)
                others = "".join(
                    f'<li><a href="{href}#story-{n}">{html_escape(s.get("story_title", ""))}</a></li>'
                    for n, s in enumerate(stories[1:3], 2))
                others_html = f'<ul class="also-in-issue">{others}</ul>' if others else ""
                latest_html = f"""
            <section class="latest">
                <h2 class="section-label">Latest issue &middot; {latest['date'].strftime('%B %-d, %Y')}</h2>
                <h3 class="lead-story-title"><a href="{href}">{html_escape(lead.get('story_title', ''))}</a></h3>
                <p class="lead-story-dek">{html_escape(lead.get('why_important', ''))}</p>
                {coverage}
                {others_html}
                <a class="read-more" href="{href}">Read the full issue &rarr;</a>
            </section>
"""
            else:
                latest_html = f"""
            <section class="latest">
                <h2 class="section-label">Latest issue</h2>
                <h3 class="lead-story-title"><a href="{href}">{latest['formatted_date']} edition</a></h3>
            </section>
"""

        funnel = funnel_strip_html(latest_funnel(load_issues(self.output_dir)), sources)
        if funnel:
            made_html = f"""
            <section class="made">
                <h2 class="section-label">How today's issue was made</h2>
                {funnel}
                <p class="funnel-note">Two AI calls, the rest is code &mdash; and every step is checked.
                   <a href="how-it-works.html">See the whole pipeline &rarr;</a></p>
            </section>
"""
        else:
            made_html = """
            <section class="made">
                <h2 class="section-label">How it is made</h2>
                <div class="cards">
                    <div class="card"><h3>Every side of the story</h3><p>How Western, Chinese, Russian, regional and Global South media frame the same event &mdash; quoted word for word, not paraphrased.</p></div>
                    <div class="card"><h3>The blindspot</h3><p>One story a day that part of the world covers and no Western outlet we track has reported.</p></div>
                    <div class="card"><h3>Receipts included</h3><p>Every claim links to its source; state-affiliated outlets are labeled wherever they appear.</p></div>
                </div>
                <p class="funnel-note">Written by AI, checked by code. <a href="how-it-works.html">See the whole pipeline &rarr;</a></p>
            </section>
"""

        earlier = "".join(self._issue_row_html(n) for n in newsletter_list[1:])
        earlier_html = f"""
            <section class="recent-newsletters">
                <h2 class="section-label">Earlier issues <span class="label-aside"><a href="archive.html">Archive &rarr;</a></span></h2>
                <ul class="issue-list">{earlier}
                </ul>
            </section>
""" if earlier else ""

        body = f"""            <section class="hero">
                <h1>{html_escape(Config.NEWSLETTER_TAGLINE)}</h1>
                <p class="page-lead">A daily five-minute briefing that shows how Western, Asian, Middle Eastern,
                African and Latin American media cover the same stories &mdash; and what each of them leaves out.</p>
{self._build_subscribe_html()}
                <ul class="hero-points">
                    <li>{outlets_point}</li>
                    <li>State media labeled, never the sole source of a fact</li>
                    <li>Daily, or one Sunday digest</li>
                </ul>
            </section>
{latest_html}{made_html}{earlier_html}
            <p class="rss-alt" style="margin-top:2rem;">Prefer a feed reader? <a href="feed.xml">Subscribe via RSS</a>.</p>"""

        html = self._shell(
            title="Geopolitical Daily - The World's News From Every Side",
            description=DEFAULT_DESCRIPTION, body=body, active="home",
            canonical=f"{self.SITE_BASE_URL}/",
        )
        with open(self.output_dir / "index.html", 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("Index page updated")

    def _story_index(self) -> List[tuple]:
        """(date, title, relative_path) for every evergreen story page, newest first."""
        import re
        entries = []
        stories_dir = self.output_dir / "stories"
        if not stories_dir.exists():
            return entries
        for path in stories_dir.glob("*.html"):
            try:
                date_obj = datetime.strptime(path.name[:10], '%Y-%m-%d')
                head = path.read_text(encoding='utf-8')[:2000]
                match = re.search(r'<title>(.*?)</title>', head, re.DOTALL)
                if not match:
                    continue
                title = match.group(1).strip()
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                entries.append((date_obj, title, f"stories/{path.name}"))
            except Exception:
                continue
        entries.sort(key=lambda e: (e[0], e[2]), reverse=True)
        return entries

    def _update_archive_page(self):
        """Archive: the issues still on the site, then every story page by month."""

        newsletter_list = self.archive_manager.get_newsletter_list()
        issues_html = "".join(self._issue_row_html(n) for n in newsletter_list)

        stories_html = ""
        current_month = None
        for date_obj, title, rel in self._story_index():
            month = date_obj.strftime('%B %Y')
            if month != current_month:
                if current_month is not None:
                    stories_html += "\n                </ul>"
                stories_html += f'\n                <h3 class="month-heading">{month}</h3>\n                <ul class="story-index">'
                current_month = month
            stories_html += (f'\n                    <li><time datetime="{date_obj.strftime("%Y-%m-%d")}">'
                             f'{date_obj.strftime("%b %-d")}</time><a href="{rel}">{title}</a></li>')
        if current_month is not None:
            stories_html += "\n                </ul>"
        stories_section = f"""
            <section class="archive-stories">
                <h2 class="section-label">Every story</h2>
                <p class="developing-note">Each top story keeps its own page, with the coverage breakdown it ran with.</p>{stories_html}
            </section>""" if stories_html else ""

        body = f"""            <header class="page-head">
                <p class="eyebrow">Archive</p>
                <h1 class="page-title">Past issues and stories</h1>
                <p class="page-lead">The most recent issues in full, and a permanent page for every top story we have covered.</p>
            </header>

            <section class="archive-issues">
                <h2 class="section-label">Recent issues</h2>
                <ul class="issue-list">{issues_html}
                </ul>
            </section>
{stories_section}"""

        html = self._shell(
            title="Archive - Geopolitical Daily",
            description="Past issues of Geopolitical Daily and a page for every top story covered.",
            body=body, active="archive",
        )
        with open(self.output_dir / "archive.html", 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("Archive page updated")

    def _update_about_page(self):
        """Generate about page with project information."""
        sources = source_stats()
        total = sources.get('total') or 0
        reads = (f"reads {total} news sources in {sources.get('perspectives', 0)} perspective groups"
                 if total else "reads news sources from every region")
        editor = (Config.NEWSLETTER_EDITOR_NAME or "").strip() if hasattr(Config, 'NEWSLETTER_EDITOR_NAME') else ""
        written = (f"Issues are drafted with AI and curated by {html_escape(editor)}." if editor else
                   "Issues are written by an AI model and published automatically; no person reviews an issue before it goes out.")

        body = f"""            <header class="page-head">
                <p class="eyebrow">About</p>
                <h1 class="page-title">One story, every side</h1>
                <p class="page-lead">Most world-news briefings show you one lens. Geopolitical Daily {reads} every day
                and shows how each part of the world covers the same event &mdash; with every source linked and
                state media clearly labeled.</p>
            </header>

            <h2 class="section-label">What is in an issue</h2>
            <div class="cards">
                <div class="card"><h3>The big story</h3><p>The day's most important event, why it matters, and <em>How the world covers it</em>: each region's framing with a word-for-word quote.</p></div>
                <div class="card"><h3>More top stories</h3><p>Two more stories, each with a bar showing which parts of the world reported them.</p></div>
                <div class="card"><h3>Developing</h3><p>One-line updates on stories you already read about &mdash; only what is new.</p></div>
                <div class="card"><h3>Also today</h3><p>Quick hits from around the world, one sentence and one link each.</p></div>
                <div class="card"><h3>The blindspot</h3><p>A story reported in one part of the world that no Western outlet we track has covered.</p></div>
                <div class="card"><h3>The big number</h3><p>One figure from today's news, with the context to read it.</p></div>
            </div>

            <h2 class="section-label">How it is made</h2>
            <div class="prose">
                <p>{written} The model's work is then checked by code: quotes must match the source text, repeated
                stories are held back, links must point at what they claim to. The whole process, with the numbers
                from the latest run, is on <a href="how-it-works.html">How it works</a>; cost and quality figures for
                every issue are on the <a href="dashboard.html">dashboard</a>.</p>
                <p>State-affiliated outlets are part of the picture on purpose. They show how a government wants an
                event to be seen. They are always labeled and never used as the only source for a fact.</p>
            </div>

            <h2 class="section-label">Subscribe</h2>
            {self._build_about_subscribe_html()}
            <p class="rss-alt">Prefer a feed reader? <a href="feed.xml">Subscribe via RSS</a>.</p>

            <h2 class="section-label">Corrections and feedback</h2>
            <div class="prose">
                <p>Spotted an error? <a href="{self.GITHUB_REPO_URL}/issues">Open an issue on GitHub</a> or reply to
                any email. The <a href="{self.GITHUB_REPO_URL}">source code</a> is public, including the list of
                sources and the editorial rules.</p>
            </div>"""

        html = self._shell(
            title="About - Geopolitical Daily",
            description="What Geopolitical Daily is, what is in an issue and how it is made.",
            body=body, active="about",
        )
        with open(self.output_dir / "about.html", 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info("About page updated")

    def _update_pipeline_page(self):
        """How it works: the pipeline diagram with the latest run's counts."""
        try:
            build_pipeline_page(self.output_dir, repo_url=self.GITHUB_REPO_URL,
                                site_base_url=self.SITE_BASE_URL,
                                tagline=Config.NEWSLETTER_TAGLINE)
            logger.info("How-it-works page updated")
        except Exception as e:
            logger.error(f"Failed to update how-it-works page: {e}")

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
        <dc:rights>© {datetime.now().year} Geopolitical Daily. All rights reserved.</dc:rights>

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
        """Copy the stylesheet (src/publishers/site.css) to the output directory."""
        write_css(self.output_dir)
        logger.info("Assets copied")

    def _update_dashboard(self):
        """Dashboard from the issue JSONs: billed cost, model, timing, readability."""
        try:
            build_dashboard_page(self.output_dir, repo_url=self.GITHUB_REPO_URL,
                                 tagline=Config.NEWSLETTER_TAGLINE)
            logger.info("Dashboard updated from issue data")
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
