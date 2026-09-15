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
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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
                 provider: Optional[str], model: Optional[str]):
        self.content = [_TextBlock(text)] if text else []
        self.usage = usage
        self.stop_reason = stop_reason
        self.provider = provider              # ktery hostitel odpoved obslouzil
        self.model = model


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

    def __init__(self, api_key: str, timeout: int = 900, max_retries: int = 3,
                 referer: str = "https://github.com/eLh0m3r0/geodaily",
                 title: str = "geodaily"):
        if not api_key:
            raise ValueError("OpenRouter API key is missing")
        self._headers = {
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": referer,
            "X-Title": title,
        }
        self._timeout = timeout
        self._max_retries = max_retries
        self.messages = _Messages(self)

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
        for attempt in range(1, self._max_retries + 1):
            try:
                r = requests.post(OPENROUTER_URL, headers=self._headers,
                                  json=body, timeout=self._timeout)
            except requests.exceptions.RequestException as e:
                last_err = "%s: %s" % (type(e).__name__, str(e)[:200])
                time.sleep(min(60, 4 * attempt ** 2))
                continue

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

            if not text.strip() and attempt < self._max_retries:
                # Uspesna HTTP odpoved bez obsahu neni uspech. Dalsi pokus
                # posleme jinam - chyba byva na strane konkretniho hostitele.
                last_err = ("prazdna odpoved (provider=%s, finish=%s, reasoning=%s tokenu)"
                            % (provider, choice.get("finish_reason"),
                               (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")))
                logger.warning("OpenRouter %s - zkousim jineho hostitele", last_err)
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
                stop_reason=choice.get("finish_reason") or choice.get("native_finish_reason"),
                provider=provider,
                model=data.get("model") or model,
            )

        raise RuntimeError("OpenRouter selhal po %d pokusech: %s" % (self._max_retries, last_err))


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
            timeout=int(os.getenv("AI_REQUEST_TIMEOUT_S", "900")),
            max_retries=int(os.getenv("AI_MAX_RETRIES", "3")),
        )
    from anthropic import Anthropic
    return Anthropic(api_key=Config.ANTHROPIC_API_KEY)


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
