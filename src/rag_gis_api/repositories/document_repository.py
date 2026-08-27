import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from rag_gis_api import PROJECT_ROOT

# A page-level cache of what each page's text extraction produced
DB_PATH = PROJECT_ROOT / "document_cache.db"

# status values
SUCCESS = "SUCCESS"
FAILED = "FAILED"

# extraction_method values
PYPDF = "PYPDF"
OCR = "OCR"
DOCX = "DOCX"


@dataclass
class PageState:
    """One page's extraction result, as stored in the document_page table."""

    source: str
    page_number: int
    page_hash: str
    extraction_method: str  # PYPDF | OCR | DOCX
    extracted_text: str | None  # NULL when the page failed
    status: str  # SUCCESS | FAILED


@contextmanager
def _connect() -> Generator[sqlite3.Connection]:
    """Open a connection for one operation, commit on success, always close.

    A fresh connection per call keeps the OCR worker threads from sharing one
    connection (sqlite3 connections aren't safe to share across threads).
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _init_db() -> None:
    with _connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_page (
                source            TEXT    NOT NULL,
                page_number       INTEGER NOT NULL,
                page_hash         TEXT    NOT NULL,
                extraction_method TEXT    NOT NULL,
                extracted_text    TEXT,
                status            TEXT    NOT NULL,
                PRIMARY KEY (source, page_number)
            )
            """
        )


_init_db()


def get_page_state(source: str, page_number: int) -> PageState | None:
    """Return the stored state of this page, or None if it was never read."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM document_page WHERE source = ? AND page_number = ?",
            (source, page_number),
        ).fetchone()

    if row is None:
        return None

    return PageState(
        source=row["source"],
        page_number=row["page_number"],
        page_hash=row["page_hash"],
        extraction_method=row["extraction_method"],
        extracted_text=row["extracted_text"],
        status=row["status"],
    )


def count_pages() -> int:
    """Return how many pages are cached across all documents."""
    with _connect() as connection:
        return connection.execute("SELECT COUNT(*) FROM document_page").fetchone()[0]


def clear_cache() -> int:
    """Delete every cached page and return how many were removed.

    The next ingest then re-extracts every page instead of reusing stale text.
    """
    removed = count_pages()

    with _connect() as connection:
        connection.execute("DELETE FROM document_page")

    return removed


def get_cached_sources() -> list[str]:
    """Return every distinct source that has cached pages."""
    with _connect() as connection:
        rows = connection.execute("SELECT DISTINCT source FROM document_page").fetchall()

    return sorted(row["source"] for row in rows)


def clear_cache_for(source: str) -> int:
    """Delete the cached pages of one source and return how many were removed."""
    with _connect() as connection:
        removed = connection.execute(
            "SELECT COUNT(*) FROM document_page WHERE source = ?", (source,)
        ).fetchone()[0]
        connection.execute("DELETE FROM document_page WHERE source = ?", (source,))

    return removed


def save_page_state(state: PageState) -> None:
    """Insert this page's state, or overwrite the row already there for it."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO document_page
                (source, page_number, page_hash, extraction_method, extracted_text, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (source, page_number) DO UPDATE SET
                page_hash         = excluded.page_hash,
                extraction_method = excluded.extraction_method,
                extracted_text    = excluded.extracted_text,
                status            = excluded.status
            """,
            (
                state.source,
                state.page_number,
                state.page_hash,
                state.extraction_method,
                state.extracted_text,
                state.status,
            ),
        )
