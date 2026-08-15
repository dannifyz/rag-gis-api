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


COMMON_THAI_WORDS = (
    "ที่",
    "การ",
    "และ",
    "ของ",
    "ให้",
    "ใน",
    "เป็น",
    "พ.ศ",
    "ประกาศ",
    "มาตรา",
    "ข้อ",
    "ความ",
    "หรือ",
)
# Legacy Thai fonts (Angsana, Cordia, Sarabun and the like) draw the vowel and
# tone marks that have to shift position as glyphs in the Private Use Area,
# following Microsoft's shared layout, and their ToUnicode maps nothing back.
# Every entry below was read off real pages in the corpus.
PUA_MAP = str.maketrans(
    {
        "\uf701": "\u0e34",  # ิ as in ปิโตรเคมี
        "\uf702": "\u0e35",  # ี as in ทั้งปี
        "\uf703": "\u0e36",  # ึ as in ฝึกอบรม
        "\uf704": "\u0e37",  # ื as in ฟื้นฟู
        "\uf710": "\u0e31",  # ั as in ฝังกลบ
        "\uf712": "\u0e47",  # ็ as in เป็น
        "\uf705": "\u0e48",  # ่ as in ผู้ป่วย
        "\uf70a": "\u0e48",  # ่ as in เล่ม
        "\uf713": "\u0e48",  # ่ as in ชายฝั่ง
        "\uf706": "\u0e49",  # ้ as in ไฟฟ้า
        "\uf70b": "\u0e49",  # ้ as in หน้า
        "\uf714": "\u0e49",  # ้ as in ปั้นดินเผา
        "\uf707": "\u0e4a",  # ๊ as in โป๊ะ
        "\uf70c": "\u0e4a",  # ๊ as in ก๊าซ
        "\uf708": "\u0e4b",  # ๋ as in ปุ๋ย
        "\uf709": "\u0e4c",  # ์ as in แสตมป์
        "\uf70e": "\u0e4c",  # ์ as in หลักเกณฑ์
    }
)

MIN_COMMON_WORDS = 2

CONSONANT = "\u0e01-\u0e2e"  # ก - ฮ
MARK = "\u0e31\u0e34-\u0e3a\u0e47-\u0e4e"  # vowel and tone marks
TONE = "\u0e48-\u0e4b"  # tone marks

# A space between a consonant and the mark that sits above or below it is not
# a space in the text, it comes from how the glyphs were laid out.
# 'นโยบายและแผนทร ัพยากรธรรมชาต'   →  'นโยบายและแผนทรัพยากรธรรมชาต'
SPLIT_MARK = re.compile(f"(?<=[{CONSONANT}{MARK}])[ \t]+(?=[{MARK}])")

# นิคหิต and สระอา that should have come back as ำ, sometimes with a tone
# mark or a space between them.
#'อํานาจ'      →  'อำนาจ'
SPLIT_SARA_AM = re.compile(f"\u0e4d[ \t]*([{TONE}]?)[ \t]*\u0e32")

# นิคหิต that came back as a space.
#'ก าหนดเขตพื้นที่'   →  'กำหนดเขตพื้นที่'
LOST_NIKHAHIT = re.compile(f"([{CONSONANT}][{TONE}]?) [\u0e32\u0e33]")


def normalize_thai(text: str) -> str:
    """Put ำ back together and swap PUA glyphs for real Thai characters."""
    text = text.translate(PUA_MAP)
    text = SPLIT_MARK.sub("", text)
    text = SPLIT_SARA_AM.sub(lambda m: m.group(1) + "\u0e33", text)

    return LOST_NIKHAHIT.sub(lambda m: m.group(1) + "\u0e33", text)


def is_junk(character: str) -> bool:
    """Tell whether a character is a decoding failure rather than text."""
    return character == "�" or unicodedata.category(character) in ("Cc", "Co")


def is_readable(text: str) -> bool:
    """
    Tell whether PyPDF made sense of a page.

    A page has to hold enough text, decode without leftover control bytes or
    unmapped glyphs, and read as Thai prose. Anything else goes to OCR: losing
    a good page there costs less than letting a garbled one reach the store.
    """
    stripped = text.strip()

    if len(stripped) < MIN_READABLE_CHARS:
        return False

    if CID_PATTERN.search(stripped):
        return False

    if any(is_junk(character) for character in stripped if not character.isspace()):
        return False

    found = sum(1 for word in COMMON_THAI_WORDS if word in stripped)
    return found >= MIN_COMMON_WORDS


async def read_pages(path: Path, ocr_queue: asyncio.Queue[Document]) -> list[Document]:
    """
    Read a PDF page by page and return every page in order.

    Pages PyPDF could not read also go on `ocr_queue`, so OCR can fill them in
    while the next pages are still being read.
    """
    loader = PyPDFLoader(str(path))
    pages = loader.lazy_load()

    documents = []

    while True:
        # lazy_load() parses on each step, so keep that off the event loop.
        page = await asyncio.to_thread(next, pages, None)

        if page is None:
            break

        page.page_content = normalize_thai(page.page_content)
        documents.append(page)
        if not is_readable(page.page_content):
            await ocr_queue.put(page)

    return documents


async def read_pages_with_ocr(path: Path) -> list[Document]:
    """Read a PDF, running OCR alongside, and return the pages that hold text."""
    ocr_queue: asyncio.Queue[Document] = asyncio.Queue()
    ocr_task = asyncio.create_task(consume_ocr_queue(ocr_queue))

    try:
        documents = await read_pages(path, ocr_queue)

        # OCR runs behind the reader, so give it the pages left in the queue.
        await ocr_queue.join()
    finally:
        ocr_task.cancel()

    return [page for page in documents if page.page_content]


def load_pdf(path: Path) -> list[Document]:
    """
    Load a PDF and return its readable pages.

    Callers stay synchronous: the page reader and the OCR worker run
    concurrently inside, and this returns once both are done.
    """
    return asyncio.run(read_pages_with_ocr(path))
