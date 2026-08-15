import asyncio
import io
import json
from pathlib import Path

import pypdfium2
import requests
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


def extract_text_from_image(
    image,
):
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

    response = requests.post(URL, files=files, data=data, headers=headers)

    if response.status_code == 200:
        result = response.json()

        # Extract text from successful results
        extracted_texts = []
        for page_result in result.get("results", []):
            if page_result.get("success") and page_result.get("message"):
                content = page_result["message"]["choices"][0]["message"]["content"]
                try:
                    # Try to parse as JSON if it's structured output
                    parsed_content = json.loads(content)
                    text = parsed_content.get("natural_text", content)
                except json.JSONDecodeError:
                    text = content
                extracted_texts.append(text)
            elif not page_result.get("success"):
                filename = page_result.get("filename", "unknown")
                error = page_result.get("error", "Unknown error")

                print(f"Error processing {filename}: {error}")

        return "\n".join(extracted_texts)
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


async def consume_ocr_queue(ocr_queue: asyncio.Queue[Document]) -> None:
    """Drain the pages PyPDF could not read."""
    while True:
        page = await ocr_queue.get()
        try:
            page.page_content = extract_text_from_image(
                render_page(page.metadata["source"], page.metadata["page"])
            )
            print(f"OCR:  {page.metadata.get('source')} page {page.metadata.get('page')}")
        finally:
            ocr_queue.task_done()
