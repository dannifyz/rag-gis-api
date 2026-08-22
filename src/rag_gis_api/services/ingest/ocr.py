import asyncio
import io
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import pypdfium2
from langchain_core.documents import Document
from PIL import Image, ImageChops

from rag_gis_api import TYPHOON_API_KEY

MODEL = "typhoon-ocr"

# Plain text back, rather than a structured layout the caller would have to parse.
TASK_TYPE = "default"

MAX_TOKEN = 8192

# Only the likeliest tokens adding up to this share stay in play
TOP_P = 0.6

# OCR wants the same page to read the same way every time, so sampling stays
# close to deterministic.
TEMPERATURE = 0.1

# A vision model that loses its place tends to repeat a line forever
REPETITION_PENALTY = 1.2

# Typhoon's OCR endpoint and the model that serves it.
URL = "https://api.opentyphoon.ai/v1/ocr"

# The scans in this corpus sit at 400 DPI, so rendering a little above that
# keeps the tone marks crisp without inventing detail the original never held.
RENDER_DPI = 400

# A fold-out map page renders far larger than the A4 scans RENDER_DPI was
# picked for, and at 400 DPI one runs to hundreds of megapixels. Capping the
# longest edge keeps that off the heap before anything is encoded.
MAX_EDGE_PIXELS = 4000

# The endpoint's proxy rejects anything larger with HTTP 413.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024

# Below this the tone marks are gone and OCR has nothing left to read, so a
# page that still will not fit has to fail rather than shrink further.
MIN_EDGE_PIXELS = 1000

# A dense scan takes the vision model a while, so the timeout is generous.
TIMEOUT = 120


class OcrError(Exception):
    """OCR could not read a page. Not the same as a page that holds no text."""


@dataclass
class OcrFailure:
    """A page OCR could not read, kept so the caller can fail the whole file."""

    source: str
    page: int
    error: str


def has_colour(image: Image.Image) -> bool:
    """Tell whether the page holds colour worth keeping."""
    red, green, blue = image.convert("RGB").split()
    spread = ImageChops.lighter(
        ImageChops.difference(red, green), ImageChops.difference(green, blue)
    )

    # Anything closer than this is scanner noise on a page of ink, not colour.
    return spread.getextrema()[1] > 8


def encode(image: Image.Image) -> bytes:
    """
    Encode a page for upload.

    A scan of ink on paper repeats itself across all three channels, so
    grayscale halves the upload and changes nothing. A zoning map, where the
    colours carry the meaning, keeps them.
    """
    if not has_colour(image):
        image = image.convert("L")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)

    return buffer.getvalue()


def shrink_to_fit(image: Image.Image) -> bytes:
    """Encode the page, shrinking it until the upload fits within the limit."""
    data = encode(image)

    while len(data) > MAX_UPLOAD_BYTES:
        # A fifth off each edge, because resampling a scan adds antialiased
        # grey that PNG cannot pack, and a smaller step comes back larger than
        # it started.
        size = (int(image.width * 0.8), int(image.height * 0.8))

        if max(size) < MIN_EDGE_PIXELS:
            raise OcrError(
                f"the page is still {len(data) / 1048576:.1f} MB at {max(image.size)} px"
            )

        image = image.resize(size, Image.LANCZOS)
        data = encode(image)

    return data


def render_page(path: Path, page_number: int) -> bytes:
    """Render the page PyPDF could not read as a PNG for OCR to pick up."""
    document = pypdfium2.PdfDocument(path)

    try:
        page = document[page_number]
        scale = RENDER_DPI / 72
        longest = max(page.get_width(), page.get_height()) * scale

        if longest > MAX_EDGE_PIXELS:
            scale *= MAX_EDGE_PIXELS / longest

        image = page.render(scale=scale).to_pil()
    finally:
        document.close()

    return shrink_to_fit(image)


def read_content(message: dict) -> str:
    """Pull the text out of one OCR result."""
    content = message["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content

    return parsed.get("natural_text", content) if isinstance(parsed, dict) else content


async def extract_text_from_image(image: bytes) -> str:
    """Send one rendered page to Typhoon OCR and return the text it read."""
    files = {"file": ("page.png", image, "image/png")}

    data = {
        "model": MODEL,
        "task_type": TASK_TYPE,
        "max_tokens": str(MAX_TOKEN),
        "temperature": str(TEMPERATURE),
        "top_p": str(TOP_P),
        "repetition_penalty": str(REPETITION_PENALTY),
    }

    headers = {"Authorization": f"Bearer {TYPHOON_API_KEY}"}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(URL, files=files, data=data, headers=headers)

    if response.status_code != 200:
        raise OcrError(f"HTTP {response.status_code}: {response.text[:200]}")

    results = response.json().get("results", [])

    if not results:
        raise OcrError("the service returned no result for this page")

    contents, errors = [], []

    for result in results:
        if result.get("success") and result.get("message"):
            contents.append(read_content(result["message"]))
        else:
            errors.append(result.get("error", "unknown error"))

    if errors:
        raise OcrError("; ".join(errors))

    return "\n".join(contents).strip()


async def consume_ocr_queue(
    ocr_queue: asyncio.Queue[Document],
    failures: list[OcrFailure],
) -> None:
    """Fill in the pages PyPDF could not read, one at a time."""
    while True:
        page = await ocr_queue.get()
        source = page.metadata["source"]
        page_number = page.metadata["page"]

        try:
            # Rendering is CPU-bound, so it goes off the event loop as well.
            image = await asyncio.to_thread(render_page, source, page_number)
            page.page_content = await extract_text_from_image(image)

            read = f"{len(page.page_content)} chars" if page.page_content else "no text"

            print(f"OCR:  {source} page {page_number} ({read})")
        except Exception as error:
            failures.append(
                OcrFailure(
                    source=source,
                    page=page_number,
                    error=f"{type(error).__name__}: {error}",
                )
            )
        finally:
            ocr_queue.task_done()
