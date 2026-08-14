from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_core.documents import Document

from pathlib import Path


def load_pdf(path: Path) -> list[Document]:
    loader = PyPDFDirectoryLoader(
        str(path.parent),
        glob=path.name,
    )

    return loader.load()
