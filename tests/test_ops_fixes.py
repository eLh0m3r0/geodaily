"""
Regression tests for the 2026-09 operational fixes (no network access):

1. Buttondown "prohibited keyword" rejection -> neutralize + retry, loud failure
3. X-thread JSON truncation/garbage -> tolerant parsing, retry, cost tracking
4. Content-enrichment archive crash on (article, result) tuples
5. "Failed to get recent pipeline runs: 'errors'" row mapping bug
7. OpenRouter wall-clock timeout, one retry, served-model logging
"""

import json
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from src.config import Config
from src.publishers import buttondown_publisher as bd
from src.social import x_thread_generator as xt
from src.ai import llm_client


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _http_response(status: int, payload) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp._content = (payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8")
    resp.url = "https://api.buttondown.com/v1/test"
    resp.headers["Content-Type"] = "application/json"
    return resp


PROHIBITED = {"code": "email_invalid",
              "detail": "Contains prohibited keyword: Leroy Merlin", "metadata": {}}

EMAIL_HTML = ("<html><body><h1>Leroy Merlin quits Russia</h1>"
              '<p><a href="https://example.com/leroy-merlin" title="Leroy Merlin">'
              "Leroy Merlin</a> sold its stores.</p></body></html>")


def _newsletter():
    return SimpleNamespace(email_subject="Leroy Merlin quits Russia", stories=[],
                           date=datetime(2026, 9, 18))


# ---------------------------------------------------------------------------
# 1. Buttondown
# ---------------------------------------------------------------------------

class TestButtondownKeywordHelpers(unittest.TestCase):
    def test_extracts_keyword_from_production_error(self):
        body = json.dumps(PROHIBITED)
        self.assertEqual(bd.extract_prohibited_keywords(body), ["Leroy Merlin"])

    def test_extracts_multiple_and_ignores_other_errors(self):
        body = json.dumps({"detail": "Contains prohibited keywords: Foo, \"Bar Baz\""})
        self.assertEqual(bd.extract_prohibited_keywords(body), ["Foo", "Bar Baz"])
        self.assertEqual(bd.extract_prohibited_keywords(json.dumps({"detail": "Invalid tag"})), [])
        self.assertEqual(bd.extract_prohibited_keywords(""), [])

    def test_neutralized_html_hides_keyword_but_keeps_markup(self):
        html = bd.neutralize_keywords_html(
            '<!-- buttondown-editor-mode: fancy -->\n<style>p{color:red}</style>'
            '<p title="Leroy Merlin">leroy  merlin</p><a href="https://x.com/leroy-merlin">x</a>',
            ["Leroy Merlin"])
        self.assertNotRegex(html.lower(), r"leroy\s+merlin")
        self.assertIn(bd.ZERO_WIDTH_JOINER, html)
        # Attribute value: character references (render identically)
        self.assertIn('title="&#76;eroy &#77;erlin"', html)
        # Untouched: comment, CSS, URL that does not contain the phrase
        self.assertIn("<!-- buttondown-editor-mode: fancy -->", html)
        self.assertIn("<style>p{color:red}</style>", html)
        self.assertIn('href="https://x.com/leroy-merlin"', html)
        # Removing the joiners restores the original visible text exactly
        self.assertIn("leroy  merlin", html.replace(bd.ZERO_WIDTH_JOINER, ""))

    def test_neutralized_subject(self):
        out = bd.neutralize_keywords_text("🌍 Leroy Merlin quits", ["leroy merlin"])
        self.assertNotIn("Leroy Merlin", out)
        self.assertEqual(out.replace(bd.ZERO_WIDTH_JOINER, ""), "🌍 Leroy Merlin quits")


class TestButtondownSendRetry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.status_file = Path(self.tmp.name) / "email_delivery_status.json"
        self.patches = [
            patch.object(Config, "BUTTONDOWN_API_KEY", "test-key"),
            patch.object(Config, "BUTTONDOWN_USERNAME", "geodaily"),
            patch.dict("os.environ", {"EMAIL_DELIVERY_STATUS_FILE": str(self.status_file),
                                      "GITHUB_ACTIONS": ""}),
            # tag lookup: no "weekly" tag -> untargeted send
            patch.object(bd.requests, "get", return_value=_http_response(200, {"results": []})),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _status(self):
        return json.loads(self.status_file.read_text())

    def test_rejected_at_send_is_neutralized_and_retried(self):
        patch_calls = []

        def fake_patch(url, json=None, headers=None, timeout=None):
            patch_calls.append(json)
            if json.get("status") == "about_to_send":
                sends = sum(1 for c in patch_calls if c.get("status") == "about_to_send")
                if sends == 1:
                    return _http_response(400, PROHIBITED)
                return _http_response(200, {"absolute_url": "https://buttondown.com/geodaily/archive/x/"})
            return _http_response(200, {"id": "em_1"})   # draft update

        with patch.object(bd.requests, "post", return_value=_http_response(201, {"id": "em_1"})) as post, \
                patch.object(bd.requests, "patch", side_effect=fake_patch):
            url = bd.ButtondownPublisher().publish(_newsletter(), EMAIL_HTML)

        self.assertEqual(url, "https://buttondown.com/geodaily/archive/x/")
        self.assertEqual(post.call_count, 1)
        update = [c for c in patch_calls if "body" in c]
        self.assertEqual(len(update), 1)
        self.assertNotIn("Leroy Merlin", update[0]["body"])
        self.assertNotIn("Leroy Merlin", update[0]["subject"])
        self.assertIn(bd.ZERO_WIDTH_JOINER, update[0]["subject"])
        self.assertEqual(self._status()["status"], "sent")

    def test_rejected_at_create_is_neutralized_and_retried(self):
        posts = []

        def fake_post(url, json=None, headers=None, timeout=None):
            posts.append(json)
            if len(posts) == 1:
                return _http_response(400, PROHIBITED)
            return _http_response(201, {"id": "em_2"})

        with patch.object(bd.requests, "post", side_effect=fake_post), \
                patch.object(bd.requests, "patch",
                             return_value=_http_response(200, {"absolute_url": "https://b/x"})):
            url = bd.ButtondownPublisher().publish(_newsletter(), EMAIL_HTML)

        self.assertEqual(url, "https://b/x")
        self.assertEqual(len(posts), 2)
        self.assertIn("Leroy Merlin", posts[0]["body"])
        self.assertNotIn("Leroy Merlin", posts[1]["body"])

    def test_persistent_rejection_fails_loudly_with_bounded_retries(self):
        def fake_patch(url, json=None, headers=None, timeout=None):
            if json.get("status") == "about_to_send":
                return _http_response(400, PROHIBITED)   # filter keeps rejecting
            return _http_response(200, {"id": "em_3"})    # draft update accepted

        with patch.object(bd.requests, "post", return_value=_http_response(201, {"id": "em_3"})), \
                patch.object(bd.requests, "patch", side_effect=fake_patch) as p, \
                patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                patch("builtins.print") as fake_print:
            publisher = bd.ButtondownPublisher()
            url = publisher.publish(_newsletter(), EMAIL_HTML)

        self.assertIsNone(url)
        # send, (update, send) once — the same keyword never triggers a 2nd retry
        self.assertEqual(p.call_count, 3)
        status = self._status()
        self.assertEqual(status["status"], "failed")
        self.assertIn("prohibited keyword", status["error"])
        self.assertEqual(status["issue_date"], "2026-09-18")
        self.assertIn("Leroy Merlin", publisher.last_error)
        annotations = [c.args[0] for c in fake_print.call_args_list
                       if c.args and str(c.args[0]).startswith("::error")]
        self.assertEqual(len(annotations), 1)

    def test_non_keyword_error_is_not_retried(self):
        with patch.object(bd.requests, "post", return_value=_http_response(201, {"id": "em_4"})), \
                patch.object(bd.requests, "patch",
                             return_value=_http_response(400, {"detail": "Something else"})) as p:
            url = bd.ButtondownPublisher().publish(_newsletter(), EMAIL_HTML)
        self.assertIsNone(url)
        self.assertEqual(p.call_count, 1)
        self.assertEqual(self._status()["status"], "failed")


# ---------------------------------------------------------------------------
# 3. X threads
# ---------------------------------------------------------------------------

VALID_THREAD = {
    "thread_title": "Test",
    "tweets": [{"number": i, "content": f"{i}/5 text {i}" + (" #geopolitika" if i == 5 else "")}
               for i in range(1, 6)],
    "hashtags": ["#geopolitika"],
}


def _llm_response(text, stop_reason="end_turn", thinking=True):
    blocks = []
    if thinking:
        blocks.append(SimpleNamespace(type="thinking", thinking=""))
    if text:
        blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(content=blocks, stop_reason=stop_reason, model="claude-sonnet-5",
                           usage=SimpleNamespace(input_tokens=1000, output_tokens=2000))


def _analysis():
    return SimpleNamespace(story_title="Story", why_important="Why " * 40,
                           what_overlooked="Overlooked", prediction="Watch",
                           impact_dimension_score=8, urgency_score=7,
                           content_type=SimpleNamespace(value="analysis"))


class TestThreadJsonParsing(unittest.TestCase):
    def test_plain_and_fenced(self):
        obj, status = xt.parse_json_object_tolerant("```json\n" + json.dumps(VALID_THREAD) + "\n```\nHotovo.")
        self.assertEqual(status, "ok")
        self.assertEqual(len(obj["tweets"]), 5)

    def test_unescaped_quotes_newlines_and_trailing_commas(self):
        text = ('{"thread_title": "T", "tweets": [\n'
                '  {"number": 1, "content": "1/3 Trump řekl "ne", pak "možná" a konec"},\n'
                '  {"number": 2, "content": "2/3 první řádek\ndruhý řádek",},\n'
                '  {"number": 3, "content": "3/3 závěr #x"},\n'
                '],}')
        obj, status = xt.parse_json_object_tolerant(text)
        self.assertEqual(status, "repaired")
        self.assertEqual(obj["tweets"][0]["content"], '1/3 Trump řekl "ne", pak "možná" a konec')
        self.assertEqual(obj["tweets"][1]["content"], "2/3 první řádek\ndruhý řádek")

    def test_truncated_response_is_closed_after_last_complete_tweet(self):
        full = json.dumps(VALID_THREAD, ensure_ascii=False, indent=2)
        cut = full[:full.index('"number": 4') + 15]   # mid tweet 4, like production
        with self.assertRaises(json.JSONDecodeError):
            json.loads(cut)
        obj, status = xt.parse_json_object_tolerant(cut)
        self.assertEqual(status, "truncated")
        thread = xt.normalize_thread(obj)
        self.assertIsNotNone(thread)
        self.assertEqual([t["number"] for t in thread["tweets"]], [1, 2, 3])

    def test_no_json(self):
        self.assertEqual(xt.parse_json_object_tolerant(""), (None, "none"))
        self.assertEqual(xt.parse_json_object_tolerant("Sorry, no."), (None, "none"))
        self.assertIsNone(xt.normalize_thread({"tweets": ["only one"]}))


class TestThreadGeneration(unittest.TestCase):
    def setUp(self):
        self.cost = MagicMock()
        self.cost.estimate_cost.return_value = SimpleNamespace(estimated_cost=0.01)
        self.cost.check_budget_allowance.return_value = {"allowed": True}
        self.cost_patch = patch("src.ai.cost_controller.ai_cost_controller", self.cost)
        self.cost_patch.start()
        self.gen = xt.XThreadGenerator()

    def tearDown(self):
        self.cost_patch.stop()

    def test_truncated_first_answer_triggers_one_retry_and_costs_are_recorded(self):
        full = json.dumps(VALID_THREAD, ensure_ascii=False)
        client = MagicMock()
        client.messages.create.side_effect = [
            _llm_response(full[:len(full) // 2], stop_reason="max_tokens"),
            _llm_response(full),
        ]
        thread = self.gen.generate_thread_from_analysis(_analysis(), client)

        self.assertIsNotNone(thread)
        self.assertEqual(len(thread["tweets"]), 5)
        self.assertEqual(client.messages.create.call_count, 2)
        first, second = client.messages.create.call_args_list
        self.assertGreaterEqual(first.kwargs["max_tokens"], 16000)
        self.assertNotIn("temperature", first.kwargs)
        self.assertIn(xt.JSON_RETRY_SUFFIX.strip()[:20], second.kwargs["messages"][0]["content"])
        self.assertEqual(self.cost.record_cost.call_count, 2)
        for call in self.cost.record_cost.call_args_list:
            self.assertEqual(call.args[2], "x_thread_generation")
            self.assertEqual(call.args[1], 3000)

    def test_empty_answers_give_none_after_one_retry(self):
        client = MagicMock()
        client.messages.create.return_value = _llm_response("", stop_reason="max_tokens")
        self.assertIsNone(self.gen.generate_thread_from_analysis(_analysis(), client))
        self.assertEqual(client.messages.create.call_count, 2)

    def test_partial_thread_used_when_retry_also_fails(self):
        full = json.dumps(VALID_THREAD, ensure_ascii=False)
        client = MagicMock()
        client.messages.create.side_effect = [
            _llm_response(full[:full.index('"number": 5')], stop_reason="max_tokens"),
            _llm_response("no json at all"),
        ]
        thread = self.gen.generate_thread_from_analysis(_analysis(), client)
        self.assertEqual(len(thread["tweets"]), 4)

    def test_thread_cost_uses_thread_model_rates(self):
        resp = _llm_response("x")
        _, _, cost = xt.thread_call_cost(resp, "claude-sonnet-5", "", "")
        self.assertAlmostEqual(cost, 1000 / 1e6 * 2.0 + 2000 / 1e6 * 10.0)
        resp.usage.cost_usd = 0.5          # provider-billed amount wins
        self.assertEqual(xt.thread_call_cost(resp, "claude-sonnet-5", "", "")[2], 0.5)


# ---------------------------------------------------------------------------
# 4. Content-extraction archive
# ---------------------------------------------------------------------------

class TestContentExtractionArchive(unittest.TestCase):
    def test_accepts_article_result_tuples(self):
        from src.archiver.ai_data_archiver import AIDataArchiver
        from src.content.intelligent_scraper import ContentExtractionResult

        with tempfile.TemporaryDirectory() as tmp:
            archiver = AIDataArchiver()
            archiver.enabled = True
            archiver.current_run_path = Path(tmp)
            article = SimpleNamespace(title="A", url="https://a", source="S")
            ok = ContentExtractionResult(full_content="text " * 50, word_count=50,
                                         extraction_method="css", quality_score=0.8,
                                         extraction_time=0.1, success=True)
            archiver.archive_content_extraction_results(
                [(article, None), (article, ok), {"success": False, "extraction_method": "x_fallback"}])
            data = json.loads((Path(tmp) / "content_extraction_results.json").read_text())

        self.assertEqual(data["total_articles"], 3)
        self.assertEqual(data["extraction_summary"]["successful_extractions"], 1)
        self.assertEqual(data["extraction_summary"]["skipped"], 1)
        self.assertEqual(data["extraction_summary"]["fallback_used"], 1)
        self.assertEqual(data["detailed_results"][0]["url"], "https://a")


# ---------------------------------------------------------------------------
# 5. Metrics database
# ---------------------------------------------------------------------------

class TestRecentPipelineRuns(unittest.TestCase):
    def test_rows_map_back_to_pipeline_runs(self):
        from src.metrics.database import MetricsDatabase, PipelineRun

        with tempfile.TemporaryDirectory() as tmp:
            db = MetricsDatabase(db_path=str(Path(tmp) / "m.db"))
            try:
                run = PipelineRun(run_id="r1", run_date=datetime(2026, 9, 29).date(),
                                  start_time=datetime(2026, 9, 29, 3, 30),
                                  end_time=datetime(2026, 9, 29, 3, 45),
                                  status="completed", errors=["boom"], newsletter_published=True)
                self.assertTrue(db.create_pipeline_run(run))
                runs = db.get_recent_pipeline_runs(5)
                single = db.get_pipeline_run("r1")
            finally:
                db.close()

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].errors, ["boom"])
        self.assertEqual(runs[0].end_time, datetime(2026, 9, 29, 3, 45))
        self.assertEqual(runs[0].start_time, datetime(2026, 9, 29, 3, 30))
        self.assertTrue(runs[0].newsletter_published)
        self.assertEqual(single.run_id, "r1")


# ---------------------------------------------------------------------------
# 7. OpenRouter client
# ---------------------------------------------------------------------------

def _openrouter_ok(model="deepseek/deepseek-v4.1-flash-20260901"):
    return SimpleNamespace(status_code=200, text="{}", json=lambda: {
        "model": model, "provider": "DeepInfra",
        "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001},
    })


class TestOpenRouterTimeouts(unittest.TestCase):
    def _client(self, timeout=0.3):
        return llm_client.OpenRouterClient(api_key="k", timeout=timeout, max_retries=3,
                                           timeout_retries=1)

    def test_hung_request_times_out_and_is_retried_once(self):
        calls = []

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.append(json)
            if len(calls) == 1:
                time.sleep(1.5)            # upstream hangs
            return _openrouter_ok()

        with patch.object(llm_client.requests, "post", side_effect=fake_post):
            with self.assertLogs(llm_client.logger, level="INFO") as logs:
                started = time.monotonic()
                resp = self._client().messages.create(
                    model="deepseek/deepseek-v4.1-flash", max_tokens=100,
                    messages=[{"role": "user", "content": "hi"}])
                elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.4)      # did not wait for the hung call
        self.assertEqual(len(calls), 2)
        self.assertEqual(resp.content[0].text, "hello")
        self.assertEqual(resp.served_model, "deepseek/deepseek-v4.1-flash-20260901")
        self.assertEqual(resp.model, resp.served_model)
        self.assertEqual(resp.requested_model, "deepseek/deepseek-v4.1-flash")
        self.assertIsNotNone(resp.latency_s)
        info = [r for r in logs.output if "LLM call:" in r]
        self.assertEqual(len(info), 1)
        self.assertIn("served_model=deepseek/deepseek-v4.1-flash-20260901", info[0])
        self.assertIn("requested_model=deepseek/deepseek-v4.1-flash", info[0])
        # CLAUDE.md: no sampling params, no reasoning cap
        for body in calls:
            for forbidden in ("temperature", "top_p", "top_k", "reasoning"):
                self.assertNotIn(forbidden, body)

    def test_second_timeout_raises(self):
        def hang(url, headers=None, json=None, timeout=None):
            time.sleep(1.0)
            return _openrouter_ok()

        with patch.object(llm_client.requests, "post", side_effect=hang) as post:
            with self.assertRaises(llm_client.LLMTimeoutError):
                self._client(timeout=0.2).messages.create(
                    model="m", max_tokens=10, messages=[{"role": "user", "content": "x"}])
        self.assertEqual(post.call_count, 2)

    def test_default_timeout_is_600s(self):
        with patch.object(Config, "OPENROUTER_API_KEY", "k"), \
                patch.dict("os.environ", {}, clear=False) as env:
            env.pop("AI_REQUEST_TIMEOUT_S", None)
            client = llm_client.build_llm_client("openrouter")
        self.assertEqual(client._timeout, 600.0)
        self.assertEqual(client._timeout_retries, 1)


if __name__ == "__main__":
    unittest.main()
