import asyncio
import re
import unicodedata
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from rag_gis_api.services.ingest.ocr import consume_ocr_queue

# A page shorter than this holds no usable text: a scanned page usually comes
# back empty, or with just a stray header PyPDF managed to decode.
MIN_READABLE_CHARS = 30

# PyPDF writes these when a font carries no usable encoding, so the text is
# there but unreadable.
CID_PATTERN = re.compile(r"\(cid:\d+\)")

# Share of the visible characters allowed to be control bytes or replacement
# characters. Pages PyPDF decoded with the wrong font encoding sit well above
# this (0.11 and up in documents/), readable pages sit at 0.00.
MAX_JUNK_RATIO = 0.02

# The corpus is Thai law, so a page with next to no Thai letter came out of the
# wrong code page, e.g. Thai read as Latin-1 ("Àπâ“ 39 √“™°‘®®“πÿ") or left as
# glyph names ("/afii59723;"). Mis-decoded pages sit at 0.01 and below, while
# the most Latin-heavy readable pages, the tables of species names, still reach
# 0.48.
MIN_THAI_LETTER_RATIO = 0.15

# Below this a page is a table of numbers or a form, not prose, so the Thai
# check has too little to go on and is skipped.
MIN_LETTERS_FOR_THAI_CHECK = 20


def is_junk(character: str) -> bool:
    """Tell whether a character is a decoding failure rather than text."""
    return character == "�" or unicodedata.category(character) == "Cc"


def is_thai(character: str) -> bool:
    return "฀" <= character <= "๿"


def is_readable(text: str) -> bool:
    """
    Tell whether PyPDF made sense of a page.

    A page fails when it holds (almost) no text, when its glyphs came back as
    "(cid:NN)" placeholders, when too much of it is control bytes, or when its
    letters are not Thai. Those are the pages OCR has to redo.
    """
    stripped = text.strip()

    if len(stripped) < MIN_READABLE_CHARS:
        return False

    if CID_PATTERN.search(stripped):
        return False

    visible = [character for character in stripped if not character.isspace()]

    if not visible:
        return False

    junk = sum(1 for character in visible if is_junk(character))

    if junk / len(visible) > MAX_JUNK_RATIO:
        return False

    letters = [character for character in visible if character.isalpha()]

    if len(letters) < MIN_LETTERS_FOR_THAI_CHECK:
        return True

    thai = sum(1 for character in letters if is_thai(character))

    return thai / len(letters) >= MIN_THAI_LETTER_RATIO


async def read_pages(path: Path, ocr_queue: asyncio.Queue[Document]) -> list[Document]:
    """
    Read a PDF page by page and return the pages PyPDF made sense of.

    Every other page goes on `ocr_queue`, so OCR can pick it up while the next
    pages are still being read.
    """
    loader = PyPDFLoader(str(path))
    pages = loader.lazy_load()

    documents = []

    while True:
        # lazy_load() parses on each step, so keep that off the event loop.
        page = await asyncio.to_thread(next, pages, None)

        if page is None:
            break

        if is_readable(page.page_content):
            documents.append(page)
        else:
            await ocr_queue.put(page)

    return documents


async def read_pages_with_ocr(path: Path) -> list[Document]:
    """Read a PDF, running OCR alongside, and wait for both to finish."""
    ocr_queue: asyncio.Queue[Document] = asyncio.Queue()
    ocr_task = asyncio.create_task(consume_ocr_queue(ocr_queue))

    try:
        documents = await read_pages(path, ocr_queue)

        # OCR runs behind the reader, so give it the pages left in the queue.
        await ocr_queue.join()
    finally:
        ocr_task.cancel()

    return documents


def load_pdf(path: Path) -> list[Document]:
    """
    Load a PDF and return its readable pages.

    Callers stay synchronous: the page reader and the OCR worker run
    concurrently inside, and this returns once both are done.
    """
    return asyncio.run(read_pages_with_ocr(path))
