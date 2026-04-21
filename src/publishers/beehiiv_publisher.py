"""
Beehiiv publisher for the Geopolitical Daily newsletter.

Publishes each newsletter edition as a Beehiiv post via the v2 API.
Runs alongside GitHub Pages — both targets stay live.

Required env vars:
    BEEHIIV_API_KEY         - API key from Beehiiv → Settings → API
    BEEHIIV_PUBLICATION_ID  - Publication ID from Beehiiv → Settings → Publication
    BEEHIIV_STATUS          - "draft" (default) or "active" (publish immediately)
"""

import re
from datetime import datetime
from typing import List, Optional

import requests

from ..models import Newsletter, AIAnalysis
from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

BEEHIIV_API_BASE = "https://api.beehiiv.com/v2"


class BeehiivPublisher:
    """Publishes newsletter editions to Beehiiv via the v2 REST API."""

    def __init__(self) -> None:
        self.api_key = Config.BEEHIIV_API_KEY
        self.publication_id = Config.BEEHIIV_PUBLICATION_ID
        self.status = Config.BEEHIIV_STATUS
        self.enabled = bool(self.api_key and self.publication_id)
        if not self.enabled:
            logger.info("Beehiiv publisher disabled (BEEHIIV_API_KEY / BEEHIIV_PUBLICATION_ID not set)")

    def publish(self, newsletter: Newsletter, html_content: str) -> Optional[str]:
        """
        Create a post on Beehiiv for the given newsletter edition.

        Args:
            newsletter:   Newsletter dataclass (date, title, stories, intro_text)
            html_content: Full HTML string already rendered by NewsletterGenerator

        Returns:
            Beehiiv post URL on success, None if disabled or on error.
        """
        if not self.enabled:
            return None

        subject = self._build_subject(newsletter)
        preview = self._build_preview(newsletter)
        # Beehiiv expects a complete HTML document for the web view; the same
        # HTML is also used for the email content_free tier.
        body = self._prepare_html(html_content)

        payload = {
            "title": subject,
            "preview_text": preview,
            "body_content": body,
            "status": self.status,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        url = f"{BEEHIIV_API_BASE}/publications/{self.publication_id}/posts"
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            post_id = data.get("id", "")
            web_url = data.get("web_url") or data.get("url") or ""
            logger.info(
                f"Beehiiv post created: id={post_id} status={self.status} url={web_url}"
            )
            return web_url or post_id
        except requests.HTTPError as exc:
            logger.error(
                f"Beehiiv publish failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text[:500]}"
            )
        except Exception as exc:
            logger.error(f"Beehiiv publish failed: {exc}")
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_subject(self, newsletter: Newsletter) -> str:
        date_str = newsletter.date.strftime("%B %-d, %Y")
        return f"Geopolitical Daily — {date_str}"

    def _build_preview(self, newsletter: Newsletter) -> str:
        """First 140 characters of the intro text, or a fallback."""
        text = getattr(newsletter, "intro_text", "") or ""
        # Strip any HTML tags that might be in the intro
        text = re.sub(r"<[^>]+>", "", text).strip()
        if not text:
            count = len(newsletter.stories)
            text = f"Today's {count} key geopolitical developments — curated intelligence briefing."
        return text[:140]

    def _prepare_html(self, html: str) -> str:
        """Light cleanup so the HTML renders cleanly inside Beehiiv's email wrapper."""
        # Beehiiv injects its own <html>/<body> wrapper, so strip the outer shell
        # but keep everything else (styles, content) intact.
        inner = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
        if inner:
            return inner.group(1).strip()
        return html
