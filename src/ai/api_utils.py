"""
Shared helpers for Claude API integration.

Centralizes response handling and cost accounting so every analyzer treats the
API the same way:
- Models with adaptive thinking (Sonnet 5+) may return thinking blocks before
  the text block, so `response.content[0].text` is not safe — use
  extract_response_text() instead.
- Cost tracking should use the real token counts from `response.usage`, not
  word-count guesses.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

from ..config import Config


def extract_response_text(response) -> str:
    """Concatenate all text blocks from a Messages API response.

    Skips thinking/tool blocks that adaptive-thinking models may emit before
    the text. Returns an empty string if no text block is present.
    """
    parts = []
    for block in getattr(response, 'content', []) or []:
        if getattr(block, 'type', None) == 'text':
            parts.append(block.text)
    return "".join(parts)


def response_tokens_and_cost(response, prompt: str = "", response_text: str = "") -> Tuple[int, int, float]:
    """Return (input_tokens, output_tokens, cost_usd) for an API response.

    Prefers the authoritative `response.usage` counts; falls back to a rough
    word-count estimate only if usage is missing (e.g. mocked responses).
    """
    usage = getattr(response, 'usage', None)
    input_tokens = getattr(usage, 'input_tokens', None) if usage else None
    output_tokens = getattr(usage, 'output_tokens', None) if usage else None

    if input_tokens is None:
        input_tokens = int(len(prompt.split()) * 1.3)
    if output_tokens is None:
        output_tokens = int(len(response_text.split()) * 1.3)

    cost = (input_tokens / 1_000_000) * Config.AI_INPUT_COST_PER_MTOK \
         + (output_tokens / 1_000_000) * Config.AI_OUTPUT_COST_PER_MTOK
    return int(input_tokens), int(output_tokens), cost


def load_recent_newsletter_titles(days_back: Optional[int] = None) -> str:
    """Load story titles from recently published newsletters.

    Used to steer the model away from repeating topics covered in the last
    few days. Returns a short plain-text digest, or '' when no history exists.
    """
    if days_back is None:
        days_back = Config.NEWSLETTER_HISTORY_DAYS

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""

    entries = []
    today = datetime.now().date()
    for i in range(1, days_back + 1):
        date_str = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        path = os.path.join("docs", "newsletters", f"newsletter-{date_str}.html")
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            titles = [el.get_text().strip() for el in soup.find_all('h2', class_='story-title')]
            if titles:
                entries.append(f"Day -{i} ({date_str}): {' | '.join(titles)}")
        except Exception:
            continue

    return "\n".join(entries)
