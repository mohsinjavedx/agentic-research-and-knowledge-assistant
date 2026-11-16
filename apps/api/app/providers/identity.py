"""Lightweight embedding-space identity shared by inference and database checks."""

from dataclasses import dataclass

BGE_MODEL = "BAAI/bge-small-en-v1.5"
BGE_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EMBEDDING_DIMENSION = 384


@dataclass(frozen=True)
class EmbeddingIdentity:
    model: str = BGE_MODEL
    revision: str = BGE_REVISION
    dimension: int = EMBEDDING_DIMENSION


class EmbeddingCompatibilityError(RuntimeError):
    """A configuration/index mismatch must fail startup, not be treated as an outage."""
