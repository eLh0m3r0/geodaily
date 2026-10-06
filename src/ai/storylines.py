"""
Storylines: recognise that today's item continues something the reader
already has.

Word-overlap repeat checks miss continuations because each day's copy is
worded differently ("Tigray forces seize Mekelle airport" → "Ethiopian
troops seize Mekelle" → "Airstrikes and forced recruitment as Ethiopia's
Tigray war returns"). What stays constant is the handful of proper names
that identify the event — Tigray, Mekelle, flydubai, RAF Fairford. A
storyline is the set of those DISTINCTIVE names; generic actors (Russia,
Trump, NATO, oil) appear in unrelated stories every day and never count.

Used for: the DEVELOPING section (running stories get one line instead of a
story slot), the blindspot screen (a blindspot is never our own running
story — 2026-10-05 ran flydubai as the "story the West missed" after four
days of covering it), and the perspective-grid member filter.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

# Actors and places that recur across unrelated stories every day. A match
# on one of these alone never ties two items to the same storyline.
GENERIC_TERMS = frozenset("""
trump biden putin xi zelensky zelenskyy netanyahu musk modi erdogan macron starmer
burnham merz sanchez lula khamenei pezeshkian kim
russia russian russians china chinese iran iranian israel israeli israelis ukraine
ukrainian ukrainians america american americans europe european europeans
us u.s. usa uk britain british england german germany france french india
indian pakistan pakistani turkey turkish turkiye saudi arabia uae japan japanese
korea korean canada canadian australia australian mexico egypt qatar
united states united kingdom european union north korea south korea saudi arabia
nato eu un g7 g20 imf who opec iea iaea brics asean wto
congress senate parliament white house kremlin pentagon downing street
washington moscow beijing tehran kyiv london paris berlin brussels jerusalem
gaza west bank taiwan middle east asia africa african latin
oil diesel gas fuel tariffs tariff election elections war ceasefire sanctions
""".split()) | frozenset({
    "united states", "united kingdom", "european union", "north korea",
    "south korea", "saudi arabia", "white house", "west bank", "middle east",
    "downing street", "latin america", "us president", "prime minister",
})

# Capitalised words that are titles, months or sentence furniture, not names
_COMMON_CAPS = frozenset("""
the a an and or but of in on at for with as by from to into after before
president prime minister ministers minister's foreign defense defence interior
finance secretary chancellor king queen prince crown pope governor mayor senator
general chief head leader leaders officials official spokesperson spokesman army
navy air force forces military police court supreme high federal national state
states government party parliament council ministry agency department committee
commission union bank central republic kingdom federation coalition alliance
north south east west eastern western northern southern central new old
river bridge island islands sea ocean gulf strait airport base city province
region capital county district
international criminal energy agency organization organisation institute
association fund programme program health world development human rights
security nuclear atomic monetary trade food refugees refugee commissioner
office service services authority authorities group groups network
pacific atlantic arctic mediterranean caribbean indian baltic islamic muslim
christian jewish arab catholic orthodox sunni shia
runoff referendum plague outbreak protest protests strike strikes drone drones
missile missiles bombing bombings attack attacks budget inflation housing migrant
migrants migration talks summit deal vote votes poll polls coup earthquake flood
floods hurricane typhoon cyclone wildfire wildfires famine measles cholera
blockade blockades offensive invasion truce hostages hostage prisoners
intelligence espionage justice education environment labor labour treasury
interior economy economic affairs development planning communications
coast coastal border borders desert mountains valley highlands frontline front
super storm storms tropical quake wildfires heatwave drought monsoon
monday tuesday wednesday thursday friday saturday sunday january february march
april may june july august september october november december
he she they it this that these those his her their its we our i
""".split())

_CAP_SEQ = re.compile(r"\b([A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,2})")
_SENT_START = re.compile(r"(?:^|[.!?:;]\s+|\n)([A-Z][\w'’.-]*)")


def _norm(term: str) -> str:
    t = (term or "").lower().replace("’", "'").strip(" .,'\"")
    if t.endswith("'s"):
        t = t[:-2]
    return t


def _tok(word: str) -> str:
    w = word.lower().replace("’", "'").strip(" .,'\"")
    return w[:-2] if w.endswith("'s") else w


def distinctive_tokens(term: str, any_case: bool = False) -> Set[str]:
    """Patterns that identify `term`.

    Only NAMES count: a token qualifies when it is capitalised in the
    original term, at least 4 letters, and neither a generic actor nor a
    title/month/furniture word ("Dnipro River" -> dnipro; "Vitalii
    Klitschko" -> vitalii, klitschko; "Russia" -> nothing; "housing
    protests" -> nothing). Long organisation names ("International Energy
    Agency") match only as the whole phrase — their words are ordinary
    English. A multiword phrase is kept when it contains a name token or a
    digit ("B-1 bombers")."""
    raw = (term or "").strip()
    phrase = _norm(raw)
    if not phrase or phrase in GENERIC_TERMS:
        return set()
    words = [w for w in re.split(r"[\s]+", raw) if w]
    name_tokens = set()
    for w in words:
        t = _tok(w)
        if ((any_case or w[:1].isupper()) and len(t) >= 4 and t not in GENERIC_TERMS
                and t not in _COMMON_CAPS and not t.isdigit()):
            name_tokens.add(t)
    out = set()
    if len(words) > 1 and (name_tokens or re.search(r"\d", phrase)):
        out.add(phrase)
    return out | name_tokens


def proper_terms(text: str) -> Set[str]:
    """Name-like terms of free text: capitalised words not at a sentence
    start (where any word is capitalised), reduced to distinctive tokens."""
    text = text or ""
    starts = {m.start(1) for m in _SENT_START.finditer(text)}
    terms: Set[str] = set()
    for m in _CAP_SEQ.finditer(text):
        seq = m.group(1)
        if m.start(1) in starts:
            # drop the sentence-initial word, keep any name that follows it
            parts = seq.split(None, 1)
            if len(parts) < 2:
                continue
            seq = parts[1]
        terms |= distinctive_tokens(seq)
    return terms


def text_has(text_lower: str, pattern: str) -> bool:
    """Whole-word match; single names of 5+ letters also match with a short
    suffix, so "Siberia" finds "Siberian" and "Tigray" finds "Tigrayan"."""
    suffix = r"\w{0,3}" if " " not in pattern and len(pattern) >= 5 else ""
    return re.search(r"(?<![\w])" + re.escape(pattern) + suffix + r"(?![\w])", text_lower) is not None


@dataclass
class Entry:
    date: str
    kind: str            # story | quick_hit | developing | big_number | blindspot
    text: str
    terms: Set[str] = field(default_factory=set)


class StorylineIndex:
    """What the last issues covered, keyed by distinctive names."""

    def __init__(self, history: Sequence[dict]):
        """`history`: editorial.load_issue_history() output, newest first."""
        self.history = list(history)
        self.entries: List[Entry] = []
        self.dates: List[str] = []
        for day in history:
            d = day.get("date", "")
            self.dates.append(d)
            for title, sig in zip(day.get("stories", []),
                                  day.get("story_terms", []) or [[]] * len(day.get("stories", []))):
                terms = proper_terms(title)
                for t in sig or []:
                    terms |= distinctive_tokens(t, any_case=" " not in t.strip())
                self.entries.append(Entry(d, "story", title, terms))
            for kind in ("quick_hits", "developing"):
                for text in day.get(kind, []) or []:
                    self.entries.append(Entry(d, kind.rstrip("s") if kind == "quick_hits" else kind,
                                              text, proper_terms(text)))
            for kind in ("big_number", "blindspot"):
                if day.get(kind):
                    self.entries.append(Entry(d, kind, day[kind], proper_terms(day[kind])))

    def _recent(self, days: int, kinds: Optional[Iterable[str]]) -> List[Entry]:
        keep = set(self.dates[:days])
        kinds = set(kinds) if kinds else None
        return [e for e in self.entries if e.date in keep and (kinds is None or e.kind in kinds)]

    def match(self, text: str, extra_terms: Iterable[str] = (), days: int = 3,
              kinds: Optional[Iterable[str]] = None) -> Optional[tuple]:
        """(entry, term) for the most recent covered item that shares a
        distinctive name with `text` (+ `extra_terms`, e.g. signal_terms),
        or None."""
        low = _norm(text)
        own = set(proper_terms(text))
        for t in extra_terms or ():
            own |= distinctive_tokens(t, any_case=" " not in t.strip())
        for entry in self._recent(days, kinds):
            for term in sorted(entry.terms, key=len, reverse=True):
                if term in own or text_has(low, term):
                    return entry, term
        return None

    def running_storylines(self, days: int = 3) -> List[Dict[str, object]]:
        """Storylines that were a STORY in the last `days` issues, merged by
        shared names, newest first — the prompt's "running stories" list."""
        groups: List[Dict[str, object]] = []
        for e in self._recent(days, {"story"}):
            if not e.terms:
                continue
            for g in groups:
                if g["terms"] & e.terms:
                    g["terms"] |= e.terms
                    g["dates"].add(e.date)
                    break
            else:
                groups.append({"terms": set(e.terms), "dates": {e.date}, "latest": e.text})
        return groups


def label_for(term: str) -> str:
    """Display label for a storyline term ("raf fairford" -> "RAF Fairford")."""
    words = term.split()
    return " ".join(w.upper() if len(w) <= 3 and w.isalpha() else w.capitalize() for w in words)
