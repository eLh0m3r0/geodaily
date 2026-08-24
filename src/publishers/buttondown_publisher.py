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
        if unresolved and included_tags:
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
        """Tag id for a tag name; creates the tag when it doesn't exist yet.

        Filter values must be tag IDENTIFIERS, not names (the production 422:
        "Tag filters must be valid tag identifiers"). The weekly tag may not
        exist before the first subscriber picks it, so create-on-miss keeps
        the daily exclusion working from day one.
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
            created = requests.post(f"{BUTTONDOWN_API_BASE}/tags",
                                    json={"name": name}, headers=headers, timeout=15)
            created.raise_for_status()
            cache[name] = created.json().get("id")
            logger.info(f"Created Buttondown tag '{name}' (id={cache[name]})")
            return cache[name]
        except Exception as e:
            logger.warning(f"Could not resolve Buttondown tag '{name}': {e}")
            return None

    def _tag_filters(self, included_tags: Optional[list], excluded_tags: Optional[list],
                     headers: dict) -> tuple:
        """(filters object or None, list of tag names that failed to resolve).

        API versions after 2024-08-15 replaced flat included_tags/excluded_tags
        with this filter structure, keyed by tag id."""
        filters = []
        unresolved = []
        for tag, operator in ([(t, "contains") for t in included_tags or []]
                              + [(t, "not_contains") for t in excluded_tags or []]):
            tag_id = self._resolve_tag_id(tag, headers)
            if tag_id:
                filters.append({"field": "subscriber.tags", "operator": operator, "value": tag_id})
            else:
                unresolved.append(tag)
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

    def _build_subject(self, newsletter: Newsletter) -> str:
        """Subject line led by the top story, not the date.

        "Geopolitical Daily — August 24" tells the reader nothing; the lead
        story's title is the reason to open. Date-only remains the fallback.
        """
        date_str = newsletter.date.strftime("%b %-d")
        if newsletter.stories:
            title = newsletter.stories[0].story_title.strip()
            if len(title) > 70:
                title = title[:67].rstrip() + "..."
            return f"🌍 {title} — {date_str}"
        return f"Geopolitical Daily — {newsletter.date.strftime('%B %-d, %Y')}"

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
