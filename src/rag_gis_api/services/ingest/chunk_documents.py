from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_gis_api.services.ingest.calculate_chunk_metadatas import (
    calculate_chunk_metadatas,
)


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_documents(documents: list[Document]) -> list[Document]:
    """Split loaded pages into chunks, each carrying its ingest metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    return calculate_chunk_metadatas(splitter.split_documents(documents))
