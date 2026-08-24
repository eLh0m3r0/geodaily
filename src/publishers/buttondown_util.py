"""
Buttondown helpers shared by page generation and publishing.

The subscribe form needs the newsletter's Buttondown username. It is not a
secret (it appears in the public form action URL), but historically it was
only available via the BUTTONDOWN_USERNAME env var — when that secret was
missing, published pages silently shipped with no email signup at all.
This helper resolves the username from the API (using the API key, which IS
configured whenever emails are being sent) so the form can never silently
disappear again.
"""

from functools import lru_cache

import requests

from ..config import Config
from ..logger import get_logger

logger = get_logger(__name__)

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"


@lru_cache(maxsize=1)
def resolve_buttondown_username() -> str:
    """Buttondown username for subscribe forms.

    Resolution order: BUTTONDOWN_USERNAME env var, then a lookup via the API
    key. Returns "" when neither is available (form is omitted, RSS CTA only).
    """
    if Config.BUTTONDOWN_USERNAME:
        return Config.BUTTONDOWN_USERNAME
    if not Config.BUTTONDOWN_API_KEY:
        return ""
    try:
        resp = requests.get(
            f"{BUTTONDOWN_API_BASE}/newsletters",
            headers={
                "Authorization": f"Token {Config.BUTTONDOWN_API_KEY}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            username = results[0].get("username", "") or ""
            if username:
                logger.info(f"Resolved Buttondown username via API: {username}")
            return username
    except Exception as e:
        logger.warning(f"Could not resolve Buttondown username from API: {e}")
    return ""


def build_subscribe_form_html(username: str, css_class: str = "subscribe-form",
                              with_frequency_choice: bool = True) -> str:
    """Shared Buttondown embed-subscribe form.

    The daily/weekly radio posts a `tag` field: subscribers who pick weekly
    are tagged (Config.BUTTONDOWN_WEEKLY_TAG) and the daily send excludes
    that tag once the Sunday digest is live. Frequency choice at signup is
    the single best-documented churn reducer for daily newsletters.
    """
    if not username:
        return ""
    weekly_tag = Config.BUTTONDOWN_WEEKLY_TAG
    frequency_html = ""
    if with_frequency_choice:
        # Checkbox, not radio: unchecked submits no tag field at all (daily
        # default), checked submits tag=<weekly> which Buttondown appends to
        # the subscriber. An empty-value radio would post tag="" instead.
        frequency_html = f"""
        <div class="subscribe-frequency">
            <label><input type="checkbox" name="tag" value="{weekly_tag}" /> Send me one Sunday digest instead of daily emails</label>
        </div>"""
    return f"""
        <form action="https://buttondown.com/api/emails/embed-subscribe/{username}"
              method="post"
              target="popupwindow"
              onsubmit="window.open('https://buttondown.com/{username}', 'popupwindow')"
              class="{css_class}">
            <input type="email" name="email" placeholder="your@email.com" required />{frequency_html}
            <input type="submit" value="Subscribe" class="subscribe-btn" />
        </form>"""
