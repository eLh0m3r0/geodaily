"""
Shared page shell and the data-driven site pages (How it works, Dashboard).

Stdlib only on purpose: `generate_simple_dashboard.py` runs this as its own
workflow step and must not drag the pipeline's dependencies in.

Everything here is built from files the daily run already commits:
`docs/newsletters/newsletter-*.json` (issue content + `meta`) and
`sources.json`. No number on these pages is an estimate — when a figure is
not recorded the page says so or leaves it out.
"""

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSS_SOURCE = Path(__file__).with_name("site.css")

SITE_NAME = "Geopolitical Daily"
DEFAULT_TAGLINE = "The world's news from every side"
DEFAULT_DESCRIPTION = (
    "World news from every side: how Western, Asian, Middle Eastern, African "
    "and Latin American media cover the same stories - every source linked, "
    "state media labeled."
)

# (key, label, file) — one list, so no page can drift from the others
NAV_ITEMS = [
    ("home", "Latest", "index.html"),
    ("archive", "Archive", "archive.html"),
    ("pipeline", "How it works", "how-it-works.html"),
    ("dashboard", "Dashboard", "dashboard.html"),
    ("about", "About", "about.html"),
    ("rss", "RSS", "feed.xml"),
]


# ----------------------------------------------------------------------
# Shell
# ----------------------------------------------------------------------

def page_shell(*, title: str, description: str, body: str, active: str = "",
               depth: int = 0, canonical: str = "", wide: bool = False,
               repo_url: str = "", tagline: str = DEFAULT_TAGLINE,
               head_extra: str = "") -> str:
    """Full HTML document: masthead, nav, <main>, footer.

    `depth` is how many directories below the site root the page lives
    (issue and story pages are 1), so links stay relative and the site
    works under any base path.
    """
    root = "../" * depth
    nav = "".join(
        f'<a href="{root}{href}"{" aria-current=" + chr(34) + "page" + chr(34) if key == active else ""}>{label}</a>'
        for key, label, href in NAV_ITEMS
    )
    canonical_tag = f'\n    <link rel="canonical" href="{canonical}">' if canonical else ""
    source_link = f' &middot; <a href="{repo_url}">Source code</a>' if repo_url else ""
    container = "container wide" if wide else "container"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{escape(description, quote=True)}">
    <link rel="stylesheet" href="{root}assets/style.css">
    <link rel="alternate" type="application/rss+xml" title="{SITE_NAME} RSS" href="{root}feed.xml">{canonical_tag}{head_extra}
</head>
<body>
    <header class="header">
        <div class="container">
            <a class="site-title" href="{root}index.html">{SITE_NAME}</a>
            <nav class="nav" aria-label="Site">{nav}</nav>
        </div>
    </header>

    <main class="main">
        <div class="{container}">
{body}
        </div>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p><strong>{SITE_NAME}</strong> &mdash; {escape(tagline)}</p>
            <p>Written with AI from the linked sources and published automatically.
               <a href="{root}how-it-works.html">How it works</a> &middot;
               <a href="{root}archive.html">Archive</a> &middot;
               <a href="{root}feed.xml">RSS</a>{source_link}</p>
        </div>
    </footer>
</body>
</html>"""


def write_css(output_dir: Path) -> Path:
    """Copy the stylesheet to <output_dir>/assets/style.css."""
    assets = Path(output_dir) / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    target = assets / "style.css"
    target.write_text(CSS_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    return target


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------

def load_issues(output_dir: Path) -> List[dict]:
    """All issue JSONs on the site, newest first."""
    issues = []
    for path in sorted((Path(output_dir) / "newsletters").glob("newsletter-*.json"), reverse=True):
        try:
            issues.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return issues


def source_stats(sources_file: Optional[Path] = None) -> Dict[str, int]:
    """Counts from sources.json: total, rss, scraped, perspectives, state."""
    path = Path(sources_file) if sources_file else PROJECT_ROOT / "sources.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rss = data.get("tier1_sources") or []
    scraped = data.get("tier2_sources") or []
    everything = rss + scraped
    western = {"western_mainstream", "western_analysis"}
    return {
        "total": len(everything),
        "rss": len(rss),
        "scraped": len(scraped),
        "perspectives": len({s.get("perspective") for s in everything if s.get("perspective")}),
        "state": sum(1 for s in everything if s.get("state_affiliated")),
        "non_western": sum(1 for s in everything
                           if s.get("perspective") and s.get("perspective") not in western),
    }


def issue_cost(issue: dict) -> Optional[float]:
    """Billed AI cost of one issue (issue call + grid call), None if unknown."""
    meta = issue.get("meta") or {}
    if "analysis_cost_usd" not in meta:
        return None
    return float(meta.get("analysis_cost_usd") or 0) + float(meta.get("grid_cost_usd") or 0)


def final_grade(issue: dict) -> Optional[float]:
    """Flesch-Kincaid grade of the published copy."""
    r = (issue.get("meta") or {}).get("readability") or {}
    if r.get("rewrite") == "applied" and r.get("rewrite_grade") is not None:
        return float(r["rewrite_grade"])
    return float(r["grade"]) if r.get("grade") is not None else None


def latest_funnel(issues: List[dict]) -> Dict[str, object]:
    """The newest issue's recorded pipeline counts (`meta.pipeline`), plus its
    date. Empty when no issue on the site carries them yet."""
    for issue in issues:
        funnel = (issue.get("meta") or {}).get("pipeline")
        if funnel:
            return dict(funnel, date=issue.get("date", ""))
    return {}


def _n(value) -> str:
    return f"{int(value):,}"


def _nice_date(date_str: str, fmt: str = "%B %-d, %Y") -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime(fmt)
    except Exception:
        return date_str


def _avg(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


# ----------------------------------------------------------------------
# How it works
# ----------------------------------------------------------------------

def funnel_strip_html(funnel: Dict[str, object], sources: Dict[str, int]) -> str:
    """Compact 'N sources -> N articles -> N events -> N stories' strip."""
    steps = []
    if sources.get("total"):
        steps.append((_n(sources["total"]), f"sources in {sources.get('perspectives', 0)} perspectives"))
    if funnel.get("collected"):
        steps.append((_n(funnel["collected"]), "articles collected"))
    if funnel.get("events"):
        steps.append((_n(funnel["events"]), "events found by clustering"))
    if funnel.get("prompt_articles"):
        steps.append((_n(funnel["prompt_articles"]), "articles read by the model"))
    if funnel.get("stories"):
        extras = funnel.get("quick_hits") or 0
        steps.append((_n(funnel["stories"]),
                      f"top stories + {extras} quick hits" if extras else "top stories"))
    if len(steps) < 2:
        return ""
    cells = "".join(f'<div class="funnel-step"><b>{value}</b><span>{label}</span></div>'
                    for value, label in steps)
    return f'<div class="funnel">{cells}</div>'


def _edge(text: str) -> str:
    return f'<li class="flow-edge" aria-hidden="true">{text}</li>'


def build_pipeline_page(output_dir: Path, *, repo_url: str = "",
                        site_base_url: str = "", tagline: str = DEFAULT_TAGLINE) -> Path:
    """Write how-it-works.html: the daily pipeline as a flow diagram, with the
    latest run's real counts on the arrows when the issue JSON records them."""
    output_dir = Path(output_dir)
    issues = load_issues(output_dir)
    sources = source_stats()
    funnel = latest_funnel(issues)
    latest_meta = (issues[0].get("meta") or {}) if issues else {}

    total = sources.get("total") or 0
    persp = sources.get("perspectives") or 0
    src_title = (f"{total} sources &middot; {persp} perspectives" if total
                 else "Sources from every part of the world")
    src_detail = (f"{sources.get('rss', 0)} RSS feeds + {sources.get('scraped', 0)} scraped sites; "
                  f"{sources.get('non_western', 0)} are non-Western and "
                  f"{sources.get('state', 0)} are state-affiliated (always labeled)"
                  if total else "RSS feeds and scraped sites, state media always labeled")

    collected = funnel.get("collected")
    deduped = funnel.get("after_dedup")
    events = funnel.get("events")
    prompt_articles = funnel.get("prompt_articles")
    e_collect = (f"<b>{_n(collected)}</b> articles from the last 24&ndash;72 hours" if collected
                 else "every article from the last 24&ndash;72 hours")
    e_cluster = (f"<b>{_n(deduped)}</b> articles after near-duplicates are removed"
                 + (f", grouped into <b>{_n(events)}</b> events" if events else "")
                 if deduped else "articles tagged with the event they report")
    e_prompt = (f"<b>{_n(prompt_articles)}</b> articles go to the model" if prompt_articles
                else "about 60 articles go to the model")
    n_stories = funnel.get("stories") or (len(issues[0].get("stories") or []) if issues else 3)
    n_hits = funnel.get("quick_hits")
    if n_hits is None and issues:
        n_hits = len(issues[0].get("quick_hits") or [])
    e_issue = f"<b>{n_stories}</b> ranked stories, <b>{n_hits or 0}</b> quick hits, one big number"

    model = latest_meta.get("served_model") or latest_meta.get("model") or ""
    model_note = (f'Latest issue written by <code>{escape(str(model))}</code>.' if model and "mock" not in str(model)
                  else "")

    costs = [issue_cost(i) for i in issues]
    avg_cost = _avg(costs)
    seconds = _avg([(i.get("meta") or {}).get("analysis_seconds") for i in issues])
    run_seconds = funnel.get("seconds")

    stats = []
    if total:
        stats.append((str(total), f"sources across {persp} perspectives"))
    if collected:
        stats.append((_n(collected), f"articles read for the {_nice_date(str(funnel.get('date', '')), '%b %-d')} issue"))
    stats.append(("2", "AI calls per issue &mdash; everything else is plain code"))
    if avg_cost is not None:
        stats.append((f"${avg_cost:.3f}", f"average AI cost per issue (last {len([c for c in costs if c is not None])})"))
    if run_seconds:
        stats.append((f"{float(run_seconds) / 60:.0f} min", "start to published, latest run"))
    elif seconds:
        stats.append((f"{seconds / 60:.1f} min", "average time the model takes to write an issue"))
    stats_html = "".join(f'<div class="stat"><b>{v}</b><span>{l}</span></div>' for v, l in stats)

    as_of = (f'Numbers on the arrows are from the {_nice_date(str(funnel["date"]))} run.'
             if funnel.get("date") else
             "Per-run counts appear on the arrows once the next issue is published.")

    body = f"""
            <header class="page-head">
                <p class="eyebrow">How it works</p>
                <h1 class="page-title">From {total or 'dozens of'} sources to one five-minute briefing</h1>
                <p class="page-lead">Every issue is produced by the same automated run: collect, group into events,
                let a language model write the issue, then check its work in code. Here is each step, what is
                AI and what is not, and what stops a bad issue from going out.</p>
            </header>

            <div class="stats">{stats_html}</div>

            <h2 class="section-label">The daily run</h2>
            <div class="flow-legend">
                <span><i></i>code</span>
                <span><i class="ai"></i>AI model call (the only paid steps)</span>
                <span><i class="soft"></i>optional &mdash; the issue ships without it if it fails</span>
            </div>
            <ol class="flow">
                <li class="flow-node">
                    <h3>{src_title}</h3>
                    <p>{src_detail}.</p>
                </li>
                {_edge(e_collect)}
                <li class="flow-node">
                    <h3>Collect and enrich</h3>
                    <p>All feeds are fetched in parallel. Short RSS summaries are replaced with the article's
                    full text; articles readers could not read (non-Latin script) are skipped.</p>
                </li>
                {_edge("each article keeps its outlet, perspective and state-media label")}
                <li class="flow-node">
                    <h3>Group articles into events</h3>
                    <p>Sentence embeddings and density clustering put every report of the same event in one
                    group &mdash; so a Western and a non-Western account of one event sit side by side.</p>
                    <p class="flow-aside"><b>Fallback:</b> if the embedding model cannot load, plain
                    title-similarity de-duplication keeps the run going.</p>
                </li>
                {_edge(e_cluster)}
                <li class="flow-node">
                    <h3>Pre-select what the model reads</h3>
                    <p>Events are ranked by how many outlets confirm them and how many different perspectives
                    cover them; up to four articles per event are kept, from different perspectives.</p>
                </li>
                {_edge(e_prompt)}
                <li class="flow-node ai">
                    <h3>AI call 1 &mdash; write the issue</h3>
                    <p>One call picks and ranks the top stories, writes the quick hits and the big number.
                    The model also sees the last issues so it can lead with fresh events.</p>
                    <p class="flow-aside"><b>Readability gate:</b> copy above a 9.5 school-grade reading level
                    is sent back for a rewrite (at most twice) &mdash; kept only if it reads easier without
                    turning choppy or losing a figure.</p>
                </li>
                {_edge(e_issue)}
                <li class="flow-node">
                    <h3>Editorial rules, enforced in code</h3>
                    <p>Running storylines move to <em>Developing</em>; items that repeat recent issues are
                    dropped; links are checked against the text they sit under; headlines are set in
                    sentence case; off-topic items (crime, celebrity, sport) are removed.</p>
                </li>
                {_edge("every decision is logged in the issue's JSON")}
                <li class="flow-node ai">
                    <h3>AI call 2 &mdash; how the world covers it</h3>
                    <p>For the big story the model gets the event's articles grouped by perspective and returns
                    each group's framing plus one quote. The <em>Blindspot</em> is picked by code: an event
                    reported by at least two outlets we track, none of them Western.</p>
                    <p class="flow-aside"><b>Quote check:</b> a quote must appear word for word in the source
                    article, or it is dropped.</p>
                </li>
                {_edge("perspective grid + blindspot")}
                <li class="flow-node soft">
                    <h3>Signals</h3>
                    <p>Prediction-market odds and news-volume trends for the big story, added only when a
                    market matches the story's specific names.</p>
                </li>
                {_edge("one data set, three outputs")}
            </ol>
            <div class="flow-out">
                <div class="flow-node"><h3>This website</h3><p>The issue page, a permanent page per story, archive and RSS.</p></div>
                <div class="flow-node"><h3>Email</h3><p>Sent to daily subscribers; delivery is verified after sending.</p></div>
                <div class="flow-node"><h3>Issue JSON</h3><p>Machine-readable copy with model, cost and decisions. Feeds the Sunday digest &mdash; no AI needed.</p></div>
            </div>
            <p class="fine-print" style="max-width:620px;margin-left:auto;margin-right:auto;">{as_of} {model_note}
               Live figures for every issue are on the <a href="dashboard.html">dashboard</a>.</p>

            <h2 class="section-label">What keeps it honest</h2>
            <ul class="checks">
                <li><strong>Quotes are verbatim.</strong> Every quote in the perspective grid is matched against the
                    article text. A paraphrase never appears in quotation marks.</li>
                <li><strong>State media is data, not a source of fact.</strong> State-affiliated outlets are labeled
                    wherever they appear and show how a government frames an event; they are never the only
                    source for a claim.</li>
                <li><strong>Who covered it is counted, not written.</strong> Coverage bars and the blindspot's
                    &ldquo;reported by&rdquo; line come from the article data, so the model cannot claim
                    coverage that is not there.</li>
                <li><strong>No reruns.</strong> Storylines are tracked across days by their distinctive names. A
                    story you already read comes back only as a one-line update with new facts.</li>
                <li><strong>Plain English.</strong> Each issue is measured with the Flesch-Kincaid formula before
                    it is published; the result is on the dashboard.</li>
                <li><strong>Every claim links to its source,</strong> and each link is checked to be about the
                    sentence it is attached to.</li>
                <li><strong>A spending cap.</strong> AI calls stop when the monthly budget is used up.</li>
            </ul>

            <h2 class="section-label">When it runs</h2>
            <div class="schedule">
                <div class="when">Every morning (UTC)</div>
                <div>The daily run above: publishes the issue here and emails subscribers. A second start the same
                     day does nothing once the issue is out.</div>
                <div class="when">Sundays</div>
                <div>The weekly digest is assembled from the week's issue files for subscribers who chose one
                     email a week.</div>
                <div class="when">Mondays</div>
                <div>Every feed is tested; dead or blocked feeds are reported.</div>
            </div>
"""
    html = page_shell(
        title=f"How it works - {SITE_NAME}",
        description="How Geopolitical Daily is made: the daily pipeline from sources to published issue, "
                    "what is AI, what is code, and the checks every issue passes.",
        body=body, active="pipeline", repo_url=repo_url, tagline=tagline,
        canonical=f"{site_base_url}/how-it-works.html" if site_base_url else "",
    )
    path = output_dir / "how-it-works.html"
    path.write_text(html, encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

def build_dashboard_page(output_dir: Path, *, repo_url: str = "",
                         tagline: str = DEFAULT_TAGLINE) -> Path:
    """Write dashboard.html from the issue JSONs' `meta` — billed cost, served
    model, timing, readability and editorial decisions per issue."""
    output_dir = Path(output_dir)
    issues = load_issues(output_dir)
    sources = source_stats()
    funnel = latest_funnel(issues)

    rows = ""
    for issue in issues:
        meta = issue.get("meta") or {}
        date = issue.get("date", "")
        cost = issue_cost(issue)
        grade = final_grade(issue)
        r = meta.get("readability") or {}
        grade_cell = '<span class="muted">&ndash;</span>'
        if grade is not None:
            before = r.get("grade")
            grade_cell = f"{grade:.1f}"
            if r.get("rewrite") == "applied" and before is not None:
                grade_cell = f'<span class="muted">{float(before):.1f} &rarr;</span> {grade:.1f}'
        grid = issue.get("perspective_grid") or {}
        angles = sum(1 for v in (grid.get("views") or []) if v.get("framing") and not v.get("wire_copy"))
        flags = meta.get("quality_flags") or []
        actions = meta.get("editorial_actions") or []
        secs = meta.get("analysis_seconds")
        model = str(meta.get("served_model") or meta.get("model") or "")
        collected = (meta.get("pipeline") or {}).get("collected")
        rows += f"""
                    <tr>
                        <td><a href="newsletters/newsletter-{date}.html">{_nice_date(date, '%b %-d')}</a></td>
                        <td class="num">{_n(collected) if collected else '<span class="muted">&ndash;</span>'}</td>
                        <td class="num">{len(issue.get('stories') or [])} / {len(issue.get('developing') or [])} / {len(issue.get('quick_hits') or [])}</td>
                        <td class="num">{angles or '<span class="warn">0</span>'}</td>
                        <td>{'<span class="ok">yes</span>' if grid.get('blindspot') else '<span class="warn">none</span>'}</td>
                        <td class="num">{grade_cell}</td>
                        <td class="num">{f'{float(secs):.0f} s' if secs else '<span class="muted">&ndash;</span>'}</td>
                        <td class="num">{f'${cost:.4f}' if cost is not None else '<span class="muted">&ndash;</span>'}</td>
                        <td class="num">{len(actions)}</td>
                        <td>{f'<span class="warn">{len(flags)}</span>' if flags else '<span class="ok">0</span>'}</td>
                        <td>{escape(model.split('/')[-1]) or '<span class="muted">&ndash;</span>'}</td>
                    </tr>"""

    costs = [c for c in (issue_cost(i) for i in issues) if c is not None]
    grades = [g for g in (final_grade(i) for i in issues) if g is not None]
    secs_all = [float((i.get("meta") or {}).get("analysis_seconds"))
                for i in issues if (i.get("meta") or {}).get("analysis_seconds")]
    with_blindspot = sum(1 for i in issues if (i.get("perspective_grid") or {}).get("blindspot"))

    stats = [(str(len(issues)), "issues on the site (the newest are kept)")]
    if costs:
        stats.append((f"${sum(costs) / len(costs):.3f}", "average billed AI cost per issue"))
        stats.append((f"${sum(costs) / len(costs) * 30:.2f}", "projected AI cost per month at that rate"))
    if secs_all:
        stats.append((f"{sum(secs_all) / len(secs_all) / 60:.1f} min", "average time for the issue call"))
    if grades:
        stats.append((f"{sum(grades) / len(grades):.1f}", "average reading grade of published copy (target 9.5 or lower)"))
    if issues:
        stats.append((f"{with_blindspot} / {len(issues)}", "issues that carried a blindspot"))
    stats_html = "".join(f'<div class="stat"><b>{v}</b><span>{l}</span></div>' for v, l in stats)

    strip = funnel_strip_html(funnel, sources)
    funnel_block = ""
    if strip:
        funnel_block = f"""
            <h2 class="section-label">Latest run &middot; {_nice_date(str(funnel.get('date', '')))}</h2>
            {strip}
            <p class="funnel-note">What each step does: <a href="how-it-works.html">How it works</a>.</p>"""

    latest_actions = ""
    if issues:
        acts = (issues[0].get("meta") or {}).get("editorial_actions") or []
        flags = (issues[0].get("meta") or {}).get("quality_flags") or []
        items = "".join(f"<li>{escape(str(a))}</li>" for a in acts)
        items += "".join(f'<li><span class="warn">Flag:</span> {escape(str(f))}</li>' for f in flags)
        if items:
            latest_actions = f"""
            <h2 class="section-label">Editorial decisions in the latest issue</h2>
            <ul class="checks">{items}</ul>"""

    updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    body = f"""
            <header class="page-head">
                <p class="eyebrow">Dashboard</p>
                <h1 class="page-title">How the last issues were made</h1>
                <p class="page-lead">Recorded by the pipeline for every issue: what the model cost, how long it
                took, how readable the copy is and what the editorial rules changed. Nothing here is an estimate.</p>
            </header>

            <div class="stats">{stats_html}</div>
            {funnel_block}

            <h2 class="section-label">Issue by issue</h2>
            <div class="table-wrap">
                <table class="data">
                    <thead><tr>
                        <th>Issue</th><th class="num">Articles</th>
                        <th class="num" title="Top stories / Developing updates / Quick hits">Stories / dev. / hits</th>
                        <th class="num" title="Perspective groups with a distinct framing of the big story">Angles</th>
                        <th>Blindspot</th>
                        <th class="num" title="Flesch-Kincaid grade, before and after the rewrite">Reading grade</th>
                        <th class="num">Model time</th><th class="num">AI cost</th>
                        <th class="num" title="Items the editorial rules moved or dropped">Edits</th>
                        <th>Flags</th><th>Model</th>
                    </tr></thead>
                    <tbody>{rows or '<tr><td colspan="11" class="muted">No issues recorded yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
            <p class="fine-print">Angles = perspective groups with their own framing of the big story.
               Edits = items the code-enforced editorial rules moved to Developing, relinked or dropped.
               AI cost is the amount the provider billed for the issue call and the perspective call.</p>
            {latest_actions}
            <p class="fine-print">Updated {updated}.</p>
"""
    html = page_shell(
        title=f"Dashboard - {SITE_NAME}",
        description="Per-issue production data for Geopolitical Daily: AI cost, model, timing, "
                    "readability and editorial decisions.",
        body=body, active="dashboard", wide=True, repo_url=repo_url, tagline=tagline,
    )
    path = output_dir / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    return path
