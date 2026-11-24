import asyncio
import multiprocessing
from io import BytesIO
from threading import Event, Lock
from time import sleep

import pytest

from app.services.indexing.upload import PDFUploadProcessor


def stalled_parser(connection, payload):
    connection.recv_bytes()
    sleep(60)


def test_cancelled_active_parser_is_joined_and_staging_and_stream_are_closed(monkeypatch, tmp_path):
    from app.services.ingestion.validation import PDFValidator

    finished = []
    monkeypatch.setattr("app.services.ingestion.sandbox._worker", stalled_parser)

    def prepare(settings, provider, source, **kwargs):
        with PDFValidator(temp_root=tmp_path).validate(source, filename="paper.pdf"):
            finished.append("must-not-embed")

    monkeypatch.setattr("app.services.indexing.upload.embed_stream", prepare)

    async def run():
        worker = PDFUploadProcessor()
        source = BytesIO(b"%PDF-1.7\nStaged test bytes")
        before = {child.pid for child in multiprocessing.active_children()}
        task = asyncio.create_task(
            worker.prepare(None, None, source, "paper.pdf", "application/pdf")
        )
        try:
            for _ in range(100):
                if list(tmp_path.iterdir()) and multiprocessing.active_children():
                    break
                await asyncio.sleep(0.02)
            else:
                pytest.fail("No active parser observed")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert source.closed
            assert list(tmp_path.iterdir()) == []
            assert {child.pid for child in multiprocessing.active_children()} == before
            assert finished == []
        finally:
            await asyncio.to_thread(worker.close)

    asyncio.run(run())


def test_concurrent_uploads_serialize_native_parsing_and_close_sources(monkeypatch):
    guard = Lock()
    active = 0
    peak = 0

    def prepare(*args, **kwargs):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        sleep(0.03)
        with guard:
            active -= 1
        return "prepared"

    monkeypatch.setattr("app.services.indexing.upload.embed_stream", prepare)

    async def run():
        worker = PDFUploadProcessor()
        sources = [BytesIO(b"pdf1"), BytesIO(b"pdf2")]
        try:
            results = await asyncio.gather(
                *[
                    worker.prepare(None, None, source, "paper.pdf", "application/pdf")
                    for source in sources
                ]
            )
            assert results == ["prepared", "prepared"]
            assert peak == 1
            assert all(source.closed for source in sources)
        finally:
            worker.close()

    asyncio.run(run())


def test_cancelled_queued_upload_closes_its_stream_without_parsing_it(monkeypatch):
    started, release = Event(), Event()
    calls = 0

    def prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(3)
        return "prepared"

    monkeypatch.setattr("app.services.indexing.upload.embed_stream", prepare)

    async def run():
        worker = PDFUploadProcessor()
        first, queued = BytesIO(b"one"), BytesIO(b"two")
        try:
            task = asyncio.create_task(
                worker.prepare(None, None, first, "one.pdf", "application/pdf")
            )
            assert await asyncio.to_thread(started.wait, 2)
            pending = asyncio.create_task(
                worker.prepare(None, None, queued, "two.pdf", "application/pdf")
            )
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert queued.closed
            release.set()
            assert await task == "prepared"
            assert first.closed and calls == 1
        finally:
            release.set()
            worker.close()

    asyncio.run(run())
