"""
Readability gate for generated newsletter copy.

Successful mass-audience news writes at US grade 6-9 (BBC ~6.3, NYT ~8-9);
the old think-tank register scored well above that and drove churn. This
module scores generated copy with Flesch-Kincaid so the analyzer can trigger
one "simplify" rewrite when a draft comes back too dense.

Self-contained on purpose: textstat's current syllable backend downloads
NLTK data at runtime, which is flaky in CI and blocked in offline sandboxes.
A vowel-group syllable estimate is within ~±0.5 grade of dictionary-based
counts — plenty for a pass/fail gate.
"""

import logging
import re
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
_WORD = re.compile(r"[A-Za-z']+")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def _count_syllables(word: str) -> int:
    """Estimate syllables by counting vowel groups, with common corrections."""
    w = word.lower().strip("'")
    if not w:
        return 0
    groups = len(_VOWEL_GROUP.findall(w))
    # Silent trailing 'e' ("state" -> 1 group counted twice otherwise)
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and groups > 1:
        groups -= 1
    # "-ed" after a consonant is usually silent ("walked")
    if w.endswith("ed") and len(w) > 4 and w[-3] not in "aeiouydt" and groups > 1:
        groups -= 1
    return max(1, groups)


def _sentences(text: str) -> List[str]:
    return [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def flesch_kincaid_grade(text: str) -> Optional[float]:
    """Flesch-Kincaid grade of a text, or None when it can't be scored."""
    if not text:
        return None
    words = _WORD.findall(text)
    if len(words) < 10:
        return None
    sentences = max(1, len(_sentences(text)))
    syllables = sum(_count_syllables(w) for w in words)
    grade = 0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59
    return round(grade, 2)


def combined_grade(texts: Iterable[str]) -> Optional[float]:
    """Grade of all passages joined together (per-passage texts are too short
    for a stable score, so score the concatenation)."""
    joined = ". ".join(t.strip().rstrip(".") for t in texts if t and t.strip())
    return flesch_kincaid_grade(joined)
