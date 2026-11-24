"""Structured answer generation through local or OpenAI-compatible chat endpoints."""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx
import instructor
from instructor.core.exceptions import InstructorRetryException
from openai import APIError, APITimeoutError, OpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.config import Settings
from app.core.telemetry import ProviderCall, begin_provider_call
from app.schemas.answers import GroundedResponse
from app.services.generation.context import pack_context
from app.services.generation.evidence import EvidencePassage
from app.services.retrieval.dense import RetrievedChunk

logger = logging.getLogger("research.generation")


class LLMProviderError(RuntimeError):
    error_code = "LLM_PROVIDER_FAILED"


class LLMTimeoutError(LLMProviderError):
    error_code = "LLM_TIMEOUT"


class LLMRateLimitError(LLMProviderError):
    error_code = "LLM_RATE_LIMITED"


@dataclass(frozen=True)
class GenerationResult:
    response: GroundedResponse
    passages: Sequence[EvidencePassage]


class LLMProvider(Protocol):
    async def generate(
        self, question: str, evidence: Sequence[RetrievedChunk]
    ) -> GenerationResult: ...

    def close(self) -> None: ...


def _exception_chain(error: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        extra_body: dict[str, object] | None = None,
        input_token_budget: int = 6000,
    ) -> None:
        self._openai_client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self._client = instructor.from_openai(self._openai_client, mode=instructor.Mode.JSON_SCHEMA)
        self._model = model
        self._extra_body = extra_body
        self._input_token_budget = input_token_budget

    def _messages(
        self, question: str, evidence: Sequence[RetrievedChunk]
    ) -> tuple[list[ChatCompletionMessageParam], list[EvidencePassage]]:
        messages, passages = pack_context(
            question,
            evidence,
            input_budget=self._input_token_budget,
            schema_factory=lambda count: GroundedResponse.model_json_schema(),
        )
        if not passages:
            raise LLMProviderError("The hosted context budget cannot fit complete evidence.")
        return messages, passages

    async def generate(self, question: str, evidence: Sequence[RetrievedChunk]) -> GenerationResult:
        messages, passages = self._messages(question, evidence)
        usage = begin_provider_call("hosted")
        try:
            response = await asyncio.to_thread(self._generate_sync, messages, usage)
            return GenerationResult(response, passages)
        except APITimeoutError:
            raise LLMTimeoutError() from None
        except RateLimitError:
            raise LLMRateLimitError() from None
        except InstructorRetryException as exc:
            # Instructor initializes total_usage to zero even if no usage was
            # received. Only a complete set of actual attempt responses is known.
            attempts = exc.failed_attempts or []
            counts = [
                getattr(getattr(row.completion, "usage", None), "total_tokens", None)
                for row in attempts
            ]
            if (
                exc.n_attempts > 0
                and len(attempts) == exc.n_attempts
                and [row.attempt_number for row in attempts] == list(range(1, exc.n_attempts + 1))
                and all(type(count) is int and count >= 0 for count in counts)
            ):
                usage.complete(sum(cast(list[int], counts)))
            errors: list[BaseException] = [
                attempt.exception
                for attempt in exc.failed_attempts or []
                if attempt.exception is not None
            ]
            errors.extend(_exception_chain(exc))
            if any(isinstance(error, APITimeoutError) for error in errors):
                raise LLMTimeoutError() from None
            if any(
                isinstance(error, RateLimitError)
                or (isinstance(error, APIError) and getattr(error, "status_code", None) == 429)
                for error in errors
            ):
                raise LLMRateLimitError() from None
            raise LLMProviderError(
                "The language model returned an invalid structured response."
            ) from None
        except APIError:
            raise LLMProviderError() from None
        except ValidationError:
            raise LLMProviderError(
                "The language model returned an invalid structured response."
            ) from None

    def _generate_sync(
        self, messages: list[ChatCompletionMessageParam], usage: ProviderCall
    ) -> GroundedResponse:
        response, completion = cast(
            tuple[GroundedResponse, Any],
            self._client.create_with_completion(
                model=self._model,
                messages=messages,
                response_model=GroundedResponse,
                max_retries=1,
                extra_body=self._extra_body,
            ),
        )
        usage.complete(getattr(getattr(completion, "usage", None), "total_tokens", None))
        return response

    def close(self) -> None:
        self._openai_client.close()


def _ollama_response_schema(source_count: int) -> dict[str, Any]:
    schema = GroundedResponse.model_json_schema()
    # Constrain generation itself, in addition to validating the returned indices.
    # The enum prevents a small model from using page numbers or one-based indices.
    schema["$defs"]["GeneratedCitation"]["properties"]["evidence_index"]["enum"] = list(
        range(source_count)
    )
    return schema


class OllamaLLM:
    """Use Ollama's native API so runtime options actually take effect.

    Context packing keeps complete selected passages and may skip ones that do
    not fit. The returned passage mapping connects model context indices to the
    original retrieval results and source ranges.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: int,
        num_ctx: int,
        max_output_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # Accept the existing base setting even if it includes the compatibility suffix.
        self._url = base_url.rstrip("/").removesuffix("/v1") + "/api/chat"
        self._model = model
        self._timeout = timeout_seconds
        self._num_ctx = num_ctx
        self._max_output_tokens = max_output_tokens
        self._transport = transport

    def _messages(
        self, question: str, evidence: Sequence[RetrievedChunk]
    ) -> tuple[list[ChatCompletionMessageParam], list[EvidencePassage]]:
        selected, selected_passages = pack_context(
            question,
            evidence,
            input_budget=self._num_ctx - self._max_output_tokens,
            schema_factory=_ollama_response_schema,
        )
        if not selected_passages:
            raise LLMProviderError(
                "The configured local context cannot fit a complete evidence passage."
            )
        return selected, selected_passages

    async def generate(self, question: str, evidence: Sequence[RetrievedChunk]) -> GenerationResult:
        messages, passages = self._messages(question, evidence)
        source_count = len(passages)
        logger.info("answer.local_context_prepared", extra={"evidence_count": source_count})
        usage = begin_provider_call("local")
        payload = {
            "model": self._model,
            "messages": messages,
            "format": _ollama_response_schema(source_count),
            "stream": False,
            "options": {
                "num_ctx": self._num_ctx,
                "num_predict": self._max_output_tokens,
                "temperature": 0,
            },
        }
        try:
            # One total deadline; cancellation closes the async request rather than
            # leaving a synchronous inference/retry running in an executor thread.
            async with asyncio.timeout(self._timeout):
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    response = await client.post(self._url, json=payload)
                    if response.status_code == 429:
                        raise LLMRateLimitError()
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict):
                        raise LLMProviderError("The language model returned an invalid response.")
                    prompt_count, answer_count = (
                        body.get("prompt_eval_count"),
                        body.get("eval_count"),
                    )
                    if (
                        type(prompt_count) is int
                        and type(answer_count) is int
                        and prompt_count >= 0
                        and answer_count >= 0
                    ):
                        usage.complete(prompt_count + answer_count)
                    if body.get("done") is not True or body.get("done_reason") == "length":
                        raise LLMProviderError("The language model did not complete its response.")
                    draft = GroundedResponse.model_validate_json(body["message"]["content"])
                    if any(item.evidence_index >= source_count for item in draft.citations):
                        raise LLMProviderError(
                            "The language model cited evidence outside its context."
                        )
                    return GenerationResult(draft, passages)
        except (TimeoutError, httpx.TimeoutException):
            raise LLMTimeoutError() from None
        except LLMProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise LLMProviderError(
                "The language model request or structured response failed."
            ) from None

    def close(self) -> None:
        # Each asynchronous request owns and closes its client, including on cancellation.
        pass


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "local":
        return OllamaLLM(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.llm_timeout_seconds,
            num_ctx=settings.ollama_num_ctx,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    return OpenAICompatibleLLM(
        base_url=settings.hosted_llm_base_url,
        api_key=settings.hosted_llm_api_key.get_secret_value(),
        model=settings.hosted_llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        input_token_budget=settings.hosted_llm_input_token_budget,
    )
