from pathlib import Path

from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.documents import Document

from rag_gis_api import DATA_PATH
from rag_gis_api.repositories import document_repository
from rag_gis_api.repositories.document_repository import PageState
from rag_gis_api.services.ingest.calculate_hash import calculate_file_hash

# A DOCX has no pages, so the whole file is stored as this single page.
DOCX_PAGE = 0


def iter_block_text(document: DocxDocumentType) -> list[str]:
    """
    Read paragraphs and tables in the order they appear in the document.

    python-docx exposes paragraphs and tables as separate collections, so walk
    the body's child elements to keep a table sitting between two paragraphs in
    its place rather than pushing every table to the end.
    """
    body = document.element.body
    lines = []

    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            text = Paragraph(child, document).text.strip()

            if text:
                lines.append(text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, document).rows:
                cells = [cell.text.strip() for cell in row.cells]
                line = " | ".join(cell for cell in cells if cell)

                if line:
                    lines.append(line)

    return lines


def extract_text(path: Path, source: str, file_hash: str) -> str:
    """
    Return the DOCX text, reusing the cached extraction when the file is unchanged.

    The whole file is cached as page 0, keyed by the file hash. A later run of
    an unchanged file reads the text back instead of parsing the DOCX again.
    """
    cached = document_repository.get_page_state(source, DOCX_PAGE)

    if (
        cached is not None
        and cached.page_hash == file_hash
        and cached.status == document_repository.SUCCESS
    ):
        print(f"{source} (Cached)")
        return cached.extracted_text

    content = "\n".join(iter_block_text(DocxDocument(str(path))))

    document_repository.save_page_state(
        PageState(
            source=source,
            page_number=DOCX_PAGE,
            page_hash=file_hash,
            extraction_method=document_repository.DOCX,
            extracted_text=content,
            status=document_repository.SUCCESS,
        )
    )

    return content


def load_docx(path: Path) -> list[Document]:
    """
    Load a DOCX and return its text as a single Document.

    A DOCX has no pages to split on, so the whole body comes back as one
    Document; chunking happens later.
    """
    source = path.relative_to(DATA_PATH).as_posix()
    content = extract_text(path, source, calculate_file_hash(path))

    return [Document(page_content=content, metadata={"source": source, "page": DOCX_PAGE})]
