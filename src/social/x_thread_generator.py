#!/usr/bin/env python3
"""
X.com (Twitter) thread generator for GeoPolitical Daily.
Generates Czech threads from AI analyses with minimal API calls.
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from ..config import Config
from ..models import AIAnalysis
from ..ai.api_utils import extract_response_text, response_tokens_and_cost

logger = logging.getLogger(__name__)

# Output budget for one thread call. Adaptive-thinking models (Sonnet 5) spend
# thinking tokens from max_tokens: the old 4000 cap left the JSON truncated on
# most days (2026-09-12..29: 17 of 49 threads survived; "Could not parse" =
# no JSON text at all, "Expecting ',' delimiter" = JSON cut off after the last
# complete tweet object). 16000 matches the other calls and stays under the
# SDK's non-streaming limit.
DEFAULT_THREAD_MAX_TOKENS = 16000
MIN_THREAD_TWEETS = 3

# Fallback per-MTok rates for the thread model when the provider does not
# report the billed amount (Anthropic doesn't; OpenRouter does). The global
# AI_*_COST_PER_MTOK rates describe the MAIN model, which is a different one.
_KNOWN_MODEL_RATES = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-5-5": (2.0, 10.0),
}

# Unified prompt that handles everything in one Claude call
UNIFIED_THREAD_PROMPT = """
Jsi expert na geopolitiku a sociální média. Z této anglické analýzy vytvoř české vlákno pro X.com (Twitter).

PŮVODNÍ ANALÝZA:
Titul: {title}
Shrnutí: {summary}
Proč je to důležité: {why_it_matters}
Co ostatní přehlížejí: {what_others_miss}
Co sledovat: {what_to_watch}
Impact skóre: {impact_score}/10
Naléhavost: {urgency}/10
Typ obsahu: {content_type}

ÚKOL - vytvoř české vlákno:
1. 5-8 tweetů (každý MUSÍ mít max 280 znaků včetně mezer)
2. První tweet: Silný hook co zaujme české čtenáře (max 260 znaků pro prostor na engagement)
3. Prostřední tweety: Klíčové informace, kontext pro ČR/střední Evropu  
4. Poslední tweet: Závěr + výzva k akci
5. Použij 1-2 relevantní emoji na tweet (🔍📊🌍⚡💡🎯🚨📈)
6. Přidej 2-3 české hashtagy na konec posledního tweetu

FORMÁT ODPOVĚDI - vrať POUZE tento JSON objekt, bez markdownu a bez textu okolo:
{{
  "thread_title": "Krátký český název tématu (max 50 znaků)",
  "tweets": [
    {{
      "number": 1,
      "content": "Text tweetu včetně emoji"
    }}
  ],
  "hashtags": ["#geopolitika", "#bezpečnost", "#analýza"],
  "estimated_engagement": 8.5,
  "main_topic": "one_word_topic_identifier"
}}

DŮLEŽITÉ:
- Piš PŘÍMO v češtině, profesionálně ale srozumitelně
- Každý tweet musí fungovat samostatně i jako část vlákna
- Použij čísla a fakta kde to dává smysl
- Zdůrazni dopady na ČR/EU když jsou relevantní
- Tweets čísluj ve formátu "1/7" na začátku
- Uvnitř textů tweetů NEPOUŽÍVEJ rovné uvozovky ("), jen české „takto“ - rovné uvozovky rozbíjejí JSON
"""

JSON_RETRY_SUFFIX = """

OPRAVA: Tvoje předchozí odpověď nebyla platný kompletní JSON. Odpověz znovu a vrať
VÝHRADNĚ jeden platný JSON objekt podle formátu výše - žádný markdown, žádný text
před ani za ním, uvnitř řetězců žádné rovné uvozovky ("), maximálně 8 tweetů.
"""


# --- tolerant JSON extraction ----------------------------------------------

_VALUE_START = tuple('"{[-0123456789')


def _next_significant(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def _starts_value(s: str, j: int) -> bool:
    return j < len(s) and (s[j] in _VALUE_START or s.startswith(("true", "false", "null"), j))


def _quote_closes_string(s: str, i: int) -> bool:
    """Is the '"' at s[i] (inside a string) the real closing quote?

    Yes when what follows is JSON structure: end of text, '}' or ']', a ','
    followed by the next key/value, or a ':' followed by a value. Otherwise
    it is an unescaped quote inside Czech prose (e.g. `řekl "ne", ale`)."""
    j = _next_significant(s, i + 1)
    if j >= len(s) or s[j] in "}]":
        return True
    if s[j] == ",":
        k = _next_significant(s, j + 1)
        return k >= len(s) or s[k] in "}]" or _starts_value(s, k)
    if s[j] == ":":
        return _starts_value(s, _next_significant(s, j + 1)) or _next_significant(s, j + 1) >= len(s)
    return False


def _repair_json_candidates(text: str) -> List[Tuple[str, bool]]:
    """Candidate repairs of model-written JSON, best first.

    One scan escapes stray quotes / raw control characters inside strings
    and drops trailing commas; it also records every point where a complete
    value ended, so a TRUNCATED response can be cut back to its last complete
    element and closed with the brackets still open at that point.
    Returns (candidate, was_truncated) pairs."""
    out: List[str] = []
    stack: List[str] = []
    cut_points: List[Tuple[int, str]] = []   # (len(out) after a complete value, closers)
    in_str = False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                out.append(text[i:i + 2])
                i += 2
                continue
            if c == '"':
                if _quote_closes_string(text, i):
                    in_str = False
                    out.append(c)
                    cut_points.append((len(out), "".join(reversed(stack))))
                else:
                    out.append('\\"')
            elif c == "\n":
                out.append("\\n")
            elif c == "\t":
                out.append("\\t")
            elif c == "\r":
                pass
            else:
                out.append(c)
        else:
            if c == '"':
                in_str = True
                out.append(c)
            elif c in "{[":
                stack.append("}" if c == "{" else "]")
                out.append(c)
            elif c in "}]":
                while out and out[-1] in (" ", "\n", "\t", "\r"):
                    out.pop()
                if out and out[-1] == ",":
                    out.pop()
                if stack:
                    stack.pop()
                out.append(c)
                cut_points.append((len(out), "".join(reversed(stack))))
            else:
                out.append(c)
                if c.isdigit() or c in "el":   # end of number / true / false / null
                    cut_points.append((len(out), "".join(reversed(stack))))
        i += 1

    candidates = [("".join(out), False)]
    if in_str or stack:
        # Truncated: close at the latest complete value that still parses.
        for pos, closers in reversed(cut_points[-400:]):
            prefix = "".join(out[:pos]).rstrip().rstrip(",")
            if closers.startswith("}"):
                # Inside an object a string right after `{` or `,` is a KEY
                # whose value never arrived - drop it.
                prefix = re.sub(r'([{,])\s*"[^"\\]*(?:\\.[^"\\]*)*"\s*$', r"\1", prefix).rstrip().rstrip(",")
            candidates.append((prefix + closers, True))
    return candidates


def parse_json_object_tolerant(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Extract one JSON object from an LLM response.

    Returns (object or None, status) with status "ok" (valid as sent),
    "repaired" (stray quotes / raw newlines / trailing commas fixed) or
    "truncated" (cut-off JSON closed after its last complete element, so the
    caller can decide whether a partial result is acceptable). Handles
    markdown fences and prose around the object."""
    if not text:
        return None, "none"
    cleaned = re.sub(r"```(?:json|JSON)?", "", text).strip()
    start = cleaned.find("{")
    if start < 0:
        return None, "none"
    cleaned = cleaned[start:]

    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned)
        if isinstance(obj, dict):
            return obj, "ok"
    except ValueError:
        pass

    # Drop trailing prose after the last closing brace before repairing.
    end = cleaned.rfind("}")
    candidates = []
    if end > 0:
        candidates.extend(_repair_json_candidates(cleaned[:end + 1]))
    candidates.extend(_repair_json_candidates(cleaned))
    for candidate, was_truncated in candidates:
        try:
            obj = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj, ("truncated" if was_truncated else "repaired")
    return None, "none"


def normalize_thread(data: Any) -> Optional[Dict[str, Any]]:
    """Validate/normalize a parsed thread; None when it is not a usable thread."""
    if not isinstance(data, dict):
        return None
    raw_tweets = data.get("tweets")
    if not isinstance(raw_tweets, list):
        return None
    tweets = []
    for item in raw_tweets:
        if isinstance(item, str):
            content = item
        elif isinstance(item, dict):
            content = item.get("content") or item.get("text") or ""
        else:
            continue
        content = str(content).strip()
        if content:
            tweets.append({"number": len(tweets) + 1, "content": content,
                           "char_count": len(content)})
    if len(tweets) < MIN_THREAD_TWEETS:
        return None
    data["tweets"] = tweets
    if not isinstance(data.get("hashtags"), list):
        data["hashtags"] = re.findall(r"#\w+", tweets[-1]["content"])
    if not str(data.get("thread_title") or "").strip():
        data["thread_title"] = tweets[0]["content"][:50]
    return data



def thread_max_tokens() -> int:
    try:
        return max(1024, int(os.getenv("X_THREADS_MAX_TOKENS", str(DEFAULT_THREAD_MAX_TOKENS))))
    except ValueError:
        return DEFAULT_THREAD_MAX_TOKENS


def thread_call_cost(response, model: str, prompt: str, text: str) -> Tuple[int, int, float]:
    """(input_tokens, output_tokens, cost_usd) for a thread call.

    Uses the provider-billed amount when present (OpenRouter); otherwise the
    thread model's own rates (X_THREADS_*_COST_PER_MTOK, else known list
    prices, else the global AI_*_COST_PER_MTOK)."""
    in_tok, out_tok, cost = response_tokens_and_cost(response, prompt, text)
    usage = getattr(response, 'usage', None)
    billed = getattr(usage, 'cost_usd', None) if usage else None
    if isinstance(billed, (int, float)) and billed > 0:
        return in_tok, out_tok, cost
    known_in, known_out = _KNOWN_MODEL_RATES.get(
        (model or "").lower(), (Config.AI_INPUT_COST_PER_MTOK, Config.AI_OUTPUT_COST_PER_MTOK))
    try:
        rate_in = float(os.getenv("X_THREADS_INPUT_COST_PER_MTOK", known_in))
        rate_out = float(os.getenv("X_THREADS_OUTPUT_COST_PER_MTOK", known_out))
    except ValueError:
        rate_in, rate_out = known_in, known_out
    return in_tok, out_tok, in_tok / 1_000_000 * rate_in + out_tok / 1_000_000 * rate_out


class XThreadGenerator:
    """Generates X.com threads from AI analyses with minimal API calls"""
    
    def __init__(self):
        """Initialize thread generator"""
        self.output_dir = Config.PROJECT_ROOT / "docs" / "threads"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_thread_from_analysis(self, analysis: AIAnalysis, api_client) -> Optional[Dict]:
        """
        Generate X.com thread from AI analysis using the configured LLM client.

        One API call normally; one retry (with an explicit valid-JSON
        instruction) when the answer is empty, truncated or unparseable.
        Every call is recorded in the AI cost controller.

        Returns:
            Thread data dict or None if generation fails
        """
        try:
            summary = f"{analysis.why_important[:100]}..." if len(analysis.why_important) > 100 else analysis.why_important

            prompt = UNIFIED_THREAD_PROMPT.format(
                title=analysis.story_title,
                summary=summary,
                why_it_matters=analysis.why_important,
                what_others_miss=analysis.what_overlooked,
                what_to_watch=analysis.prediction,
                impact_score=analysis.impact_dimension_score,
                urgency=analysis.urgency_score,
                content_type=analysis.content_type.value if hasattr(analysis.content_type, 'value') else str(analysis.content_type)
            )
        except Exception as e:
            logger.error(f"Failed to build thread prompt: {e}")
            return None

        logger.info(f"Generating X.com thread for: {analysis.story_title[:50]}...")

        fallback: Optional[Dict] = None
        for attempt in (1, 2):
            attempt_prompt = prompt if attempt == 1 else prompt + JSON_RETRY_SUFFIX
            try:
                text, stop_reason = self._call_model(api_client, attempt_prompt)
            except Exception as e:
                logger.error(f"Failed to generate thread (attempt {attempt}): {e}")
                continue

            data, status = parse_json_object_tolerant(text)
            thread = normalize_thread(data)
            truncated = status == "truncated" or stop_reason in ("max_tokens", "length")

            if thread and not truncated:
                if status == "repaired":
                    logger.info("Thread JSON needed repair (stray quotes/commas) - repaired OK")
                return self._finalize(thread, analysis)

            reason = ("no JSON object in response" if data is None else
                      "JSON is not a usable thread" if thread is None else
                      "response truncated")
            logger.warning(f"Thread attempt {attempt} unusable: {reason} "
                           f"(stop_reason={stop_reason}, {len(text)} chars of text)")
            if thread and fallback is None:
                fallback = thread

        if fallback:
            logger.warning("Using partially recovered thread (truncated response)")
            return self._finalize(fallback, analysis)
        logger.error("Could not parse thread JSON after retry")
        return None

    def _finalize(self, thread: Dict, analysis: AIAnalysis) -> Dict:
        thread['source_analysis_id'] = analysis.story_title
        thread['generated_at'] = datetime.now().isoformat()
        for tweet in thread.get('tweets', []):
            if tweet['char_count'] > 280:
                logger.warning(f"Tweet {tweet['number']} exceeds 280 chars: {tweet['char_count']}")
        logger.info(f"Successfully generated thread with {len(thread.get('tweets', []))} tweets")
        return thread

    def _call_model(self, api_client, prompt: str) -> Tuple[str, Optional[str]]:
        """One API call; records its cost. Returns (text, stop_reason)."""
        from ..ai.cost_controller import ai_cost_controller

        model = Config.X_THREADS_MODEL
        estimate = ai_cost_controller.estimate_cost(len(prompt), "analysis")
        budget = ai_cost_controller.check_budget_allowance(estimate.estimated_cost)
        if not budget.get('allowed', True):
            raise RuntimeError(f"thread generation blocked by AI budget: {budget.get('reason')}")

        started = time.time()
        # Sampling params (temperature) are not sent: Sonnet 5 rejects them.
        response = api_client.messages.create(
            model=model,
            max_tokens=thread_max_tokens(),
            messages=[{"role": "user", "content": prompt}],
        )
        # Thinking blocks may precede the text on adaptive-thinking models.
        text = extract_response_text(response)
        in_tok, out_tok, cost = thread_call_cost(response, model, prompt, text)
        ai_cost_controller.record_cost(cost, in_tok + out_tok, "x_thread_generation")
        stop_reason = getattr(response, 'stop_reason', None)
        logger.info(f"Thread call: {in_tok}+{out_tok} tokens, ${cost:.4f}, "
                    f"{time.time() - started:.1f}s, stop_reason={stop_reason}, "
                    f"model={getattr(response, 'model', model)}")
        return text, stop_reason

    def generate_mock_thread(self, analysis: AIAnalysis) -> Dict:
        """Generate mock thread for testing without API calls"""
        # Generate realistic tweet lengths
        title_short = analysis.story_title[:80] if len(analysis.story_title) > 80 else analysis.story_title
        
        tweet1 = f"1/5 🔍 ANALÝZA: {title_short}... Co to znamená pro ČR? 🧵"
        tweet2 = f"2/5 📊 Klíčová fakta: {analysis.why_important[:120]}..."
        tweet3 = f"3/5 ⚡ Co přehlížíme: {analysis.what_overlooked[:100]}..."
        tweet4 = f"4/5 🎯 Co sledovat: {analysis.prediction[:100]}..."
        tweet5 = "5/5 💡 Závěr: Situace se rychle vyvíjí. Sledujte náš newsletter pro detailní analýzy. #geopolitika #bezpečnost"
        
        return {
            "thread_title": f"Test: {analysis.story_title[:40]}",
            "tweets": [
                {"number": 1, "content": tweet1, "char_count": len(tweet1)},
                {"number": 2, "content": tweet2, "char_count": len(tweet2)},
                {"number": 3, "content": tweet3, "char_count": len(tweet3)},
                {"number": 4, "content": tweet4, "char_count": len(tweet4)},
                {"number": 5, "content": tweet5, "char_count": len(tweet5)}
            ],
            "hashtags": ["#geopolitika", "#bezpečnost", "#analýza"],
            "estimated_engagement": 7.5,
            "main_topic": "test_topic",
            "source_analysis_id": analysis.story_title,
            "generated_at": datetime.now().isoformat()
        }
    
    def export_html(self, threads: List[Dict], date_str: str = None) -> str:
        """
        Generate HTML preview of threads
        
        Args:
            threads: List of thread data dicts
            date_str: Optional date string for filename
            
        Returns:
            Path to generated HTML file
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X.com vlákna - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f7f9fa;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #14171a;
            font-size: 24px;
            margin-bottom: 20px;
        }}
        .thread-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}
        .thread {{
            background: white;
            border: 1px solid #e1e8ed;
            border-radius: 16px;
            padding: 20px;
        }}
        .thread-title {{
            font-size: 18px;
            font-weight: bold;
            color: #14171a;
            margin-bottom: 15px;
            border-bottom: 2px solid #1da1f2;
            padding-bottom: 10px;
        }}
        .tweet {{
            padding: 12px;
            border-bottom: 1px solid #e1e8ed;
            position: relative;
        }}
        .tweet:last-of-type {{
            border-bottom: none;
        }}
        .tweet-number {{
            color: #536471;
            font-weight: bold;
            font-size: 14px;
        }}
        .tweet-content {{
            color: #14171a;
            font-size: 15px;
            line-height: 1.4;
            margin: 8px 0;
            white-space: pre-wrap;
        }}
        .char-count {{
            position: absolute;
            right: 12px;
            top: 12px;
            color: #536471;
            font-size: 12px;
            background: #f7f9fa;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .char-count.warning {{
            color: #ff6600;
            font-weight: bold;
        }}
        .char-count.error {{
            color: #e0245e;
            font-weight: bold;
        }}
        .hashtags {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e1e8ed;
        }}
        .hashtag {{
            display: inline-block;
            color: #1da1f2;
            margin-right: 10px;
            font-size: 14px;
        }}
        .thread-meta {{
            margin-top: 10px;
            padding: 10px;
            background: #f7f9fa;
            border-radius: 8px;
            font-size: 13px;
            color: #536471;
        }}
        .copy-button {{
            background: #1da1f2;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
        }}
        .copy-button:hover {{
            background: #1a91da;
        }}
        .header-info {{
            background: #fff;
            padding: 20px;
            border-radius: 16px;
            margin-bottom: 20px;
            border: 1px solid #e1e8ed;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-info">
            <h1>🐦 X.com vlákna - GeoPolitical Daily</h1>
            <p style="color: #536471;">Vygenerováno: {datetime.now().strftime("%d.%m.%Y %H:%M")} | Počet vláken: {len(threads)}</p>
            <p style="color: #536471; font-size: 14px;">
                Náhled vláken pro manuální publikaci na X.com. Každé vlákno je optimalizováno pro maximální engagement českého publika.
            </p>
        </div>
        
        <div class="thread-grid">
"""
        
        for i, thread in enumerate(threads, 1):
            html += f"""
            <div class="thread">
                <div class="thread-title">
                    {i}. {thread.get('thread_title', 'Bez názvu')}
                </div>
"""
            
            tweets = thread.get('tweets', [])
            for tweet in tweets:
                char_count = tweet.get('char_count', 0)
                char_class = ''
                if char_count > 280:
                    char_class = 'error'
                elif char_count > 270:
                    char_class = 'warning'
                
                html += f"""
                <div class="tweet">
                    <span class="char-count {char_class}">{char_count}/280</span>
                    <div class="tweet-content">{tweet.get('content', '')}</div>
                </div>
"""
            
            # Add hashtags
            hashtags = thread.get('hashtags', [])
            if hashtags:
                html += '<div class="hashtags">'
                for tag in hashtags:
                    html += f'<span class="hashtag">{tag}</span>'
                html += '</div>'
            
            # Add metadata
            html += f"""
                <div class="thread-meta">
                    <div>📊 Odhadovaný engagement: {thread.get('estimated_engagement', 'N/A')}/10</div>
                    <div>🏷️ Téma: {thread.get('main_topic', 'N/A')}</div>
                    <div>⏰ Vygenerováno: {thread.get('generated_at', 'N/A')[:16]}</div>
                </div>
                <button class="copy-button" onclick="copyThread({i})">📋 Kopírovat vlákno</button>
            </div>
"""
        
        html += """
        </div>
    </div>
    
    <script>
        function copyThread(threadNum) {
            // TODO: Implement copy functionality
            alert('Funkce kopírování bude implementována v další verzi');
        }
    </script>
</body>
</html>"""
        
        # Save HTML
        output_path = self.output_dir / f"threads-{date_str}.html"
        output_path.write_text(html, encoding='utf-8')
        
        logger.info(f"Thread preview exported to: {output_path}")
        return str(output_path)
    
    def export_json(self, threads: List[Dict], date_str: str = None) -> str:
        """Export threads as JSON for potential API integration"""
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        output_path = self.output_dir / f"threads-{date_str}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(threads, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Thread data exported to: {output_path}")
        return str(output_path)