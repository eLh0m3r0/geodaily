"""
Human-readable source attribution for newsletter output.

Turns raw article URLs into named, deduplicated outlet links so readers see
"South China Morning Post" instead of "scmp.com" — and never the same domain
twice under one story. Outlet names come from sources.json (each source may
declare an explicit "site" domain) with a static fallback map for domains
whose feed URL lives on a different host than their articles.
"""

from functools import lru_cache
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from ..config import Config

# Multi-part TLDs where the registrable domain needs three labels.
_TWO_LEVEL_TLDS = {
    "co.uk", "org.uk", "ac.uk", "com.au", "org.au", "net.au", "co.nz",
    "co.za", "com.br", "com.cn", "com.hk", "com.sg", "co.in", "co.jp",
    "or.jp", "com.tr", "com.pk", "co.ke",
}

# Fallback names for article domains that can't be derived from sources.json
# (feed hosted off-site, historic sources, syndication domains).
_KNOWN_DOMAINS: Dict[str, str] = {
    "bbc.com": "BBC", "bbc.co.uk": "BBC",
    "theguardian.com": "The Guardian",
    "aljazeera.com": "Al Jazeera",
    "ft.com": "Financial Times",
    "npr.org": "NPR",
    "foreignaffairs.com": "Foreign Affairs",
    "thediplomat.com": "The Diplomat",
    "foreignpolicy.com": "Foreign Policy",
    "atlanticcouncil.org": "Atlantic Council",
    "ecfr.eu": "ECFR",
    "gmfus.org": "German Marshall Fund",
    "crisisgroup.org": "International Crisis Group",
    "hrw.org": "Human Rights Watch",
    "warontherocks.com": "War on the Rocks",
    "france24.com": "France 24",
    "scmp.com": "South China Morning Post",
    "asiatimes.com": "Asia Times",
    "middleeasteye.net": "Middle East Eye",
    "al-monitor.com": "Al-Monitor",
    "responsiblestatecraft.org": "Responsible Statecraft",
    "theafricareport.com": "The Africa Report",
    "africanarguments.org": "African Arguments",
    "aspistrategist.org.au": "ASPI Strategist",
    "bellingcat.com": "Bellingcat",
    "justsecurity.org": "Just Security",
    "38north.org": "38 North",
    "breakingdefense.com": "Breaking Defense",
    "politico.eu": "Politico Europe",
    "meduza.io": "Meduza",
    "themoscowtimes.com": "The Moscow Times",
    "defenseone.com": "Defense One",
    "worldpoliticsreview.com": "World Politics Review",
}


def registrable_domain(url: str) -> str:
    """Return the registrable domain of a URL ("www.scmp.com/x" -> "scmp.com")."""
    try:
        netloc = urlparse(url).netloc or url
    except Exception:
        netloc = url
    netloc = netloc.lower().split(":")[0].removeprefix("www.")
    parts = netloc.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL_TLDS:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return netloc


def _clean_feed_name(name: str) -> str:
    """Strip feed-listing artifacts from a source name ("SCMP RSS" -> "SCMP")."""
    for suffix in (" RSS", " Feed", " (English)"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


@lru_cache(maxsize=1)
def _sources_domain_map() -> Dict[str, str]:
    """Map registrable domain -> outlet display name.

    Precedence (weakest to strongest): cleaned source name from sources.json,
    the curated _KNOWN_DOMAINS names, then an explicit "display" field on a
    source entry. Sources may declare a "site" domain when their feed URL
    lives on a different host than their articles.
    """
    from_config: Dict[str, str] = {}
    explicit: Dict[str, str] = {}
    try:
        sources = Config.load_sources()
    except Exception:
        sources = {}
    for tier in sources.values():
        if not isinstance(tier, list):
            continue
        for entry in tier:
            name = entry.get("name")
            if not name:
                continue
            site = entry.get("site")
            domain = registrable_domain(site) if site else registrable_domain(entry.get("url", ""))
            if not domain:
                continue
            if entry.get("display"):
                explicit.setdefault(domain, entry["display"])
            from_config.setdefault(domain, _clean_feed_name(name))
    return {**from_config, **_KNOWN_DOMAINS, **explicit}


def source_display_name(url: str) -> str:
    """Human-readable outlet name for an article URL (falls back to the domain)."""
    domain = registrable_domain(url)
    return _sources_domain_map().get(domain, domain)


def dedupe_sources(urls: List[str], limit: int = 5) -> List[Tuple[str, str]]:
    """Deduplicate source URLs by outlet domain.

    Returns up to `limit` (url, display_name) pairs, keeping the first URL
    seen per domain — one story must never cite the same outlet twice.
    """
    seen = set()
    result: List[Tuple[str, str]] = []
    for url in urls:
        if not url or url == "No source":
            continue
        domain = registrable_domain(url)
        if domain in seen:
            continue
        seen.add(domain)
        result.append((url, source_display_name(url)))
        if len(result) >= limit:
            break
    return result
