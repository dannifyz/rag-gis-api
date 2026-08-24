from pathlib import Path

from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.documents import Document

from rag_gis_api import DATA_PATH


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


def load_docx(path: Path) -> list[Document]:
    """
    Load a DOCX and return its text as a single Document.

    A DOCX has no pages to split on, so the whole body comes back as one
    Document; chunking happens later.
    """
    source = path.relative_to(DATA_PATH).as_posix()
    document = DocxDocument(str(path))

    content = "\n".join(iter_block_text(document))

    return [Document(page_content=content, metadata={"source": source})]
