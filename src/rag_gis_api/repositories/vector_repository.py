from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document

from rag_gis_api.database.vectorstore import vectorstore


def get_file_hash(source: str) -> str | None:
    """
    Return the file hash stored on the chunks of this source.

    None = the file has never been ingested.
    """
    result = vectorstore.get(where={"source": source}, limit=1, include=["metadatas"])
    metadatas = result["metadatas"]

    if not metadatas:
        return None

    return metadatas[0].get("file_hash")


def get_chunk_hashes(source: str) -> dict[str, str]:
    """Return {chunk_id: content_hash} for every stored chunk of this source."""
    result = vectorstore.get(where={"source": source}, include=["metadatas"])

    return {
        chunk_id: metadata["content_hash"]
        for chunk_id, metadata in zip(result["ids"], result["metadatas"], strict=True)
    }


def get_chunks(source: str) -> list[Document]:
    """
    Return every stored chunk of this source, ordered by page then chunk index.

    Chroma does not guarantee an order, so the chunks are sorted here.
    """
    result = vectorstore.get(
        where={"source": source}, include=["documents", "metadatas"]
    )

    chunks = [
        Document(id=chunk_id, page_content=content, metadata=metadata)
        for chunk_id, content, metadata in zip(
            result["ids"], result["documents"], result["metadatas"], strict=True
        )
    ]

    return sorted(
        chunks,
        key=lambda chunk: (chunk.metadata["page"], chunk.metadata["chunk_index"]),
    )


async def search_chunks(question: str, limit: int) -> list[Document]:
    """
    Return the stored chunks most similar to the question, best match first.

    Async because embedding the question is a network call: the sync version
    would block the event loop and stall every other request for its duration.
    """
    return await vectorstore.asimilarity_search(question, k=limit)


def save_chunks(chunks: list[Document]) -> None:
    """Embed and store chunks. Chroma upserts, so this also replaces old vectors."""
    if not chunks:
        return

    ids = [chunk.metadata["id"] for chunk in chunks]

    # Chroma only accepts scalar metadata values.
    vectorstore.add_documents(documents=filter_complex_metadata(chunks), ids=ids)


def save_chunk_metadatas(chunks: list[Document]) -> None:
    """
    Overwrite metadata of stored chunks without re-embedding them.

    Used to refresh file_hash on chunks whose text did not change, so every
    chunk of a source keeps reporting the same file hash.
    """
    if not chunks:
        return

    ids = [chunk.metadata["id"] for chunk in chunks]

    # langchain's update_documents() re-embeds; the raw collection does not.
    vectorstore._collection.update(
        ids=ids,
        metadatas=[chunk.metadata for chunk in filter_complex_metadata(chunks)],
    )


def delete_chunks(chunk_ids: list[str]) -> None:
    if not chunk_ids:
        return

    vectorstore.delete(ids=chunk_ids)


def count_chunks() -> int:
    """Return how many chunks are stored in the collection."""
    return len(vectorstore.get(include=[])["ids"])


def delete_all_chunks() -> None:
    """Drop the collection and recreate it empty."""
    vectorstore.reset_collection()
