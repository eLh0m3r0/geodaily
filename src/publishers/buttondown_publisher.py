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
        Create and send a Buttondown email for the given newsletter edition.

        Returns the archive URL on success, None if disabled or on error.
        """
        if not self.enabled:
            return None

        subject = self._build_subject(newsletter)
        body = self._prepare_body(html_content)
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Buttondown-Version": "2026-04-01",
        }

        # Step 1: create draft
        email_id = self._create_draft(subject, body, headers)
        if not email_id:
            return None

        # Step 2: send draft to all subscribers
        return self._send_draft(email_id, headers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_draft(self, subject: str, body: str, headers: dict) -> Optional[str]:
        payload = {"subject": subject, "body": body, "status": "draft"}
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
        date_str = newsletter.date.strftime("%B %-d, %Y")
        return f"Geopolitical Daily — {date_str}"

    def _prepare_body(self, html: str) -> str:
        """Extract body content and strip JS event handlers (Buttondown rejects them).

        The email HTML is generated with inline styles, so extracting the body
        preserves all visual formatting regardless of email client head-stripping.
        """
        inner = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
        body = inner.group(1).strip() if inner else html
        body = re.sub(r'\s+on\w+="[^"]*"', "", body, flags=re.IGNORECASE)
        body = re.sub(r"\s+on\w+='[^']*'", "", body, flags=re.IGNORECASE)
        return body
