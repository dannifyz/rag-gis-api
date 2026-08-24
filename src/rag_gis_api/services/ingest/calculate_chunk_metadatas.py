from langchain_core.documents import Document

from rag_gis_api.services.ingest.calculate_hash import calculate_content_hash


def calculate_chunk_metadatas(chunks: list[Document]) -> list[Document]:
    """
    Add the metadata the ingest pipeline relies on:

        id           {source}:{page}:{chunk_index}, e.g. law/act/law_001.pdf:6:2
        source       path relative to DATA_PATH
        page         page number from the loader
        chunk_index  index of the chunk within its page
        content_hash hash of the chunk text, used to detect changes
    """
    last_page_id = None
    chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        page_id = f"{source}:{page}"

        chunk_index = chunk_index + 1 if page_id == last_page_id else 0

        chunk.metadata["chunk_index"] = chunk_index
        chunk.metadata["id"] = f"{page_id}:{chunk_index}"
        chunk.metadata["content_hash"] = calculate_content_hash(chunk.page_content)

        last_page_id = page_id

    return chunks
