import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services import llm_service as llm


class LLMServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-only-key",
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_openai_preserves_prompt_history_and_does_not_store_response(self):
        create = AsyncMock(return_value=SimpleNamespace(status="completed", output_text="  answer  "))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        history = [{"role": "user", "content": "first"}, {"role": "assistant", "content": "reply"}, {"role": "user", "content": "next"}]
        with patch.object(llm, "_openai_client", return_value=client), patch.object(llm, "_claude_client") as old:
            self.assertEqual(await llm.generate_text(history, system="instructions", max_tokens=1024, temperature=0), "answer")
        params = create.call_args.kwargs
        self.assertEqual(params["input"], history)
        self.assertEqual(params["instructions"], "instructions")
        self.assertEqual(params["reasoning"], {"effort": "low"})
        self.assertGreater(params["max_output_tokens"], 1024)
        self.assertNotIn("temperature", params)
        self.assertFalse(params["store"])
        old.assert_not_called()

    async def test_fast_workloads_keep_their_own_model_and_output_limit(self):
        create = AsyncMock(return_value=SimpleNamespace(status="completed", output_text='{"age":30}'))
        with patch.object(llm, "_openai_client", return_value=SimpleNamespace(responses=SimpleNamespace(create=create))):
            await llm.generate_text([{"role": "user", "content": "profile"}], task="fast", max_tokens=200, temperature=0)
        params = create.call_args.kwargs
        self.assertEqual(params["model"], "gpt-4.1-mini")
        self.assertEqual(params["max_output_tokens"], 200)
        self.assertEqual(params["temperature"], 0)
        self.assertNotIn("reasoning", params)

    async def test_empty_or_incomplete_responses_are_errors(self):
        for status, text in [("completed", " "), ("incomplete", "partial JSON"), ("failed", "")]:
            with self.subTest(status=status):
                create = AsyncMock(return_value=SimpleNamespace(status=status, output_text=text))
                with patch.object(llm, "_openai_client", return_value=SimpleNamespace(responses=SimpleNamespace(create=create))):
                    with self.assertRaises(RuntimeError):
                        await llm.generate_text([{"role": "user", "content": "test"}])

    async def test_upstream_failure_does_not_silently_switch_providers(self):
        create = AsyncMock(side_effect=RuntimeError("upstream unavailable"))
        with patch.object(llm, "_openai_client", return_value=SimpleNamespace(responses=SimpleNamespace(create=create))), patch.object(llm, "_claude_client") as old:
            with self.assertRaisesRegex(RuntimeError, "upstream unavailable"):
                await llm.generate_text([{"role": "user", "content": "test"}])
        old.assert_not_called()

    async def test_explicit_claude_configuration_remains_supported(self):
        os.environ["LLM_PROVIDER"] = "claude"
        create = AsyncMock(return_value=SimpleNamespace(content=[SimpleNamespace(type="text", text="answer")]))
        with patch.object(llm, "_claude_client", return_value=SimpleNamespace(messages=SimpleNamespace(create=create))), patch.object(llm, "_openai_client") as other:
            self.assertEqual(await llm.generate_text([{"role": "user", "content": "test"}], task="fast"), "answer")
        self.assertEqual(create.call_args.kwargs["model"], "claude-haiku-4-5-20251001")
        other.assert_not_called()

    def test_key_status_uses_only_the_selected_provider(self):
        self.assertTrue(llm.is_api_key_configured())
        os.environ["LLM_PROVIDER"] = "claude"
        self.assertFalse(llm.is_api_key_configured())

    def test_missing_openai_key_does_not_use_claude_key(self):
        os.environ.pop("OPENAI_API_KEY")
        os.environ["CLAUDE_API_KEY"] = "test-only-key"
        llm._openai_client.cache_clear()
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            llm._openai_client()

    def test_unknown_provider_is_rejected(self):
        os.environ["LLM_PROVIDER"] = "typo"
        with self.assertRaises(ValueError):
            llm.get_provider()


if __name__ == "__main__":
    unittest.main()
