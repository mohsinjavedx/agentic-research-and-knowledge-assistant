"""Pinned BGE embeddings, with lazy ONNX CPU inference or a hosted HTTP endpoint."""

from collections.abc import Sequence
from typing import Any, Protocol

import httpx
import numpy as np
from tokenizers import Tokenizer

from app.core.config import Settings
from app.providers.identity import BGE_MODEL, BGE_REVISION, EmbeddingIdentity

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingProviderError(ValueError):
    error_code = "EMBEDDING_PROVIDER_FAILED"


class EmbeddingInputTooLong(EmbeddingProviderError):
    error_code = "EMBEDDING_INPUT_TOO_LONG"


class BGETokenizer:
    name = f"{BGE_MODEL}@{BGE_REVISION}:wordpiece"
    max_tokens = 512
    content_limit = 510

    def __init__(self, engine: Tokenizer | None = None) -> None:
        self._engine = engine

    def _get(self) -> Tokenizer:
        if self._engine is None:
            try:
                from huggingface_hub import hf_hub_download

                path = hf_hub_download(BGE_MODEL, "tokenizer.json", revision=BGE_REVISION)
                self._engine = Tokenizer.from_file(path)
                self._engine.no_truncation()
                self._engine.no_padding()
            except Exception:
                raise EmbeddingProviderError("EMBEDDING_TOKENIZER_UNAVAILABLE") from None
        return self._engine

    def count(self, text: str, *, include_special_tokens: bool = False) -> int:
        return len(self._get().encode(text, add_special_tokens=include_special_tokens).ids)

    def inputs(self, texts: Sequence[str]) -> dict[str, Any]:
        encodings = self._get().encode_batch(list(texts), add_special_tokens=True)
        for index, encoded in enumerate(encodings):
            if len(encoded.ids) > self.max_tokens:
                raise EmbeddingInputTooLong(
                    f"Input {index} has {len(encoded.ids)} model tokens; "
                    f"maximum is {self.max_tokens}."
                )
        width = max(len(encoded.ids) for encoded in encodings)
        ids = np.zeros((len(texts), width), dtype=np.int64)
        masks, types = np.zeros_like(ids), np.zeros_like(ids)
        for index, encoded in enumerate(encodings):
            length = len(encoded.ids)
            ids[index, :length] = encoded.ids
            masks[index, :length] = encoded.attention_mask
            types[index, :length] = encoded.type_ids
        return {"input_ids": ids, "attention_mask": masks, "token_type_ids": types}


class EmbeddingProvider(Protocol):
    identity: EmbeddingIdentity
    kind: str
    tokenizer: BGETokenizer

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def close(self) -> None: ...


def normalize_vectors(value: object, expected_count: int) -> list[list[float]]:
    """Enforce the wire/database contract before any batch can be persisted."""
    try:
        vectors = np.asarray(value)
        if vectors.shape != (expected_count, 384) or vectors.dtype.kind not in "fiu":
            raise ValueError
        vectors = vectors.astype(np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if not np.isfinite(vectors).all() or not np.isfinite(norms).all() or (norms <= 0).any():
            raise ValueError
        normalized = (vectors / norms).astype(np.float32)
        return [[float(item) for item in row] for row in normalized]
    except (ValueError, TypeError, OverflowError):
        raise EmbeddingProviderError("INVALID_EMBEDDING_VECTORS") from None


class _BGEProvider:
    identity = EmbeddingIdentity()

    def __init__(self, tokenizer: BGETokenizer | None, batch_size: int) -> None:
        if not 1 <= batch_size <= 64:
            raise ValueError("Embedding batch size must be between 1 and 64")
        self.tokenizer = tokenizer or BGETokenizer()
        self.batch_size = batch_size

    def _validate(self, texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingProviderError("EMPTY_EMBEDDING_INPUT")
        # Reject the entire request before sending text or loading neural weights.
        for index, text in enumerate(texts):
            count = self.tokenizer.count(text, include_special_tokens=True)
            if count > self.tokenizer.max_tokens:
                raise EmbeddingInputTooLong(
                    f"Input {index} has {count} model tokens; maximum is 512."
                )

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise EmbeddingProviderError("EMPTY_EMBEDDING_INPUT")
        return self.embed_documents([QUERY_INSTRUCTION + text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class LocalBGEProvider(_BGEProvider):
    kind = "local"

    def __init__(self, *, tokenizer: BGETokenizer | None = None, batch_size: int = 8) -> None:
        super().__init__(tokenizer, batch_size)
        self._session: Any = None

    def _get_session(self) -> Any:
        if self._session is None:
            try:
                import onnxruntime as ort
                from huggingface_hub import hf_hub_download

                path = hf_hub_download(BGE_MODEL, "onnx/model.onnx", revision=BGE_REVISION)
                options = ort.SessionOptions()
                options.intra_op_num_threads = 2
                options.inter_op_num_threads = 1
                self._session = ort.InferenceSession(
                    path, sess_options=options, providers=["CPUExecutionProvider"]
                )
            except Exception:
                raise EmbeddingProviderError("LOCAL_EMBEDDING_MODEL_UNAVAILABLE") from None
        return self._session

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._validate(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                hidden = self._get_session().run(
                    ["last_hidden_state"], self.tokenizer.inputs(batch)
                )[0]
                vectors.extend(normalize_vectors(hidden[:, 0, :], len(batch)))
            except EmbeddingProviderError:
                raise
            except Exception:
                raise EmbeddingProviderError("LOCAL_EMBEDDING_INFERENCE_FAILED") from None
        return vectors

    def close(self) -> None:
        self._session = None


class APIEmbeddingProvider(_BGEProvider):
    kind = "api"

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        tokenizer: BGETokenizer | None = None,
        client: httpx.Client | None = None,
        batch_size: int = 8,
        timeout: float = 30,
    ) -> None:
        super().__init__(tokenizer, batch_size)
        self.url = url
        self._key = api_key
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._validate(texts)
        result: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            try:
                response = self._client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self._key}"},
                    json={"model": BGE_MODEL, "input": batch, "encoding_format": "float"},
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("model", BGE_MODEL) != BGE_MODEL:
                    raise ValueError
                rows = payload["data"]
                if not isinstance(rows, list) or len(rows) != len(batch):
                    raise ValueError
                ordered: dict[int, list[float]] = {}
                for row in rows:
                    index, embedding = row["index"], row["embedding"]
                    if (
                        type(index) is not int
                        or not 0 <= index < len(batch)
                        or index in ordered
                        or not isinstance(embedding, list)
                        or any(type(item) not in (int, float) for item in embedding)
                    ):
                        raise ValueError
                    ordered[index] = embedding
                result.extend(
                    normalize_vectors([ordered[i] for i in range(len(batch))], len(batch))
                )
            except Exception:
                # Do not propagate error bodies, request text, URLs, or Authorization headers.
                raise EmbeddingProviderError("EMBEDDING_API_FAILED") from None
        return result

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_model != BGE_MODEL:
        raise EmbeddingProviderError("UNSUPPORTED_EMBEDDING_MODEL")
    if settings.embedding_provider == "local":
        return LocalBGEProvider(batch_size=settings.embedding_batch_size)
    return APIEmbeddingProvider(
        url=settings.embedding_api_url,
        api_key=settings.embedding_api_key.get_secret_value(),
        batch_size=settings.embedding_batch_size,
        timeout=settings.embedding_timeout_seconds,
    )
