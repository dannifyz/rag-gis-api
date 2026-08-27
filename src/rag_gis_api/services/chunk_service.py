from pathlib import Path

from rag_gis_api.repositories import document_repository, vector_repository


def clear_vectorstore() -> int:
    """
    Delete every chunk in the vector store and return how many were removed.

    The next ingest then re-embeds everything from scratch.
    """
    removed = vector_repository.count_chunks()

    vector_repository.delete_all_chunks()

    return removed


def _is_under(source: str, prefix: str) -> bool:
    """True when source is the prefix path itself or sits under that folder."""
    return source == prefix or source.startswith(f"{prefix}/")


def clear_chunks(path: str | None = None) -> tuple[int, int]:
    """Delete stored chunks and invalidate their page cache."""
    if path is None:
        return clear_vectorstore(), document_repository.clear_cache()

    prefix = Path(path).as_posix()

    removed_chunks = sum(
        vector_repository.delete_chunks_by_source(source)
        for source in vector_repository.get_sources()
        if _is_under(source, prefix)
    )
    removed_pages = sum(
        document_repository.clear_cache_for(source)
        for source in document_repository.get_cached_sources()
        if _is_under(source, prefix)
    )

    return removed_chunks, removed_pages
