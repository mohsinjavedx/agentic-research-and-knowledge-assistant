import asyncio

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import APITimeoutError
from openai.types.chat import ChatCompletionMessageParam

from app.providers.llm import LLMTimeoutError, OpenAICompatibleLLM
from app.schemas.answers import GroundedResponse


def test_instructor_wrapped_timeout_is_classified_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = OpenAICompatibleLLM(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="llama3.2:3b",
        timeout_seconds=1,
    )

    def raise_wrapped_timeout(messages: list[ChatCompletionMessageParam]) -> GroundedResponse:
        del messages
        timeout = APITimeoutError(
            request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
        )
        raise InstructorRetryException(
            "All structured output attempts failed.",
            n_attempts=1,
            total_usage=None,
            failed_attempts=[],
        ) from timeout

    monkeypatch.setattr(provider, "_generate_sync", raise_wrapped_timeout)
    try:
        with pytest.raises(LLMTimeoutError):
            asyncio.run(provider.generate("What is in the evidence?", []))
    finally:
        provider.close()
