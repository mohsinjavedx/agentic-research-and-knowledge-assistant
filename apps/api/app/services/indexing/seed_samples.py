"""Verify and index the licensed Phase 3 sample corpus."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.providers.embeddings import create_embedding_provider
from app.services.indexing.processor import embed_pdf
from app.services.indexing.service import persist_document

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
SAMPLES_DIRECTORY = REPOSITORY_ROOT / "data" / "samples"
MANIFEST_PATH = SAMPLES_DIRECTORY / "manifest.json"


def _read_manifest() -> list[dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = manifest.get("documents")
    if manifest.get("version") != 1 or not isinstance(documents, list) or not documents:
        raise ValueError("Invalid sample corpus manifest.")

    for entry in documents:
        if entry.get("license") != "CC BY 4.0":
            raise ValueError("Every sample must record the approved CC BY 4.0 license.")
        file_path = SAMPLES_DIRECTORY / entry["file"]
        if file_path.parent != SAMPLES_DIRECTORY or not file_path.is_file():
            raise ValueError("A manifest PDF is missing or outside the sample directory.")
        checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if checksum != entry["sha256"]:
            raise ValueError(f"Sample checksum mismatch: {entry['file']}")
        entry["path"] = file_path
        entry["id"] = UUID(entry["document_id"])
    return documents


async def _seed() -> list[dict[str, Any]]:
    settings = load_settings()
    provider = create_embedding_provider(settings)
    database = Database(settings)
    outcomes: list[dict[str, Any]] = []
    try:
        await database.check()
        for entry in _read_manifest():
            async with database.sessions() as session:
                existing = await session.get(Document, entry["id"])
                if existing is not None:
                    if (
                        not existing.is_sample
                        or existing.checksum != entry["sha256"]
                        or existing.status != "ready"
                    ):
                        raise RuntimeError(
                            f"Sample document ID conflicts with existing data: {entry['id']}"
                        )
                    outcomes.append(
                        {
                            "document_id": str(existing.id),
                            "status": "already_indexed",
                            "filename": existing.filename,
                        }
                    )
                    continue

            embedded = embed_pdf(
                settings,
                provider,
                entry["path"],
                document_id=entry["id"],
            )
            document_id = await persist_document(
                database,
                embedded,
                filename=entry["path"].name,
                is_sample=True,
            )
            outcomes.append(
                {
                    "document_id": str(document_id),
                    "status": "indexed",
                    "filename": entry["path"].name,
                    "page_count": embedded.page_count,
                    "chunk_count": len(embedded.chunks),
                }
            )
    finally:
        provider.close()
        await database.close()
    return outcomes


def main() -> None:
    print(json.dumps(asyncio.run(_seed()), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
