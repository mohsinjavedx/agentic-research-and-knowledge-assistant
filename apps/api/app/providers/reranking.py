"""Optional, lazy quantized TinyBERT pair scoring on CPU, without PyTorch."""

import hashlib
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

import numpy as np
from tokenizers import Tokenizer

from app.core.config import Settings
from app.core.telemetry import begin_provider_call
from app.services.retrieval.dense import RetrievedChunk

RERANKER_MODEL = "Xenova/ms-marco-TinyBERT-L-2-v2"
RERANKER_REVISION = "b76bb5e1fefd66aa36cd108622d768e86c015ff1"
RERANKER_SHA256 = "026c2ec3257cd351696e45bbd6040bb83cf818ba89059b4344bd6350138b62ce"


class RerankerError(RuntimeError):
    """A stable, non-sensitive reason suitable for fallback metadata."""

    def __init__(self, error_code: str = "RERANKER_INFERENCE_FAILED") -> None:
        self.error_code = (
            error_code
            if error_code
            in {"RERANKER_UNAVAILABLE", "RERANKER_INFERENCE_FAILED", "RERANKER_INVALID_OUTPUT"}
            else "RERANKER_INFERENCE_FAILED"
        )
        super().__init__(self.error_code)


class Reranker(Protocol):
    def rerank(
        self, question: str, candidates: Sequence[RetrievedChunk]
    ) -> list[RetrievedChunk]: ...

    def close(self) -> None: ...


class TinyBERTReranker:
    """Serialize inference, batch four pairs, and bound pair length to 512 tokens."""

    def __init__(self) -> None:
        self._session: Any = None
        self._tokenizer: Tokenizer | None = None
        self._lock = Lock()

    def _load(self) -> None:
        if self._session is not None and self._tokenizer is not None:
            return
        try:
            import onnxruntime as ort
            from huggingface_hub import hf_hub_download

            model_path = hf_hub_download(
                RERANKER_MODEL, "onnx/model_quantized.onnx", revision=RERANKER_REVISION
            )
            if hashlib.sha256(Path(model_path).read_bytes()).hexdigest() != RERANKER_SHA256:
                raise ValueError("Unexpected model digest")
            tokenizer_path = hf_hub_download(
                RERANKER_MODEL, "tokenizer.json", revision=RERANKER_REVISION
            )
            tokenizer = Tokenizer.from_file(tokenizer_path)
            tokenizer.no_padding()
            tokenizer.enable_truncation(max_length=512, strategy="only_second")
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(
                model_path, sess_options=options, providers=["CPUExecutionProvider"]
            )
            self._tokenizer, self._session = tokenizer, session
        except Exception:
            raise RerankerError("RERANKER_UNAVAILABLE") from None

    def _scores(self, question: str, texts: list[str]) -> list[float]:
        assert self._tokenizer is not None
        encoded = self._tokenizer.encode_batch([(question, text) for text in texts])
        width = max(len(row.ids) for row in encoded)
        ids = np.zeros((len(texts), width), dtype=np.int64)
        masks, types = np.zeros_like(ids), np.zeros_like(ids)
        for index, row in enumerate(encoded):
            length = len(row.ids)
            ids[index, :length] = row.ids
            masks[index, :length] = row.attention_mask
            types[index, :length] = row.type_ids
        usage = begin_provider_call("local")
        logits = np.asarray(
            self._session.run(
                None, {"input_ids": ids, "attention_mask": masks, "token_type_ids": types}
            )[0]
        )
        usage.complete(int(masks.sum()))
        if logits.shape != (len(texts), 1) or not np.isfinite(logits).all():
            raise RerankerError("RERANKER_INVALID_OUTPUT")
        return [float(value) for value in logits[:, 0]]

    def rerank(self, question: str, candidates: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        if not candidates:
            return []
        if not question.strip() or len(candidates) > 20:
            raise RerankerError()
        try:
            with self._lock:
                self._load()
                scores = []
                for start in range(0, len(candidates), 4):
                    scores.extend(
                        self._scores(question, [row.text for row in candidates[start : start + 4]])
                    )
            # Python's stable sort retains retrieval order for equal logits.
            return sorted(
                [
                    replace(row, rerank_score=score)
                    for row, score in zip(candidates, scores, strict=True)
                ],
                key=lambda row: -float(row.rerank_score or 0),
            )
        except RerankerError:
            raise
        except Exception:
            raise RerankerError() from None

    def close(self) -> None:
        with self._lock:
            self._session = None
            self._tokenizer = None


def create_reranker(settings: Settings) -> Reranker | None:
    return TinyBERTReranker() if settings.enable_reranker else None
