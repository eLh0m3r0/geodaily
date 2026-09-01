"""
Buttondown publisher for the Geopolitical Daily newsletter.

Publishes each newsletter edition as a Buttondown email via the v1 API.
Runs alongside GitHub Pages — both targets stay live.

Required env vars:
    BUTTONDOWN_API_KEY  - API key from Buttondown → Settings → API Key
"""

import re
from typing import Optional

import requests

from ..models import Newsletter
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"


class ButtondownPublisher:
    """Publishes newsletter editions to Buttondown subscribers via the v1 REST API."""

    def __init__(self) -> None:
        self.api_key = Config.BUTTONDOWN_API_KEY
        self.username = Config.BUTTONDOWN_USERNAME
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.info("Buttondown publisher disabled (BUTTONDOWN_API_KEY not set)")

    def publish(self, newsletter: Newsletter, html_content: str) -> Optional[str]:
        """
        Create and send the daily Buttondown email for a newsletter edition.
        Weekly-digest subscribers (tagged) are excluded — they get the
        Sunday digest instead.

        Returns the archive URL on success, None if disabled or on error.
        """
        return self.send_email(
            subject=self._build_subject(newsletter),
            html_content=html_content,
            excluded_tags=[Config.BUTTONDOWN_WEEKLY_TAG],
        )

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

        body = self._prepare_body(html_content)
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Buttondown-Version": "2026-04-01",
        }

        filters, unresolved = self._tag_filters(included_tags, excluded_tags, headers)
        if unresolved:
            logger.error(f"Could not resolve tag ids for {unresolved} — "
                         "aborting targeted send rather than emailing the whole list")
            return None

        # Step 1: create draft
        email_id = self._create_draft(subject, body, headers, filters=filters)
        if not email_id and excluded_tags and not included_tags and filters:
            logger.warning("Buttondown rejected the tag filter — retrying daily send untargeted")
            email_id = self._create_draft(subject, body, headers)
        if not email_id:
            if included_tags:
                logger.error("Buttondown draft with included-tag filter failed — "
                             "aborting rather than sending to the whole list")
            return None

        # Step 2: send draft to the targeted subscribers
        return self._send_draft(email_id, headers)

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
            return email_id
        except requests.HTTPError as exc:
            logger.error(
                f"Buttondown create failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text[:500]}"
            )
        except Exception as exc:
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
            return url or email_id
        except requests.HTTPError as exc:
            logger.error(
                f"Buttondown send failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text[:500]}"
            )
        except Exception as exc:
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
        return f"🌍 {subject}"

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
