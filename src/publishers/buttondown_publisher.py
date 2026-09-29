"""
Buttondown publisher for the Geopolitical Daily newsletter.

Publishes each newsletter edition as a Buttondown email via the v1 API.
Runs alongside GitHub Pages — both targets stay live.

Required env vars:
    BUTTONDOWN_API_KEY  - API key from Buttondown → Settings → API Key
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import requests

from ..models import Newsletter
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"

# Buttondown's content filter answers HTTP 400 with e.g.
#   {"code":"email_invalid","detail":"Contains prohibited keyword: Leroy Merlin"}
# (2026-09-18: a news story naming the retailer blocked the whole send).
_PROHIBITED_RE = re.compile(r"prohibited\s+keywords?\s*:\s*(.+)", re.IGNORECASE)
# Invisible joiner inserted inside flagged words: renders identically in every
# mail client but breaks a substring match.
ZERO_WIDTH_JOINER = "\u200d"
# Each rejection names what it found; a retry happens only when it names
# something new, and at most this many times.
MAX_KEYWORD_RETRIES = 2

# Where the daily send records its outcome for the workflow's delivery check
# (env EMAIL_DELIVERY_STATUS_FILE). output/ is gitignored and per-run.
DEFAULT_DELIVERY_STATUS_FILE = "output/email_delivery_status.json"

_TOKEN_RE = re.compile(
    r"(<(?:style|script)\b[^>]*>.*?</(?:style|script)\s*>|<!--.*?-->|<[^>]*>)",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_VALUE_RE = re.compile(r"""(=\s*)("[^"]*"|'[^']*')""")


def extract_prohibited_keywords(response_text: str) -> List[str]:
    """Keywords named by a Buttondown content-filter rejection ([] if none)."""
    if not response_text:
        return []
    candidates = []
    try:
        data = json.loads(response_text)
    except (TypeError, ValueError):
        data = None
    if isinstance(data, dict):
        meta = data.get("metadata") or {}
        for key in ("keywords", "keyword", "prohibited_keywords"):
            value = meta.get(key) if isinstance(meta, dict) else None
            if isinstance(value, str):
                candidates.append(value)
            elif isinstance(value, list):
                candidates.extend(str(v) for v in value)
        texts = [str(data.get("detail") or ""), str(data.get("message") or "")]
    else:
        texts = [response_text]
    for text in texts:
        m = _PROHIBITED_RE.search(text)
        if m:
            candidates.extend(m.group(1).split(","))
    keywords = []
    for kw in candidates:
        kw = kw.strip().strip("\"'“”„.").strip()
        if kw and kw.lower() not in {k.lower() for k in keywords}:
            keywords.append(kw)
    return keywords


def _keyword_regex(keyword: str) -> re.Pattern:
    words = [re.escape(w) for w in keyword.split()]
    return re.compile(r"\s+".join(words), re.IGNORECASE)


def _break_with_joiner(match: re.Match) -> str:
    # ZWJ after the first character of every word: "Leroy Merlin" ->
    # "L\u200deroy M\u200derlin"
    return re.sub(r"(?<!\w)(\w)(?=\w)", lambda m: m.group(1) + ZERO_WIDTH_JOINER, match.group(0))


def _break_with_entity(match: re.Match) -> str:
    # Inside attribute values (alt, title, href...) a joiner would change
    # the value (and break URLs); a numeric character reference decodes to
    # the identical character in the browser.
    return re.sub(r"(?<!\w)(\w)(?=\w)", lambda m: "&#%d;" % ord(m.group(1)), match.group(0))


def neutralize_keywords_text(text: str, keywords: List[str]) -> str:
    """Plain text (subject line): break each keyword with a zero-width joiner."""
    for kw in keywords:
        text = _keyword_regex(kw).sub(_break_with_joiner, text)
    return text


def neutralize_keywords_html(html: str, keywords: List[str]) -> str:
    """HTML body: joiner inside text nodes, character references inside
    attribute values; tag/attribute names, comments, <style> and <script>
    are left untouched so the markup stays valid."""
    patterns = [_keyword_regex(kw) for kw in keywords]
    out = []
    for i, part in enumerate(_TOKEN_RE.split(html)):
        if not part:
            continue
        if i % 2 == 0:          # text node
            for pat in patterns:
                part = pat.sub(_break_with_joiner, part)
        elif part.startswith("<") and not part.startswith("<!--") \
                and not re.match(r"<(?:style|script)\b", part, re.IGNORECASE):
            def _fix_value(m, _pats=patterns):
                value = m.group(2)
                for pat in _pats:
                    value = pat.sub(_break_with_entity, value)
                return m.group(1) + value
            part = _ATTR_VALUE_RE.sub(_fix_value, part)
        out.append(part)
    return "".join(out)


class ButtondownPublisher:
    """Publishes newsletter editions to Buttondown subscribers via the v1 REST API."""

    def __init__(self) -> None:
        self.api_key = Config.BUTTONDOWN_API_KEY
        self.username = Config.BUTTONDOWN_USERNAME
        self.enabled = bool(self.api_key)
        self.last_error: Optional[str] = None
        self._last_failure: Optional[Tuple[int, str]] = None
        if not self.enabled:
            logger.info("Buttondown publisher disabled (BUTTONDOWN_API_KEY not set)")

    def publish(self, newsletter: Newsletter, html_content: str) -> Optional[str]:
        """
        Create and send the daily Buttondown email for a newsletter edition.
        Weekly-digest subscribers (tagged) are excluded — they get the
        Sunday digest instead.

        Returns the archive URL on success, None if disabled or on error.
        A failed send is also made LOUD outside the return value, because
        the pipeline only logs a warning for None: the outcome is written to
        the delivery-status file (checked by the workflow's "Verify email
        delivery" step, which fails the job and opens an issue) and, on
        GitHub Actions, raised as an ::error:: annotation.
        """
        if not self.enabled:
            self._record_delivery("disabled")
            return None
        try:
            url = self.send_email(
                subject=self._build_subject(newsletter),
                html_content=html_content,
                excluded_tags=[Config.BUTTONDOWN_WEEKLY_TAG],
            )
        except Exception as exc:  # never let an unexpected error pass silently
            self.last_error = f"unexpected error: {exc}"
            url = None
        if url:
            self._record_delivery("sent", url=url, newsletter=newsletter)
        else:
            error = self.last_error or "Buttondown send failed (no details)"
            logger.error(f"EMAIL NOT SENT to subscribers: {error}")
            if os.getenv("GITHUB_ACTIONS") == "true":
                # Workflow-command annotation: shows on the run summary page.
                clean = error.replace("\r", " ").replace("\n", " ").replace("%", "%25")
                print(f"::error title=Buttondown email not sent::{clean[:900]}", flush=True)
            self._record_delivery("failed", error=error, newsletter=newsletter)
        return url

    @staticmethod
    def delivery_status_path() -> Path:
        return Path(os.getenv("EMAIL_DELIVERY_STATUS_FILE", DEFAULT_DELIVERY_STATUS_FILE))

    def _record_delivery(self, status: str, url: Optional[str] = None,
                         error: Optional[str] = None, newsletter: Optional[Newsletter] = None) -> None:
        record = {
            "status": status,                       # sent | failed | disabled
            "url": url,
            "error": error,
            "issue_date": (newsletter.date.strftime("%Y-%m-%d")
                           if newsletter is not None and getattr(newsletter, "date", None) else None),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            path = self.delivery_status_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.error(f"Could not write email delivery status: {exc}")

    def send_email(self, subject: str, html_content: str,
                   included_tags: Optional[list] = None,
                   excluded_tags: Optional[list] = None) -> Optional[str]:
        """Create and send one Buttondown email, optionally targeted by tags.

        Failure semantics of tag targeting differ by direction:
        - excluded_tags (daily send): if the filter is rejected, retry
          untargeted — a weekly subscriber getting one extra daily beats
          nobody getting anything.
        - included_tags (weekly digest): if the filter is rejected, ABORT —
          never widen a targeted send to the whole list.
        """
        if not self.enabled:
            return None
        self.last_error = None

        body = self._prepare_body(html_content)
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Buttondown-Version": "2026-04-01",
        }

        filters, unresolved = self._tag_filters(included_tags, excluded_tags, headers)
        if unresolved:
            self.last_error = (f"could not resolve tag ids for {unresolved} — aborted targeted "
                               "send rather than emailing the whole list")
            logger.error(self.last_error)
            return None

        neutralized: List[str] = []

        # Step 1: create draft
        email_id = None
        for _ in range(MAX_KEYWORD_RETRIES + 1):
            email_id = self._create_draft(subject, body, headers, filters=filters)
            if not email_id and excluded_tags and not included_tags and filters \
                    and not self._failure_keywords():
                logger.warning("Buttondown rejected the tag filter — retrying daily send untargeted")
                filters = None
                email_id = self._create_draft(subject, body, headers)
            if email_id:
                break
            new_keywords = self._new_keywords(neutralized)
            if not new_keywords:
                break
            subject, body = self._neutralize(subject, body, new_keywords, neutralized)
        if not email_id:
            if included_tags:
                logger.error("Buttondown draft with included-tag filter failed — "
                             "aborting rather than sending to the whole list")
            self.last_error = self._failure_summary("create")
            return None

        # Step 2: send draft to the targeted subscribers. The content filter
        # runs at send time too (that is where 2026-09-18 was rejected).
        for _ in range(MAX_KEYWORD_RETRIES + 1):
            url = self._send_draft(email_id, headers)
            if url:
                if neutralized:
                    logger.warning(f"Buttondown email sent after neutralizing prohibited "
                                   f"keyword(s) {neutralized} with invisible joiners")
                return url
            new_keywords = self._new_keywords(neutralized)
            if not new_keywords:
                break
            subject, body = self._neutralize(subject, body, new_keywords, neutralized)
            if not self._update_draft(email_id, subject, body, headers):
                break
        self.last_error = self._failure_summary("send")
        return None

    # ------------------------------------------------------------------
    # Prohibited-keyword handling
    # ------------------------------------------------------------------

    def _failure_keywords(self) -> List[str]:
        if not self._last_failure:
            return []
        status, text = self._last_failure
        return extract_prohibited_keywords(text) if status == 400 else []

    def _new_keywords(self, already: List[str]) -> List[str]:
        seen = {k.lower() for k in already}
        return [k for k in self._failure_keywords() if k.lower() not in seen]

    @staticmethod
    def _neutralize(subject: str, body: str, keywords: List[str],
                    neutralized: List[str]) -> Tuple[str, str]:
        logger.warning(f"Buttondown flagged prohibited keyword(s) {keywords} — "
                       "neutralizing them in the email copy and retrying")
        neutralized.extend(keywords)
        return (neutralize_keywords_text(subject, keywords),
                neutralize_keywords_html(body, keywords))

    def _failure_summary(self, stage: str) -> str:
        if not self._last_failure:
            return f"Buttondown {stage} failed"
        status, text = self._last_failure
        return f"Buttondown {stage} failed (HTTP {status}): {text[:300]}"

    def _update_draft(self, email_id: str, subject: str, body: str, headers: dict) -> bool:
        try:
            resp = requests.patch(
                f"{BUTTONDOWN_API_BASE}/emails/{email_id}",
                json={"subject": subject, "body": body},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Buttondown draft {email_id} updated with neutralized copy")
            return True
        except requests.HTTPError as exc:
            self._last_failure = (exc.response.status_code, exc.response.text or "")
            logger.error(f"Buttondown draft update failed (HTTP {exc.response.status_code}): "
                         f"{exc.response.text[:500]}")
        except Exception as exc:
            self._last_failure = (0, str(exc))
            logger.error(f"Buttondown draft update failed: {exc}")
        return False

    def _resolve_tag_id(self, name: str, headers: dict) -> Optional[str]:
        """Tag id for a tag name, or None when it doesn't exist or can't be read.

        Filter values must be tag IDENTIFIERS, not names (the production 422:
        "Tag filters must be valid tag identifiers"). Tags are never created
        here: excluding a nonexistent tag is a no-op anyway, and including one
        would target zero subscribers — the tag comes into existence when the
        first subscriber picks "weekly" on the signup form. Note the tags API
        itself needs Buttondown's Basic plan or higher; on the free plan it
        answers 422 and every send stays untargeted.
        """
        cache = getattr(self, "_tag_id_cache", None)
        if cache is None:
            cache = self._tag_id_cache = {}
        if name in cache:
            return cache[name]
        try:
            resp = requests.get(f"{BUTTONDOWN_API_BASE}/tags", headers=headers, timeout=15)
            resp.raise_for_status()
            for tag in resp.json().get("results", []):
                if (tag.get("name") or "").lower() == name.lower():
                    cache[name] = tag.get("id")
                    return cache[name]
            logger.info(f"Buttondown tag '{name}' doesn't exist yet (no subscriber has it)")
            return None
        except Exception as e:
            detail = ""
            body = getattr(getattr(e, "response", None), "text", "")
            if body:
                detail = f" — {body[:200]}"
            logger.warning(f"Could not resolve Buttondown tag '{name}': {e}{detail}"
                           " (tags need Buttondown's Basic plan or higher)")
            return None

    def has_tag(self, name: str) -> bool:
        """True when the tag exists and is addressable — gate for targeted sends."""
        if not self.enabled:
            return False
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json",
            "Buttondown-Version": "2026-04-01",
        }
        return self._resolve_tag_id(name, headers) is not None

    def _tag_filters(self, included_tags: Optional[list], excluded_tags: Optional[list],
                     headers: dict) -> tuple:
        """(filters object or None, list of INCLUDED tag names that failed to resolve).

        API versions after 2024-08-15 replaced flat included_tags/excluded_tags
        with this filter structure, keyed by tag id. An exclusion that fails to
        resolve is dropped silently — while the tag has no subscribers, sending
        untargeted is equivalent. A failed inclusion is reported so the caller
        aborts instead of widening the audience."""
        filters = []
        unresolved = []
        for tag in included_tags or []:
            tag_id = self._resolve_tag_id(tag, headers)
            if tag_id:
                filters.append({"field": "subscriber.tags", "operator": "contains", "value": tag_id})
            else:
                unresolved.append(tag)
        for tag in excluded_tags or []:
            tag_id = self._resolve_tag_id(tag, headers)
            if tag_id:
                filters.append({"field": "subscriber.tags", "operator": "not_contains", "value": tag_id})
            else:
                logger.info(f"Exclusion tag '{tag}' unresolved — sending untargeted "
                            "(equivalent while nobody carries the tag)")
        if not filters:
            return None, unresolved
        return {"filters": filters, "groups": [], "predicate": "and"}, unresolved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_draft(self, subject: str, body: str, headers: dict,
                      filters: Optional[dict] = None) -> Optional[str]:
        payload = {"subject": subject, "body": body, "status": "draft"}
        if filters:
            payload["filters"] = filters
        try:
            resp = requests.post(
                f"{BUTTONDOWN_API_BASE}/emails",
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            email_id = resp.json().get("id", "")
            logger.info(f"Buttondown draft created: id={email_id}")
            self._last_failure = None
            return email_id
        except requests.HTTPError as exc:
            self._last_failure = (exc.response.status_code, exc.response.text or "")
            logger.error(
                f"Buttondown create failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text[:500]}"
            )
        except Exception as exc:
            self._last_failure = (0, str(exc))
            logger.error(f"Buttondown create failed: {exc}")
        return None

    def _send_draft(self, email_id: str, headers: dict) -> Optional[str]:
        # v2026-04-01: use PATCH to set status=about_to_send with the live-dangerously header
        send_headers = {**headers, "X-Buttondown-Live-Dangerously": "true"}
        try:
            resp = requests.patch(
                f"{BUTTONDOWN_API_BASE}/emails/{email_id}",
                json={"status": "about_to_send"},
                headers=send_headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            url = (
                data.get("absolute_url")
                or (
                    f"https://buttondown.com/{self.username}/archive"
                    if self.username
                    else ""
                )
            )
            logger.info(f"Buttondown email queued for send: id={email_id} url={url}")
            self._last_failure = None
            return url or email_id
        except requests.HTTPError as exc:
            self._last_failure = (exc.response.status_code, exc.response.text or "")
            logger.error(
                f"Buttondown send failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text[:500]}"
            )
        except Exception as exc:
            self._last_failure = (0, str(exc))
            logger.error(f"Buttondown send failed: {exc}")
        return None

    @staticmethod
    def _truncate_at_word(text: str, limit: int) -> str:
        """Cut at a word boundary; ellipsis only when something was cut."""
        text = text.strip()
        if len(text) <= limit:
            return text
        cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:—- ")
        return cut + "…"

    def _build_subject(self, newsletter: Newsletter) -> str:
        """Inbox subject: the dedicated AI-written subject with the newsletter
        name appended, never the full headline and never a date suffix.

        Subject, headline and preheader are three different jobs: the client
        already shows the date, the headline lives inside the email, and a
        title + " — Aug 25" combo just truncates mid-word in every inbox.
        The brand goes LAST so the hook owns the first ~40 chars mobile
        clients show — on desktop it adds recognition, on mobile it simply
        truncates away.
        """
        title = Config.NEWSLETTER_TITLE
        subject = (getattr(newsletter, 'email_subject', "") or "").strip()
        if not subject and newsletter.stories:
            subject = self._truncate_at_word(newsletter.stories[0].story_title, 56)
        if not subject:
            return f"{title} — {newsletter.date.strftime('%B %-d, %Y')}"
        subject = self._truncate_at_word(subject, 60)
        if title.lower() not in subject.lower():
            subject = f"{subject} — {title}"
        # No emoji: the analyzer is told "no emoji" for a reason — and a
        # leading 🌍 turned every Buttondown archive slug into "u1f30d-…".
        return subject

    def _prepare_body(self, html: str) -> str:
        """Extract body content, strip JS handlers, and force Buttondown HTML mode.

        The editor-mode comment disables Buttondown's Markdown processing so
        indented HTML is rendered as-is rather than turned into code blocks.
        """
        inner = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
        body = inner.group(1).strip() if inner else html
        body = re.sub(r'\s+on\w+="[^"]*"', "", body, flags=re.IGNORECASE)
        body = re.sub(r"\s+on\w+='[^']*'", "", body, flags=re.IGNORECASE)
        return "<!-- buttondown-editor-mode: fancy -->\n" + body
