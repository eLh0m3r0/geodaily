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

# Words too generic to identify a story's subject
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "with",
    "over", "after", "amid", "as", "its", "his", "her", "their", "new",
    "says", "said", "will", "would", "could", "may", "might", "talks",
    "deal", "plan", "vote", "war", "crisis", "power", "world", "global",
}


def _keywords(story: AIAnalysis, max_terms: int = 6) -> List[str]:
    """Salient terms from the story title — capitalized tokens first
    (names/places), then remaining long words."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", story.story_title)
    named = [w for w in words if w[0].isupper() and w.lower() not in _STOPWORDS]
    other = [w for w in words if not w[0].isupper()
             and w.lower() not in _STOPWORDS and len(w) > 4]
    seen, result = set(), []
    for w in named + other:
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            result.append(w)
    return result[:max_terms]


def polymarket_signal(story: AIAnalysis) -> Optional[Signal]:
    """Highest-volume active Polymarket market matching the story's subject."""
    try:
        keywords = [k.lower() for k in _keywords(story)]
        if not keywords:
            return None
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

        best, best_hits = None, 0
        for market in markets:
            question = (market.get("question") or "").lower()
            hits = sum(1 for k in keywords if k in question)
            if hits > best_hits:
                best, best_hits = market, hits
        # One name match ("Iran") on a top market is meaningful; zero is noise.
        if not best or best_hits < 1:
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
        keywords = _keywords(story, max_terms=2)
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
