import asyncio
import os
from uuid import UUID, uuid4

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from app.api.v1.sessions import SESSION_COOKIE_NAME
from app.core.config import load_settings
from app.db.models import Document
from app.db.session import Database
from app.main import create_app
from app.providers.embeddings import BGETokenizer
from app.providers.identity import EmbeddingIdentity

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"),
]


class FixedEmbeddings:
    identity = EmbeddingIdentity()
    kind = "local"

    def __init__(self):
        engine = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
        engine.pre_tokenizer = Whitespace()
        self.tokenizer = BGETokenizer(engine)

    def embed_documents(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]

    def close(self):
        pass


def pdf_bytes(*, blank: bool = False) -> bytes:
    with pymupdf.open() as document:
        page = document.new_page()
        if not blank:
            page.insert_textbox(
                pymupdf.Rect(40, 40, 540, 700),
                "Research findings\n\n"
                + "Evidence connects a research question to its sources. " * 25,
            )
        return document.tobytes()


def test_upload_is_indexed_visible_only_to_its_session_and_can_be_deleted():
    settings = load_settings()
    document_id = None
    with TestClient(create_app(settings)) as client:
        client.app.state.embedding_provider = FixedEmbeddings()
        assert (
            client.post(
                "/api/v1/documents?filename=paper.pdf",
                content=pdf_bytes(),
                headers={"Content-Type": "application/pdf"},
            ).status_code
            == 401
        )
        assert client.post("/api/v1/session").status_code == 204
        owner = client.cookies.get(SESSION_COOKIE_NAME)
        try:
            response = client.post(
                "/api/v1/documents?filename=paper.pdf",
                content=pdf_bytes(),
                headers={"Content-Type": "application/pdf"},
            )
            assert response.status_code == 201
            uploaded = response.json()
            document_id = uploaded["document_id"]
            assert uploaded["page_count"] == 1 and uploaded["is_sample"] is False
            assert uploaded["status"] == "ready"
            listed = client.get("/api/v1/documents")
            assert listed.status_code == 200
            assert document_id in {row["document_id"] for row in listed.json()}
            client.cookies.clear()
            client.cookies.set(SESSION_COOKIE_NAME, str(uuid4()), path="/api/v1")
            assert document_id not in {
                row["document_id"] for row in client.get("/api/v1/documents").json()
            }
            assert client.delete(f"/api/v1/documents/{document_id}").status_code == 404
            client.cookies.clear()
            client.cookies.set(SESSION_COOKIE_NAME, owner, path="/api/v1")
            assert client.delete(f"/api/v1/documents/{document_id}").status_code == 204
        finally:
            if document_id:

                async def cleanup():
                    database = Database(settings)
                    try:
                        async with database.sessions() as session, session.begin():
                            await session.execute(
                                delete(Document).where(Document.id == UUID(document_id))
                            )
                    finally:
                        await database.close()

                asyncio.run(cleanup())


@pytest.mark.parametrize(
    "filename,content_type,content,expected,code",
    [
        ("scanned.pdf", "application/pdf", pdf_bytes(blank=True), 422, "OCR_NOT_SUPPORTED"),
        ("fake.pdf", "application/pdf", b"not a pdf", 415, "INVALID_PDF_SIGNATURE"),
        ("../paper.pdf", "application/pdf", b"%PDF-x", 400, "INVALID_FILENAME"),
        ("paper.pdf", "text/plain", b"%PDF-x", 415, "UNSUPPORTED_MEDIA_TYPE"),
        ("large.pdf", "application/pdf", b"%PDF-" + b"x" * (1024 * 1024), 413, "FILE_TOO_LARGE"),
    ],
)
def test_upload_returns_actionable_stable_errors(filename, content_type, content, expected, code):
    settings = load_settings().model_copy(update={"max_upload_mb": 1})
    with TestClient(create_app(settings)) as client:
        client.app.state.embedding_provider = FixedEmbeddings()
        client.post("/api/v1/session")
        response = client.post(
            "/api/v1/documents",
            params={"filename": filename},
            content=content,
            headers={"Content-Type": content_type},
        )
        assert response.status_code == expected
        assert response.json()["detail"]["code"] == code
