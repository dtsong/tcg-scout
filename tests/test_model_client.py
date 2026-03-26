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
