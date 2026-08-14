from langchain_core.documents import Document


def list_sources(chunks: list[Document]) -> list[dict[str, object]]:
    """
    Collapse the retrieved chunks into one entry per file with its page numbers.

    Several chunks usually come from the same file, and the client only needs to
    know which document and page an answer came from. Files stay in relevance
    order; pages are sorted so the citation reads naturally.
    """
    pages: dict[str, set[int]] = {}

    for chunk in chunks:
        pages.setdefault(chunk.metadata["source"], set()).add(chunk.metadata["page"])

    return [
        {"source": source, "pages": sorted(page_numbers)}
        for source, page_numbers in pages.items()
    ]
