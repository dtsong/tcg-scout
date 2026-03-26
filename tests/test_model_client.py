"""Tests for reports/model_client.py — ModelClient abstraction."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("anthropic")

from reports.model_client import ModelClient, create_client_from_config

# --- Helpers ---


def _mock_anthropic_response(text: str) -> MagicMock:
    """Build a mock Anthropic message response."""
    mock_content = MagicMock()
    mock_content.text = text
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    return mock_message


# --- ModelClient init ---


class TestModelClientInit:
    def test_stores_config(self):
        with patch("reports.model_client.anthropic.Anthropic"):
            client = ModelClient(model_id="test-model", temperature=0.5, max_tokens=1024)
        assert client.model_id == "test-model"
        assert client.temperature == 0.5
        assert client.max_tokens == 1024

    def test_defaults(self):
        with patch("reports.model_client.anthropic.Anthropic"):
            client = ModelClient(model_id="test-model")
        assert client.temperature == 0.3
        assert client.max_tokens == 2048


# --- generate ---


class TestGenerate:
    def test_returns_stripped_text(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("  hello world  ")
            MockAnthropicCls.return_value.messages.create.return_value = mock_resp
            client = ModelClient(model_id="test-model")
            result = client.generate("prompt text")
        assert result == "hello world"

    def test_passes_model_and_params(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("ok")
            mock_create = MockAnthropicCls.return_value.messages.create
            mock_create.return_value = mock_resp
            client = ModelClient(model_id="my-model", temperature=0.7, max_tokens=512)
            client.generate("test prompt")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "my-model"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 512
        assert call_kwargs["messages"] == [{"role": "user", "content": "test prompt"}]

    def test_system_prompt_included_when_provided(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("ok")
            mock_create = MockAnthropicCls.return_value.messages.create
            mock_create.return_value = mock_resp
            client = ModelClient(model_id="m")
            client.generate("user msg", system_prompt="sys msg")

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["system"] == "sys msg"

    def test_system_prompt_omitted_when_none(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("ok")
            mock_create = MockAnthropicCls.return_value.messages.create
            mock_create.return_value = mock_resp
            client = ModelClient(model_id="m")
            client.generate("user msg")

        call_kwargs = mock_create.call_args[1]
        assert "system" not in call_kwargs

    def test_raises_on_empty_content(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_message = MagicMock()
            mock_message.content = []
            mock_message.stop_reason = "end_turn"
            MockAnthropicCls.return_value.messages.create.return_value = mock_message
            client = ModelClient(model_id="test-model")
            with pytest.raises(ValueError, match="empty content"):
                client.generate("prompt")

    def test_raises_on_non_text_block(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_block = MagicMock(spec=[])  # no .text attribute
            mock_message = MagicMock()
            mock_message.content = [mock_block]
            MockAnthropicCls.return_value.messages.create.return_value = mock_message
            client = ModelClient(model_id="test-model")
            with pytest.raises(TypeError, match="Expected TextBlock"):
                client.generate("prompt")

    def test_api_error_propagates(self):
        import anthropic as anthropic_mod

        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            MockAnthropicCls.return_value.messages.create.side_effect = anthropic_mod.APIError(
                message="rate limited",
                request=MagicMock(),
                body=None,
            )
            client = ModelClient(model_id="test-model")
            with pytest.raises(anthropic_mod.APIError):
                client.generate("prompt")

    def test_per_call_overrides(self):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("ok")
            mock_create = MockAnthropicCls.return_value.messages.create
            mock_create.return_value = mock_resp
            client = ModelClient(model_id="m", temperature=0.3, max_tokens=2048)
            client.generate("p", temperature=0.9, max_tokens=100)

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["temperature"] == 0.9
        assert call_kwargs["max_tokens"] == 100


# --- cache_key ---


class TestCacheKey:
    def test_deterministic(self):
        k1 = ModelClient.cache_key("hello")
        k2 = ModelClient.cache_key("hello")
        assert k1 == k2

    def test_different_inputs_different_keys(self):
        k1 = ModelClient.cache_key("hello")
        k2 = ModelClient.cache_key("world")
        assert k1 != k2

    def test_key_length(self):
        key = ModelClient.cache_key("test")
        assert len(key) == 12

    def test_different_system_prompts_different_keys(self):
        k1 = ModelClient.cache_key("prompt", system_prompt="sys1")
        k2 = ModelClient.cache_key("prompt", system_prompt="sys2")
        assert k1 != k2

    def test_different_model_ids_different_keys(self):
        k1 = ModelClient.cache_key("prompt", model_id="model-a")
        k2 = ModelClient.cache_key("prompt", model_id="model-b")
        assert k1 != k2

    def test_different_temperature_different_keys(self):
        k1 = ModelClient.cache_key("prompt", temperature=0.3)
        k2 = ModelClient.cache_key("prompt", temperature=0.9)
        assert k1 != k2


# --- generate_cached ---


class TestGenerateCached:
    def test_writes_cache_on_miss(self, tmp_path):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("cached response")
            MockAnthropicCls.return_value.messages.create.return_value = mock_resp
            client = ModelClient(model_id="m")
            text, data_hash, hit = client.generate_cached("prompt", tmp_path)

        assert text == "cached response"
        assert not hit
        cache_file = tmp_path / f".llm-cache-{data_hash}.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        assert cached["response"] == "cached response"

    def test_returns_cached_on_hit(self, tmp_path):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("first call")
            mock_create = MockAnthropicCls.return_value.messages.create
            mock_create.return_value = mock_resp
            client = ModelClient(model_id="m")

            # First call -- miss
            text1, _, hit1 = client.generate_cached("prompt", tmp_path)
            # Second call -- hit
            text2, _, hit2 = client.generate_cached("prompt", tmp_path)

        assert not hit1
        assert hit2
        assert text1 == text2
        assert mock_create.call_count == 1

    def test_corrupt_cache_regenerates(self, tmp_path):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("regenerated")
            MockAnthropicCls.return_value.messages.create.return_value = mock_resp
            client = ModelClient(model_id="m")

            # Write corrupt cache file
            data_hash = client.cache_key(
                "prompt",
                model_id="m",
                system_prompt="",
                temperature=0.3,
                max_tokens=2048,
            )
            cache_file = tmp_path / f".llm-cache-{data_hash}.json"
            cache_file.write_text("not valid json", encoding="utf-8")

            text, _, hit = client.generate_cached("prompt", tmp_path)

        assert text == "regenerated"
        assert not hit

    def test_per_call_overrides_produce_distinct_cache_keys(self, tmp_path):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            call_count = 0

            def make_response(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return _mock_anthropic_response(f"response-{call_count}")

            MockAnthropicCls.return_value.messages.create.side_effect = make_response
            client = ModelClient(model_id="m")

            # Same prompt, different temperature -> should produce two cache misses
            text1, hash1, hit1 = client.generate_cached("prompt", tmp_path, temperature=0.3)
            text2, hash2, hit2 = client.generate_cached("prompt", tmp_path, temperature=0.9)

        assert not hit1
        assert not hit2
        assert hash1 != hash2
        assert text1 != text2
        assert call_count == 2

    def test_per_call_max_tokens_override_distinct_cache(self, tmp_path):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            call_count = 0

            def make_response(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return _mock_anthropic_response(f"response-{call_count}")

            MockAnthropicCls.return_value.messages.create.side_effect = make_response
            client = ModelClient(model_id="m")

            text1, hash1, hit1 = client.generate_cached("prompt", tmp_path, max_tokens=512)
            text2, hash2, hit2 = client.generate_cached("prompt", tmp_path, max_tokens=4096)

        assert not hit1
        assert not hit2
        assert hash1 != hash2
        assert call_count == 2

    def test_custom_cache_prefix(self, tmp_path):
        with patch("reports.model_client.anthropic.Anthropic") as MockAnthropicCls:
            mock_resp = _mock_anthropic_response("ok")
            MockAnthropicCls.return_value.messages.create.return_value = mock_resp
            client = ModelClient(model_id="m")
            _, data_hash, _ = client.generate_cached("p", tmp_path, cache_prefix=".my-cache")

        assert (tmp_path / f".my-cache-{data_hash}.json").exists()


# --- create_client_from_config ---


class TestCreateClientFromConfig:
    def test_uses_config_values(self):
        with (
            patch("reports.model_client.anthropic.Anthropic"),
            patch("reports.model_client.REPORT_LLM_MODEL", "cfg-model", create=True),
            patch("reports.model_client.REPORT_LLM_TEMPERATURE", 0.42, create=True),
            patch("reports.model_client.REPORT_LLM_MAX_TOKENS", 999, create=True),
        ):
            # Patch the config imports inside the function
            with patch.dict(
                "sys.modules",
                {
                    "config": MagicMock(
                        REPORT_LLM_MODEL="cfg-model",
                        REPORT_LLM_TEMPERATURE=0.42,
                        REPORT_LLM_MAX_TOKENS=999,
                    )
                },
            ):
                client = create_client_from_config()
        assert client.model_id == "cfg-model"
        assert client.temperature == 0.42
        assert client.max_tokens == 999
