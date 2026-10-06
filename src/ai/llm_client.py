"""
Jednotny klient pro LLM volani (src/ai/llm_client.py).

Proc adapter a ne prepsani volajicich mist: analyzatory pracuji s tvarem
odpovedi Anthropic Messages API (response.content[] bloky, response.usage
.input_tokens/.output_tokens) a api_utils.extract_response_text() i
response_tokens_and_cost() na tom stoji. Adapter tenhle tvar zachova, takze
na volajicich mistech se meni jen konstrukce klienta - jeden radek.

Prepnuti zpet na Anthropic je zmena jedne promenne prostredi (AI_PROVIDER),
zadny revert kodu.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Wall-clock limit for ONE request, in seconds (env AI_REQUEST_TIMEOUT_S).
# A plain requests timeout is per socket read, and OpenRouter keeps idle
# non-streaming requests alive with whitespace, so a stuck upstream hung
# silently for 6-13 minutes (2026-09-21 grid call 13.5 min, 09-23 main call
# 509 s). Legitimate DeepSeek calls that write ~15k output tokens DO take
# 360-510 s (09-20, 09-23 succeeded that way), so the limit sits above that
# and below the observed 13.5-minute hang.
DEFAULT_REQUEST_TIMEOUT_S = 600
# How many times a request that hit the wall-clock limit is re-sent
# (env AI_TIMEOUT_RETRIES).
DEFAULT_TIMEOUT_RETRIES = 1
# Ceiling for the automatic budget growth after a length-truncated empty reply
# (a 64000-token retry ran past the 600 s request limit on a slow host)
MAX_GROWN_TOKENS = int(os.getenv("AI_MAX_GROWN_TOKENS", "32000"))


class LLMTimeoutError(RuntimeError):
    """A request exceeded the wall-clock timeout on every allowed attempt."""


# --- objekty napodobujici tvar odpovedi Anthropic SDK -----------------------

class _TextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int,
                 cost_usd: Optional[float] = None, reasoning_tokens: int = 0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd              # skutecna cena od OpenRouteru
        self.reasoning_tokens = reasoning_tokens


class _Response:
    def __init__(self, text: str, usage: _Usage, stop_reason: Optional[str],
                 provider: Optional[str], model: Optional[str],
                 requested_model: Optional[str] = None,
                 latency_s: Optional[float] = None,
                 llm_provider: str = "openrouter"):
        self.content = [_TextBlock(text)] if text else []
        self.usage = usage
        self.stop_reason = stop_reason
        self.provider = provider              # ktery hostitel odpoved obslouzil
        # `model` stays the model that actually served the request (Anthropic
        # SDK semantics); served_model/requested_model make the distinction
        # explicit so callers can record silent reroutes.
        self.model = model
        self.served_model = model
        self.requested_model = requested_model
        self.latency_s = latency_s
        self.llm_provider = llm_provider


class _Messages:
    def __init__(self, client: "OpenRouterClient"):
        self._client = client

    def create(self, model: str, max_tokens: int, messages: List[Dict[str, Any]],
               **kwargs) -> _Response:
        return self._client._create(model, max_tokens, messages, **kwargs)


# --- vlastni klient ---------------------------------------------------------

class OpenRouterClient:
    """OpenRouter s rozhranim `client.messages.create(...)`.

    Retry pokryva tri veci, ktere se v provozu opravdu deji:
      1) 429 a 5xx           -> exponencialni backoff
      2) HTTP 200 s PRAZDNYM obsahem -> u nekterych hostitelu chyba uvnitr
         uspesne odpovedi, nebo model spotreboval cely rozpocet na reasoning;
         dalsi pokus jde zamerne na jineho hostitele
      3) sitove vypadky      -> backoff
    """

    def __init__(self, api_key: str, timeout: float = DEFAULT_REQUEST_TIMEOUT_S,
                 max_retries: int = 3,
                 referer: str = "https://github.com/eLh0m3r0/geodaily",
                 title: str = "geodaily",
                 timeout_retries: int = DEFAULT_TIMEOUT_RETRIES):
        if not api_key:
            raise ValueError("OpenRouter API key is missing")
        self._headers = {
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": referer,
            "X-Title": title,
        }
        self._timeout = float(timeout)
        self._max_retries = max_retries
        self._timeout_retries = max(0, int(timeout_retries))
        self.messages = _Messages(self)

    def _post(self, body: Dict[str, Any]) -> requests.Response:
        """POST with a hard wall-clock limit of self._timeout seconds.

        requests' own timeout only bounds each socket read; keep-alive bytes
        reset it indefinitely. The request therefore runs in a daemon thread
        and we stop waiting at the deadline (a daemon thread never blocks
        interpreter exit; its socket read timeout eventually reaps it).
        Raises requests.exceptions.Timeout when the deadline passes."""
        outcome: Dict[str, Any] = {}

        def _worker():
            try:
                outcome["response"] = requests.post(
                    OPENROUTER_URL, headers=self._headers, json=body,
                    timeout=(min(30.0, self._timeout), self._timeout))
            except BaseException as e:  # re-raised in the caller's thread
                outcome["error"] = e

        worker = threading.Thread(target=_worker, name="openrouter-request", daemon=True)
        worker.start()
        worker.join(self._timeout)
        if worker.is_alive():
            raise requests.exceptions.Timeout(
                "no complete response within %.0f s (wall clock)" % self._timeout)
        if "error" in outcome:
            raise outcome["error"]
        return outcome["response"]

    def _create(self, model: str, max_tokens: int, messages: List[Dict[str, Any]],
                **kwargs) -> _Response:
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "usage": {"include": True},       # OpenRouter vrati skutecnou cenu
        }
        # Volitelne per-model nastaveni (napr. {"reasoning": {"effort": "low"}}).
        # Pro DeepSeek V4.1 Flash se NIC nepridava - testy ukazaly, ze omezeni
        # reasoningu mu kvalitu zhorsuje.
        extra = kwargs.get("extra_body")
        if extra:
            body.update(extra)

        last_err = None
        timeouts = 0
        attempt = 0
        while attempt < self._max_retries:
            attempt += 1
            started = time.monotonic()
            try:
                r = self._post(body)
            except requests.exceptions.Timeout as e:
                timeouts += 1
                last_err = "timeout after %.0f s: %s" % (time.monotonic() - started, str(e)[:200])
                if timeouts > self._timeout_retries:
                    logger.error("OpenRouter %s (model=%s) - giving up after %d timeout(s)",
                                 last_err, model, timeouts)
                    raise LLMTimeoutError("OpenRouter request timed out %d time(s) "
                                          "(limit %.0f s each, model=%s)"
                                          % (timeouts, self._timeout, model)) from e
                logger.warning("OpenRouter %s (model=%s) - retrying once", last_err, model)
                # A timeout is not a failure of the retry budget for other
                # errors: give the retry its own attempt.
                attempt -= 1
                continue
            except requests.exceptions.RequestException as e:
                last_err = "%s: %s" % (type(e).__name__, str(e)[:200])
                logger.warning("OpenRouter %s, pokus %d/%d", last_err, attempt, self._max_retries)
                time.sleep(min(60, 4 * attempt ** 2))
                continue
            latency = time.monotonic() - started

            if r.status_code in (429, 500, 502, 503, 520, 524):
                last_err = "HTTP %d: %s" % (r.status_code, r.text[:200])
                logger.warning("OpenRouter %s, pokus %d/%d", last_err, attempt, self._max_retries)
                time.sleep(min(60, 4 * attempt ** 2))
                continue
            if r.status_code != 200:
                raise RuntimeError("OpenRouter HTTP %d: %s" % (r.status_code, r.text[:500]))

            data = r.json()
            if "error" in data and not data.get("choices"):
                raise RuntimeError("OpenRouter error: %s" % json.dumps(data["error"])[:300])

            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            text = msg.get("content") or ""
            usage = data.get("usage") or {}
            provider = data.get("provider")
            served_model = data.get("model") or model
            stop_reason = choice.get("finish_reason") or choice.get("native_finish_reason")

            logger.info("LLM call: provider=openrouter upstream=%s requested_model=%s "
                        "served_model=%s latency=%.1fs tokens_in=%s tokens_out=%s "
                        "stop=%s attempt=%d",
                        provider, model, served_model, latency,
                        usage.get("prompt_tokens"), usage.get("completion_tokens"),
                        stop_reason, attempt)
            if served_model and model and served_model.split(":")[0] != model.split(":")[0]:
                logger.warning("OpenRouter served %s although %s was requested",
                               served_model, model)

            if not text.strip() and attempt < self._max_retries:
                # Uspesna HTTP odpoved bez obsahu neni uspech. Dalsi pokus
                # posleme jinam - chyba byva na strane konkretniho hostitele.
                last_err = ("prazdna odpoved (provider=%s, finish=%s, reasoning=%s tokenu)"
                            % (provider, choice.get("finish_reason"),
                               (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")))
                logger.warning("OpenRouter %s - zkousim jineho hostitele", last_err)
                # Reasoning that ate the whole budget (finish=length, no text)
                # is not a host fault: the same budget fails again on every
                # host (2026-10-06 shadow run: 4 x 16000 reasoning tokens, no
                # issue). Double the budget instead — never cap the reasoning
                # itself (it measurably lowered quality).
                if (choice.get("finish_reason") or choice.get("native_finish_reason")) == "length":
                    grown = min(MAX_GROWN_TOKENS, int(body.get("max_tokens") or max_tokens) * 2)
                    if grown > int(body.get("max_tokens") or 0):
                        logger.warning("OpenRouter: reasoning used the whole budget - retrying with "
                                       "max_tokens=%d", grown)
                        body["max_tokens"] = grown
                if provider:
                    ignore = body.setdefault("provider", {}).setdefault("ignore", [])
                    if provider not in ignore:
                        ignore.append(provider)
                time.sleep(2)
                continue

            return _Response(
                text=text,
                usage=_Usage(
                    input_tokens=int(usage.get("prompt_tokens") or 0),
                    output_tokens=int(usage.get("completion_tokens") or 0),
                    cost_usd=usage.get("cost"),
                    reasoning_tokens=int((usage.get("completion_tokens_details") or {})
                                         .get("reasoning_tokens") or 0),
                ),
                stop_reason=stop_reason,
                provider=provider,
                model=served_model,
                requested_model=model,
                latency_s=round(latency, 2),
            )

        raise RuntimeError("OpenRouter selhal po %d pokusech: %s" % (self._max_retries, last_err))


class _LoggedAnthropicMessages:
    """Wraps anthropic's `messages` so every call gets the same INFO line as
    OpenRouter calls (latency, requested vs served model). The SDK response
    object is returned unchanged; its `.model` already is the served model."""

    def __init__(self, messages):
        self._messages = messages

    def create(self, **kwargs):
        requested = kwargs.get("model")
        started = time.monotonic()
        response = self._messages.create(**kwargs)
        latency = time.monotonic() - started
        usage = getattr(response, "usage", None)
        logger.info("LLM call: provider=anthropic requested_model=%s served_model=%s "
                    "latency=%.1fs tokens_in=%s tokens_out=%s stop=%s",
                    requested, getattr(response, "model", None), latency,
                    getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None),
                    getattr(response, "stop_reason", None))
        return response

    def __getattr__(self, name):
        return getattr(self._messages, name)


class LoggedAnthropicClient:
    """Anthropic client with per-call logging; everything else is delegated."""

    def __init__(self, client):
        self._client = client
        self.messages = _LoggedAnthropicMessages(client.messages)

    def __getattr__(self, name):
        return getattr(self._client, name)


def request_timeout_s() -> float:
    """Wall-clock limit per LLM request (env AI_REQUEST_TIMEOUT_S, default 600)."""
    try:
        value = float(os.getenv("AI_REQUEST_TIMEOUT_S", str(DEFAULT_REQUEST_TIMEOUT_S)))
        return value if value > 0 else float(DEFAULT_REQUEST_TIMEOUT_S)
    except ValueError:
        return float(DEFAULT_REQUEST_TIMEOUT_S)


# --- tovarna ----------------------------------------------------------------

def build_llm_client(provider: Optional[str] = None):
    """Vrati klienta podle Config.AI_PROVIDER (nebo podle explicitniho override).

    Volajici mista uz nic neresi - dostanou objekt s `messages.create(...)`
    bez ohledu na to, ktery poskytovatel je za nim."""
    from ..config import Config

    provider = (provider or Config.AI_PROVIDER or "anthropic").lower()
    if provider == "openrouter":
        return OpenRouterClient(
            api_key=Config.OPENROUTER_API_KEY,
            timeout=request_timeout_s(),
            max_retries=int(os.getenv("AI_MAX_RETRIES", "3")),
            timeout_retries=int(os.getenv("AI_TIMEOUT_RETRIES", str(DEFAULT_TIMEOUT_RETRIES))),
        )
    from anthropic import Anthropic
    # Explicit per-request timeout instead of the SDK's 10-minute default.
    # The SDK keeps its own retry policy (2 retries on timeouts, 429, 5xx/529):
    # lowering it would cost resilience against Anthropic overload errors.
    return LoggedAnthropicClient(Anthropic(
        api_key=Config.ANTHROPIC_API_KEY,
        timeout=request_timeout_s(),
    ))


def ai_credentials_present(provider: Optional[str] = None) -> bool:
    """Ma pipeline cim volat?

    Nahrazuje primou kontrolu ANTHROPIC_API_KEY v analyzatorech - ta by po
    prepnuti na OpenRouter poslala celou analyzu do mock rezimu a vydani by
    vyslo s vymyslenym obsahem."""
    from ..config import Config
    provider = (provider or Config.AI_PROVIDER or "anthropic").lower()
    if provider == "openrouter":
        return bool(Config.OPENROUTER_API_KEY)
    return bool(Config.ANTHROPIC_API_KEY)
