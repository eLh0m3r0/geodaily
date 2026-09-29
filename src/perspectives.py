"""
Perspective taxonomy shared by the analyzer, enrichment and renderers.

Source-level axes (sources.json `perspective`) roll up into display groups —
the rows of the "How the world covers it" grid. Grouping keeps the grid at
3-6 legible rows instead of 14.
"""

from typing import Dict, List

# axis -> display group
GROUP_OF: Dict[str, str] = {
    "western_mainstream": "western",
    "western_analysis": "western",
    "east_asia": "east_asia",
    "chinese_state": "chinese_state",
    "south_asia": "south_asia",
    "middle_east": "middle_east",
    "iranian_state": "middle_east_state",
    "turkish_state": "middle_east_state",
    "russian_state": "russian_state",
    "russian_exile": "russian_exile",
    "ukrainian": "ukrainian",
    "african": "african",
    "latam": "latam",
    "global_south": "global_south",
    "intl_org": "intl_org",
}

GROUP_LABELS: Dict[str, str] = {
    "western": "Western media",
    "east_asia": "East Asian media",
    "chinese_state": "Chinese state media",
    "south_asia": "South Asian media",
    "middle_east": "Middle East media",
    "middle_east_state": "Regional state media",
    "russian_state": "Russian state media",
    "russian_exile": "Russian independent media",
    "ukrainian": "Ukrainian media",
    "african": "African media",
    "latam": "Latin American media",
    "global_south": "Global South voices",
    "intl_org": "International organizations",
}

# Groups whose members are (mostly) state-controlled — rendered with a label
STATE_GROUPS = {"chinese_state", "russian_state", "middle_east_state"}

# Non-western groups for blindspot detection (a story living only here is
# invisible to a Western reader — that's the interesting asymmetry)
NON_WESTERN_GROUPS = {
    "east_asia", "chinese_state", "south_asia", "middle_east",
    "middle_east_state", "russian_state", "russian_exile", "ukrainian",
    "african", "latam", "global_south",
}

# Render order for grid rows
GROUP_ORDER: List[str] = [
    "western", "east_asia", "chinese_state", "south_asia", "middle_east",
    "middle_east_state", "russian_state", "russian_exile", "ukrainian",
    "african", "latam", "global_south", "intl_org",
]

# Web/pages coverage-bar colors per group (email uses text proportions)
GROUP_COLORS: Dict[str, str] = {
    "western": "#3E6DB5",
    "east_asia": "#2E8B8B",
    "chinese_state": "#C24C3A",
    "south_asia": "#B8862E",
    "middle_east": "#8A6D3B",
    "middle_east_state": "#A0522D",
    "russian_state": "#7A5AA0",
    "russian_exile": "#9B7EBD",
    "ukrainian": "#D4A017",
    "african": "#3E8A5A",
    "latam": "#C77B3F",
    "global_south": "#5A8A3E",
    "intl_org": "#6B7280",
}


def group_of(perspective: str) -> str:
    return GROUP_OF.get(perspective, "western")


def label_of(group: str) -> str:
    return GROUP_LABELS.get(group, group.replace("_", " ").title())


# Brand stripe: the perspective spectrum in one bar — the visual identity of
# "every side of the story". Order picked for hue contrast between neighbors.
SPECTRUM = [
    GROUP_COLORS["western"], GROUP_COLORS["east_asia"], GROUP_COLORS["chinese_state"],
    GROUP_COLORS["south_asia"], GROUP_COLORS["middle_east"], GROUP_COLORS["russian_state"],
    GROUP_COLORS["african"], GROUP_COLORS["latam"],
]


def spectrum_bar_html(height: int = 4) -> str:
    """Email-safe spectrum stripe (inline-block spans; no flex, no gradients)."""
    width = round(100.0 / len(SPECTRUM), 2)
    spans = "".join(
        f'<span style="display:inline-block;width:{width}%;height:{height}px;'
        f'background-color:{color};"></span>'
        for color in SPECTRUM
    )
    return f'<div style="font-size:0;line-height:0;">{spans}</div>'


def summarize_grid(grid) -> tuple:
    """Render-ready view of a PerspectiveGrid's coverage distribution.

    Returns (parts, legend): parts is a list of dicts (group, label, count,
    pct, color, state) in display order; legend is a one-line text summary
    usable where a graphical bar can't render (email).
    """
    total = sum(grid.counts.values()) or 1
    parts = []
    ordered = [g for g in GROUP_ORDER if g in grid.counts]
    ordered += [g for g in grid.counts if g not in GROUP_ORDER]
    for g in ordered:
        count = grid.counts[g]
        parts.append({
            "group": g,
            "label": label_of(g),
            "count": count,
            "pct": round(100 * count / total),
            "color": GROUP_COLORS.get(g, "#6B7280"),
            "state": g in STATE_GROUPS,
        })
    legend = " · ".join(f"{p['pct']}% {p['label']}" for p in parts)
    return parts, legend


# ----------------------------------------------------------------------
# Shared render helpers (web, email and Pages renderers all use these, so
# the three outputs can't drift apart)
# ----------------------------------------------------------------------

def is_wire_view(view) -> bool:
    """A grid row with no editorial angle of its own (agency copy). Older
    issue JSON carries the sentinel framing instead of the flag."""
    if getattr(view, "wire_copy", False):
        return True
    return (getattr(view, "framing", "") or "").lower().startswith("runs wire copy")


def coverage_summary(total_outlets: int, counts: Dict[str, int]) -> str:
    """'11 reports from 6 outlets' — the bar and per-group numbers count
    REPORTS; saying only 'outlets' next to them read as a contradiction."""
    reports = sum(counts.values()) if counts else 0
    outlets = total_outlets or 0
    if reports and outlets and reports != outlets:
        return f"{reports} reports from {outlets} outlets"
    n = outlets or reports
    return f"{n} outlet{'s' if n != 1 else ''}"


def wire_copy_line(views) -> str:
    """One shared line for groups that ran straight agency copy, e.g.
    'Straight news, no distinct angle: East Asian media (3), Chinese state
    media (2, state)'. Empty when no group qualifies."""
    groups = []
    for v in views:
        if not is_wire_view(v):
            continue
        extra = ", state" if getattr(v, "state_affiliated", False) else ""
        groups.append(f"{label_of(v.perspective)} ({v.article_count}{extra})")
    if not groups:
        return ""
    return "Straight news, no distinct angle: " + ", ".join(groups)


def _join_names(names: List[str]) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def blindspot_sources_line(outlets: List[str], limit: int = 4) -> str:
    """'Reported by Dawn, Meduza and 2 more — no Western outlet we track.'"""
    outlets = [o for o in (outlets or []) if o]
    if not outlets:
        return ""
    shown = outlets[:limit]
    rest = len(outlets) - len(shown)
    names = _join_names(shown) if not rest else ", ".join(shown) + f" and {rest} more"
    return f"Reported by {names} &mdash; no Western outlet we track."
