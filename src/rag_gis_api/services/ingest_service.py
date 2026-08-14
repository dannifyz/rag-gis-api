from dataclasses import dataclass
from pathlib import Path

from rag_gis_api import DATA_PATH
from rag_gis_api.repositories import vector_repository
from rag_gis_api.services.ingest.calculate_hash import calculate_file_hash
from rag_gis_api.services.ingest.chunk_documents import chunk_documents
from rag_gis_api.services.ingest.compare_chunks import compare_chunks
from rag_gis_api.services.ingest.load_pdf import load_pdf


@dataclass
class IngestResult:
    source: str
    status: str  # "skipped" | "new" | "changed"
    inserted: int = 0
    updated: int = 0
    deleted: int = 0


def clear_vectorstore() -> int:
    """
    Delete every chunk in the vector store and return how many were removed.

    The next ingest then re-embeds everything from scratch.
    """
    removed = vector_repository.count_chunks()

    vector_repository.delete_all_chunks()

    return removed


def ingest_file(path: Path) -> IngestResult:
    """
    Sync one PDF into the vector store.

    The file is skipped when its hash matches the hash stored on its chunks.
    Otherwise only chunks that are new, changed, or gone are touched, so
    unchanged chunks are never re-embedded.
    """
    source = path.relative_to(DATA_PATH).as_posix()

    file_hash = calculate_file_hash(path)
    stored_file_hash = vector_repository.get_file_hash(source)

    if stored_file_hash == file_hash:
        return IngestResult(source=source, status="skipped")

    status = "new" if stored_file_hash is None else "changed"

    chunks = chunk_documents(load_pdf(path))

    for chunk in chunks:
        chunk.metadata["file_hash"] = file_hash

    diff = compare_chunks(chunks, vector_repository.get_chunk_hashes(source))

    vector_repository.delete_chunks(diff.to_delete_ids)
    vector_repository.save_chunks(diff.to_insert + diff.to_update)
    vector_repository.save_chunk_metadatas(diff.unchanged)

    return IngestResult(
        source=source,
        status=status,
        inserted=len(diff.to_insert),
        updated=len(diff.to_update),
        deleted=len(diff.to_delete_ids),
    )
