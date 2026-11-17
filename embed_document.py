from typing import Protocol

import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalBGEProvider:
    model_name = "BAAI/bge-small-en-v1.5"
    dimension = 384

    def __init__(self):
        # Load once and reuse for all chunks.
        self.model = SentenceTransformer(
            self.model_name,
            revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
            device="cpu",
        )

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # Count with the embedding model's tokenizer.
        encoded = self.model.tokenizer(
            texts,
            add_special_tokens=True,
            truncation=False,
            padding=False,
        )

        limit = min(512, self.model.max_seq_length)

        for index, token_ids in enumerate(encoded["input_ids"]):
            if len(token_ids) > limit:
                raise ValueError(
                    f"Input {index} has {len(token_ids)} model tokens; "
                    f"limit is {limit}. Split it before embedding."
                )

        # This is where text becomes numerical vectors.
        vectors = self.model.encode(
            texts,
            batch_size=8,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        if vectors.shape != (len(texts), self.dimension):
            raise ValueError("Unexpected embedding dimensions")

        if not np.isfinite(vectors).all():
            raise ValueError("Embeddings contain NaN or infinity")

        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Document passages do not need a query instruction.
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        instruction = "Represent this sentence for searching relevant passages: "
        return self._encode([instruction + text])[0]