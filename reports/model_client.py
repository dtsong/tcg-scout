"""ModelClient abstraction for LLM interactions in Scout."""

import hashlib
import json
import logging
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)


class ModelClient:
    """Configurable wrapper around the Anthropic SDK.

    Centralizes model ID, temperature, and max_tokens so callers
    don't instantiate ``anthropic.Anthropic()`` directly.
    """

    def __init__(
        self,
        model_id: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a prompt to the configured model and return the text response.

        Parameters
        ----------
        user_prompt:
            The user message content.
        system_prompt:
            Optional system-level instruction.
        temperature:
            Override the instance default for this call.
        max_tokens:
            Override the instance default for this call.

        Returns
        -------
        str
            Raw text from the first content block of the model response.
        """
        kwargs: dict = {
            "model": self.model_id,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt is not None:
            kwargs["system"] = system_prompt

        message = self._client.messages.create(**kwargs)
        return message.content[0].text.strip()

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------

    @staticmethod
    def cache_key(prompt: str) -> str:
        """Return a short hash suitable for use as a file-system cache key."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    def generate_cached(
        self,
        user_prompt: str,
        cache_dir: Path,
        cache_prefix: str = ".llm-cache",
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, str, bool]:
        """Generate with hash-based caching.

        Returns
        -------
        tuple[str, str, bool]
            (response_text, data_hash, cache_hit)
        """
        data_hash = self.cache_key(user_prompt)
        cache_path = cache_dir / f"{cache_prefix}-{data_hash}.json"

        if cache_path.exists():
            logger.info("Cache hit (hash %s)", data_hash)
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return cached["response"], data_hash, True

        logger.info("Calling %s (hash %s)", self.model_id, data_hash)
        response = self.generate(
            user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"response": response}, ensure_ascii=False),
            encoding="utf-8",
        )
        return response, data_hash, False


def create_client_from_config() -> ModelClient:
    """Factory that builds a ModelClient from ``config`` module settings."""
    from config import REPORT_LLM_MAX_TOKENS, REPORT_LLM_MODEL, REPORT_LLM_TEMPERATURE

    return ModelClient(
        model_id=REPORT_LLM_MODEL,
        temperature=REPORT_LLM_TEMPERATURE,
        max_tokens=REPORT_LLM_MAX_TOKENS,
    )
