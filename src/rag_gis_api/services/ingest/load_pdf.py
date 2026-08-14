from pathlib import Path

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_core.documents import Document


def load_pdf(path: Path) -> list[Document]:
    loader = PyPDFDirectoryLoader(
        str(path.parent),
        glob=path.name,
    )

    return loader.load()
