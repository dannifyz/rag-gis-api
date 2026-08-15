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
# ฟอนต์ไทยรุ่นเก่า (Angsana, Cordia, Sarabun ฯลฯ) วาดสระและวรรณยุกต์ที่ต้องเลื่อน
# ตำแหน่งเป็น glyph ใน Private Use Area ตามผังกลางของ Microsoft แต่ ToUnicode ไม่
# map กลับ ทุกค่าในตารางนี้ decode จากบริบทจริงในคลัง
PUA_MAP = str.maketrans(
    {
        "\uf701": "\u0e34",  # ิ เช่น ปิโตรเคมี
        "\uf702": "\u0e35",  # ี เช่น ทั้งปี
        "\uf703": "\u0e36",  # ึ เช่น ฝึกอบรม
        "\uf704": "\u0e37",  # ื เช่น ฟื้นฟู
        "\uf710": "\u0e31",  # ั เช่น ฝังกลบ
        "\uf712": "\u0e47",  # ็ เช่น เป็น
        "\uf705": "\u0e48",  # ่ เช่น ผู้ป่วย
        "\uf70a": "\u0e48",  # ่ เช่น เล่ม
        "\uf713": "\u0e48",  # ่ เช่น ชายฝั่ง
        "\uf706": "\u0e49",  # ้ เช่น ไฟฟ้า
        "\uf70b": "\u0e49",  # ้ เช่น หน้า
        "\uf714": "\u0e49",  # ้ เช่น ปั้นดินเผา
        "\uf707": "\u0e4a",  # ๊ เช่น โป๊ะ
        "\uf70c": "\u0e4a",  # ๊ เช่น ก๊าซ
        "\uf708": "\u0e4b",  # ๋ เช่น ปุ๋ย
        "\uf709": "\u0e4c",  # ์ เช่น แสตมป์
        "\uf70e": "\u0e4c",  # ์ เช่น หลักเกณฑ์
    }
)

MIN_COMMON_WORDS = 2

CONSONANT = "\u0e01-\u0e2e"  # ก - ฮ
MARK = "\u0e31\u0e34-\u0e3a\u0e47-\u0e4e"  # สระและวรรณยุกต์
TONE = "\u0e48-\u0e4b"  # วรรณยุกต์

# ช่องว่างที่คั่นพยัญชนะกับสระบน/ล่าง ไม่ใช่ช่องว่างจริง เกิดจากการจัดวาง glyph
# 'นโยบายและแผนทร ัพยากรธรรมชาต'   →  'นโยบายและแผนทรัพยากรธรรมชาต'
SPLIT_MARK = re.compile(f"(?<=[{CONSONANT}{MARK}])[ \t]+(?=[{MARK}])")

# นิคหิตกับสระอาที่ควรรวมเป็น ำ อาจมีวรรณยุกต์หรือช่องว่างคั่น
#'อํานาจ'      →  'อำนาจ'
SPLIT_SARA_AM = re.compile(f"\u0e4d[ \t]*([{TONE}]?)[ \t]*\u0e32")

# นิคหิตที่หายไปเป็นช่องว่าง
#'ก าหนดเขตพื้นที่'   →  'กำหนดเขตพื้นที่'
LOST_NIKHAHIT = re.compile(f"([{CONSONANT}][{TONE}]?) [\u0e32\u0e33]")


def normalize_thai(text: str) -> str:
    """คืนข้อความที่ประกอบ ำ กลับ และแทน glyph PUA ด้วยอักขระไทยจริง"""
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
