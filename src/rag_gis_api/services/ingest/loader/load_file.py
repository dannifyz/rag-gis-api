from pathlib import Path

from langchain_core.documents import Document

from rag_gis_api.services.ingest.loader.load_docx import load_docx
from rag_gis_api.services.ingest.loader.load_pdf import load_pdf

# Extensions load_file knows how to read.
SUPPORTED_SUFFIXES = (".pdf", ".docx")


class UnsupportedFileError(Exception):
    """The file has an extension no loader handles."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"no loader for '{path.suffix}' files: {path}")


def load_file(path: Path) -> list[Document]:
    """Load a file into Documents, picking the loader by its extension."""
    match path.suffix.lower():
        case ".pdf":
            return load_pdf(path)
        case ".docx":
            return load_docx(path)
        case _:
            raise UnsupportedFileError(path)
