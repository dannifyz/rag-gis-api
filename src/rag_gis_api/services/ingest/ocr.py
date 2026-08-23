import asyncio
import io
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import pypdfium2
from langchain_core.documents import Document

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

# The scans in this corpus sit at 300 DPI, so rendering a little above that
# keeps the tone marks crisp without inventing detail the original never held.
RENDER_DPI = 400

# A dense scan takes the vision model a while, so the timeout is generous.
TIMEOUT = 120

# OCR is network-bound, so several pages can be in flight at once.
OCR_CONCURRENCY = 4


class OcrError(Exception):
    """OCR could not read a page. Not the same as a page that holds no text."""


@dataclass
class OcrFailure:
    """A page OCR could not read, kept so the caller can fail the whole file."""

    source: str
    page: int
    error: str


def render_page(path: Path, page_number: int) -> bytes:
    """Render the page PyPDF could not read as a PNG for OCR to pick up."""
    document = pypdfium2.PdfDocument(path)

    try:
        image = document[page_number].render(scale=RENDER_DPI / 72).to_pil()
    finally:
        document.close()

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)

    return buffer.getvalue()


def read_content(message: dict) -> str:
    """Pull the text out of one OCR result."""
    content = message["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content

    return parsed.get("natural_text", content) if isinstance(parsed, dict) else content


async def extract_text_from_image(client: httpx.AsyncClient, image: bytes) -> str:
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


async def _ocr_worker(
    client: httpx.AsyncClient,
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
            page.page_content = await extract_text_from_image(client, image)

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


async def consume_ocr_queue(
    ocr_queue: asyncio.Queue[Document],
    failures: list[OcrFailure],
) -> None:
    """Run OCR workers in parallel until cancelled, sharing one client."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        workers = [
            asyncio.create_task(_ocr_worker(client, ocr_queue, failures))
            for _ in range(OCR_CONCURRENCY)
        ]

        try:
            await asyncio.gather(*workers)
        finally:
            for worker in workers:
                worker.cancel()

            await asyncio.gather(*workers, return_exceptions=True)
