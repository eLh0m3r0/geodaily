"""
Editorial guardrails for generated issues — pure, testable helpers.

The prompts ask for the right things, but models drift; these functions
enforce the rules that a review of the 2026-09 issues showed slipping:

- day-to-day memory: the previous issues' stories, quick hits, big number
  and blindspot (not just story titles) so the brief doesn't repeat itself;
- repeat detection for quick hits and the big number (a repeat is allowed
  only when it carries a new figure — an update, not a rerun);
- sentence-shape stats, so a "simplify" rewrite that chops copy into
  telegraphic fragments can be rejected;
- sentence-case headlines (models alternate between Title Case and
  sentence case from day to day).
"""

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'“‘A-Z0-9])")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Too common to identify an event.
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "after", "over",
    "into", "says", "said", "will", "have", "their", "than", "more", "been",
    "about", "amid", "also", "just", "were", "they", "what", "when", "which",
    "while", "would", "could", "some", "most", "other", "its", "his", "her",
    "has", "was", "are", "not", "but", "new", "who", "two", "one", "three",
}


def _fold(text: str) -> str:
    """Lower-case and strip accents ("El Niño" == "El Nino")."""
    import unicodedata
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def content_words(text: str) -> Set[str]:
    """Lower-cased identifying words (len > 3, no stop words)."""
    return {w for w in re.findall(r"[a-z0-9]+", _fold(text))
            if len(w) > 3 and w not in _STOP}


def overlap(a: str, b: str) -> float:
    """Share of the shorter text's content words that the other text has."""
    wa, wb = content_words(a), content_words(b)
    base = min(len(wa), len(wb))
    if base < 3:
        return 0.0
    return len(wa & wb) / base


def numbers_in(text: str) -> Set[str]:
    """Normalized figures in a text ("74,000" -> "74000"); years excluded."""
    found = set()
    for raw in _NUMBER.findall(text or ""):
        n = raw.replace(",", "").rstrip(".")
        if re.fullmatch(r"(19|20)\d\d", n):
            continue
        if n:
            found.add(n)
    return found


def is_repeat(text: str, prior_texts: Iterable[str], threshold: float = 0.65) -> Optional[str]:
    """The prior text this one merely repeats, or None.

    A high word overlap is a repeat unless the new text carries a figure the
    old one didn't (a rising death toll, a final vote count): that is an
    update and stays."""
    new_numbers = numbers_in(text)
    # A distinctive figure (not a small count) shared with a prior item on
    # the same topic marks a rerun even when the wording changed.
    distinctive = {n for n in new_numbers if len(n.replace(".", "")) >= 4}
    for prior in prior_texts:
        if not prior:
            continue
        score = overlap(text, prior)
        if score >= threshold:
            if new_numbers - numbers_in(prior):
                continue
            return prior
        shared_figures = distinctive & numbers_in(prior)
        if shared_figures:
            shared_words = len(content_words(text) & content_words(prior))
            longest = max(len(n.replace(".", "")) for n in shared_figures)
            if shared_words >= 2 or (shared_words >= 1 and longest >= 5):
                return prior
    return None


# ----------------------------------------------------------------------
# Sentence shape
# ----------------------------------------------------------------------

def sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split((text or "").strip()) if s.strip()]


def sentence_stats(texts: Iterable[str]) -> Tuple[float, float]:
    """(average words per sentence, share of fragments under 7 words)."""
    lengths = []
    for t in texts:
        for s in sentences(t):
            n = len(_WORD.findall(s))
            if n:
                lengths.append(n)
    if not lengths:
        return 0.0, 0.0
    avg = sum(lengths) / len(lengths)
    fragments = sum(1 for n in lengths if n < 7) / len(lengths)
    return round(avg, 1), round(fragments, 2)


# Copy below this average reads as a telegram ("Kyiv is short. It needs
# more."); above the fragment share it reads as bullet points in prose.
MIN_AVG_SENTENCE_WORDS = 10.5
MAX_FRAGMENT_SHARE = 0.25


def reads_choppy(texts: Iterable[str]) -> bool:
    avg, frag = sentence_stats(texts)
    return avg < MIN_AVG_SENTENCE_WORDS or frag > MAX_FRAGMENT_SHARE


# ----------------------------------------------------------------------
# Headlines
# ----------------------------------------------------------------------

_ALWAYS_LOWER = {
    "a", "an", "the", "and", "or", "but", "nor", "of", "to", "in", "on", "at",
    "for", "with", "as", "by", "from", "into", "over", "after", "before",
    "about", "amid", "than", "via", "vs", "is", "are", "was", "be", "its",
    "their", "his", "her", "it", "up", "out", "off", "down", "if", "so",
    # headline words that are never proper nouns on their own
    "first", "second", "third", "fourth", "fifth", "last", "next", "new",
    "says", "said", "say", "will", "may", "could", "would", "can", "not",
    "no", "all", "more", "most", "less", "year", "years", "day", "days",
    "week", "weeks", "month", "months", "war", "talks", "deal", "plan",
    "plans", "vote", "votes", "election", "elections", "court", "police",
}


def _stem(word: str) -> str:
    w = word.lower().replace("’", "'")
    if w.endswith("'s"):
        w = w[:-2]
    for suffix in ("ing", "ed", "es", "s"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _looks_title_case(words: Sequence[str]) -> bool:
    long_words = [w for w in words[1:] if len(w) > 3 and w[0].isalpha()]
    if len(long_words) < 3:
        return False
    capped = sum(1 for w in long_words if w[0].isupper())
    return capped / len(long_words) >= 0.75


def _case_evidence(corpus: str) -> Dict[str, List[int]]:
    """stem -> [lower-case uses, capitalized uses], counting only words
    inside a sentence (a sentence-initial capital proves nothing)."""
    evidence: Dict[str, List[int]] = {}
    for sent in re.split(r"(?<=[.!?:;])\s+|\n+", corpus or ""):
        words = re.findall(r"[A-Za-z][A-Za-z'’]*", sent)
        for w in words[1:]:
            if w.isupper() and len(w) > 1:
                continue
            e = evidence.setdefault(_stem(w), [0, 0])
            e[0 if w[0].islower() else 1] += 1
    return evidence


def to_sentence_case(title: str, reference_text: str = "") -> str:
    """Convert a Title Case Headline to sentence case, keeping proper nouns.

    Every capitalized word after the first needs evidence: a function or
    stock headline word, or a stem the reference text (story body plus the
    day's article pool) uses in lower case more often than capitalized, is
    lowered; a stem it capitalizes is a proper noun and stays. If any word
    has no evidence either way, the headline is returned unchanged — a
    half-converted "Houthi Rebels Seize Yemen's Mokha port" is worse than
    consistent Title Case."""
    if not title:
        return title
    tokens = title.split(" ")
    if not _looks_title_case(tokens):
        return title
    evidence = _case_evidence(reference_text)
    out = [tokens[0]]
    after_colon = tokens[0].endswith(":")
    for tok in tokens[1:]:
        if after_colon:
            out.append(tok)
            after_colon = tok.endswith(":")
            continue
        new_parts = []
        for part in tok.split("-"):
            m = re.match(r"^([^A-Za-z]*)([A-Za-z][A-Za-z'’]*)(.*)$", part)
            if not m:
                new_parts.append(part)
                continue
            pre, word, post = m.groups()
            if word[0].isupper() and not (word.isupper() and len(word) > 1) \
                    and not any(c.isupper() for c in word[1:]):
                low = word.lower()
                lower_uses, cap_uses = evidence.get(_stem(word), [0, 0])
                if low in _ALWAYS_LOWER or lower_uses > cap_uses:
                    word = low
                elif cap_uses == 0:
                    return title  # no evidence: don't half-convert
            new_parts.append(pre + word + post)
        out.append("-".join(new_parts))
        after_colon = tok.endswith(":")
    return " ".join(out)


# ----------------------------------------------------------------------
# Issue history
# ----------------------------------------------------------------------

def load_issue_history(newsletters_dir: Path, days: int = 3,
                       today: Optional[date] = None) -> List[dict]:
    """The last `days` published issues BEFORE today, newest first, reduced
    to what the next issue must not repeat."""
    today = today or datetime.now().date()
    history = []
    for path in sorted(Path(newsletters_dir).glob("newsletter-*.json"), reverse=True):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        if not m:
            continue
        try:
            issue_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if issue_date >= today:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Skipping unreadable issue JSON {path}: {e}")
            continue
        grid = data.get("perspective_grid") or {}
        bn = data.get("big_number") or {}
        history.append({
            "date": m.group(1),
            "stories": [s.get("story_title", "") for s in data.get("stories", [])],
            "quick_hits": [h.get("text", "") for h in data.get("quick_hits", [])],
            "big_number": (f"{bn.get('value', '')} — {bn.get('context', '')}" if bn else ""),
            "blindspot": grid.get("blindspot", "") or "",
        })
        if len(history) >= days:
            break
    return history


def history_texts(history: List[dict], *keys: str) -> List[str]:
    """Flatten the given fields of the history into one list of texts."""
    texts: List[str] = []
    for day in history:
        for key in keys:
            value = day.get(key)
            if isinstance(value, list):
                texts.extend(v for v in value if v)
            elif value:
                texts.append(value)
    return texts


def format_history_block(history: List[dict]) -> str:
    """Prompt block listing what recent issues already told the reader."""
    if not history:
        return ""
    lines = []
    for day in history:
        lines.append(f"{day['date']}:")
        for t in day["stories"]:
            lines.append(f"  STORY: {t}")
        for t in day["quick_hits"]:
            lines.append(f"  QUICK HIT: {t}")
        if day["big_number"]:
            lines.append(f"  BIG NUMBER: {day['big_number']}")
        if day["blindspot"]:
            lines.append(f"  BLINDSPOT: {day['blindspot']}")
    return (
        "\nALREADY TOLD TO THE READER IN RECENT ISSUES (newest first):\n"
        + "\n".join(lines)
        + "\nDo not repeat any of these — not as a story, quick hit, big number or "
        "blindspot. A running story may return only with a genuinely new development, "
        "and then the copy must lead with what is new since the last issue.\n"
    )
