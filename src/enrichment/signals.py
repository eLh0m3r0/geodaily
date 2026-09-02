"""
Signals: real-world numbers attached to the big story.

- Polymarket (free Gamma API, no key): a live prediction-market probability
  related to the big story, so "what to watch" carries actual odds.
- GDELT Doc API (free, no key): 7-day news-volume trend for the story's
  main actor, e.g. "coverage tripled this week".

Everything here is strictly fail-soft: any network/parse problem returns
fewer signals, never an exception — the newsletter ships without the block.
"""

import logging
import re
from typing import List, Optional

import requests

from ..models import AIAnalysis, Signal
from ..config import Config

logger = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMEOUT = 12

# Words too generic to identify a story's subject (title-derived fallback)
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with",
    "over", "after", "amid", "as", "its", "his", "her", "their", "new",
    "says", "said", "will", "would", "could", "may", "might", "talks",
    "deal", "plan", "vote", "war", "crisis", "power", "world", "global",
    # generic actors/verbs that match unrelated markets ("us" matched "Jesus")
    "us", "u.s.", "usa", "trade", "trades", "strike", "strikes", "again",
    "month", "six-month", "escalates", "escalation", "hits", "tops", "passes",
    "still", "missing", "toll", "death", "kills", "killed", "expels", "blames",
    "resigns", "quits", "meets", "agrees", "signs", "warns", "claims", "denies",
    "threatens", "tensions", "rift", "flares", "flare", "thousands", "hundreds",
}

# Market subjects that are never a geopolitical signal, however popular
_JUNK_MARKET = re.compile(
    r"\b(jesus|christ|god|alien|aliens|ufo|bitcoin|btc|ethereum|solana|crypto|"
    r"nba|nfl|nhl|mlb|ufc|super bowl|world series|oscars?|grammys?|emmys?|"
    r"taylor swift|kanye|drake|mrbeast|gta|fortnite|eurovision|bachelor|"
    r"temperature|hottest|rainfall|tweets?)\b", re.IGNORECASE)


def _keywords(story: AIAnalysis, max_terms: int = 6) -> List[str]:
    """Salient terms from the story title — capitalized tokens first
    (names/places), then remaining long words. Fallback only: analyzer-
    supplied signal_terms are far more precise (see _search_terms)."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", story.story_title)
    named = [w for w in words if w[0].isupper() and w.lower() not in _STOPWORDS
             and len(w) >= 4]
    other = [w for w in words if not w[0].isupper()
             and w.lower() not in _STOPWORDS and len(w) > 4]
    seen, result = set(), []
    for w in named + other:
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            result.append(w)
    return result[:max_terms]


def _search_terms(story: AIAnalysis) -> tuple:
    """(terms, precise): analyzer-supplied proper nouns when present
    (precise=True), else title-derived words (precise=False)."""
    terms = [t for t in (getattr(story, 'signal_terms', None) or [])
             if isinstance(t, str) and len(t.strip()) >= 3
             and t.strip().lower() not in _STOPWORDS]
    if terms:
        return terms[:4], True
    return _keywords(story, max_terms=5), False


def _term_hits(text: str, terms: List[str]) -> int:
    """Whole-word / whole-phrase matches — never substrings, so "US" can no
    longer hit "Jesus" and "Iran" can no longer hit "Iranian-American"
    by accident... (word boundaries on both sides)."""
    low = text.lower()
    hits = 0
    for term in terms:
        t = term.strip().lower()
        if not t:
            continue
        if re.search(r"\b" + re.escape(t) + r"\b", low):
            hits += 1
            continue
        # Multi-word term: its distinctive words count too ("Hormuz")
        parts = [w for w in re.findall(r"[a-z][a-z'-]+", t)
                 if len(w) >= 5 and w not in _STOPWORDS]
        if len(parts) > 1 and any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in parts):
            hits += 1
    return hits


def match_market(markets: list, story: AIAnalysis) -> Optional[dict]:
    """Best market for the story, or None. Markets are expected sorted by
    volume (desc); ties go to the higher-volume one. Precise (analyzer)
    terms need one whole-word hit; title-derived terms need two, because a
    single generic title word on the most-traded meme market is exactly how
    "Will Jesus Christ return before 2027?" once ended up under an Iran story."""
    terms, precise = _search_terms(story)
    if not terms:
        return None
    min_hits = 1 if precise else 2
    best, best_hits = None, 0
    for market in markets:
        question = (market.get("question") or "").strip()
        if not question or _JUNK_MARKET.search(question):
            continue
        hits = _term_hits(question, terms)
        if hits > best_hits:
            best, best_hits = market, hits
    if best is None or best_hits < min_hits:
        return None
    return best


def polymarket_signal(story: AIAnalysis) -> Optional[Signal]:
    """Highest-volume active Polymarket market genuinely about the story."""
    try:
        resp = requests.get(
            GAMMA_MARKETS_URL,
            params={"closed": "false", "active": "true",
                    "order": "volumeNum", "ascending": "false", "limit": 200},
            headers={"User-Agent": Config.USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        markets = resp.json()
        if not isinstance(markets, list):
            return None

        best = match_market(markets, story)
        if not best:
            logger.info("Polymarket: no market matches the story's terms — no signal")
            return None

        prices = best.get("outcomePrices")
        if isinstance(prices, str):
            import json as _json
            prices = _json.loads(prices)
        if not prices:
            return None
        probability = round(float(prices[0]) * 100)
        if probability <= 1 or probability >= 99:
            return None
        slug = best.get("slug", "")
        url = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"
        return Signal(
            text=f'Polymarket puts "{best.get("question", "").strip()}" at {probability}%.',
            url=url,
            source="Polymarket",
        )
    except Exception as e:
        logger.info(f"Polymarket signal unavailable: {e}")
        return None


def gdelt_trend_signal(story: AIAnalysis) -> Optional[Signal]:
    """7-day vs prior-7-day global news volume trend for the story's main actor."""
    try:
        keywords, _precise = _search_terms(story)
        keywords = keywords[:2]
        if not keywords:
            return None
        query = " ".join(keywords)
        resp = requests.get(
            GDELT_DOC_URL,
            params={"query": query, "mode": "timelinevol",
                    "timespan": "14d", "format": "json"},
            headers={"User-Agent": Config.USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        series = (data.get("timeline") or [{}])[0].get("data") or []
        if len(series) < 10:
            return None
        values = [point.get("value", 0.0) for point in series]
        half = len(values) // 2
        prior, recent = sum(values[:half]), sum(values[half:])
        if prior <= 0 or recent <= 0:
            return None
        ratio = recent / prior
        if ratio >= 1.8:
            text = f"Global news coverage of {keywords[0]} is up {ratio:.1f}x week-over-week."
        elif ratio <= 0.55:
            text = f"Global news coverage of {keywords[0]} fell {1 / ratio:.1f}x week-over-week."
        else:
            return None  # a flat trend is not a signal
        return Signal(text=text, source="GDELT",
                      url=f"https://api.gdeltproject.org/api/v2/doc/doc?query={requests.utils.quote(query)}&mode=timelinevol&timespan=14d")
    except Exception as e:
        logger.info(f"GDELT signal unavailable: {e}")
        return None


def collect_signals(story: AIAnalysis) -> List[Signal]:
    """All available signals for the big story (possibly empty, never raises)."""
    if Config.DRY_RUN:
        return [Signal(text='(mock) Polymarket puts "US-Iran military confrontation '
                            'by year end" at 23%.', url="https://polymarket.com",
                       source="Polymarket")]
    signals = []
    for fn in (polymarket_signal, gdelt_trend_signal):
        signal = fn(story)
        if signal:
            signals.append(signal)
    return signals
