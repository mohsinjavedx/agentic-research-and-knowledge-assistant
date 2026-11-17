from pathlib import Path

from app.services.chunking.splitter import MarkdownChunker
from app.services.ingestion.pipeline import PDFIngestionService

from embed_document import EmbeddingProvider, LocalBGEProvider

# Smaller windows for this example.
# The provider still checks actual model-token lengths.
service = PDFIngestionService(
    chunker=MarkdownChunker(
        min_tokens=200,
        max_tokens=300,
        overlap_tokens=40,
    )
)

pdf_path = Path(r"D:\cover letter.pdf")
with pdf_path.open("rb") as pdf:
    prepared = service.prepare(pdf, filename=pdf_path.name)

# 1. Obtain the chunks created by Phase 1.
chunks = prepared.chunks

# 2. Take their normalized text for embedding.
texts = [chunk.normalized_text for chunk in chunks]

# 3. Generate one vector per chunk.
provider: EmbeddingProvider = LocalBGEProvider()
vectors = provider.embed_documents(texts)

# 4. Associate every vector with its original chunk and provenance.
records = [
    {
        **chunk.model_dump(),
        "embedding": vector,
    }
    for chunk, vector in zip(chunks, vectors, strict=True)
]

print("Number of chunks:", len(records))
print("First chunk:", records[0]["normalized_text"])
print("Vector dimensions:", len(records[0]["embedding"]))  # 384
print("First eight values:", records[0]["embedding"][:8])

# Later, retrieval will embed the question with the same model.
question_vector = provider.embed_query(
    "What limitations did the researchers identify?"
)
