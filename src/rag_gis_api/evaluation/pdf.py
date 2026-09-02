import base64
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium

# The expected letters are scanned images with no text layer, so they are rendered
# to page images and read by the multimodal judge. 2x keeps Thai legible without
# bloating the request.
RENDER_SCALE = 2


def pdf_to_image_data_urls(path: Path) -> list[str]:
    """Render every page of a PDF to a base64 PNG data URL, one per page."""
    pdf = pdfium.PdfDocument(path)
    try:
        urls = []
        for page in pdf:
            image = page.render(scale=RENDER_SCALE).to_pil()
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode()
            urls.append(f"data:image/png;base64,{encoded}")
        return urls
    finally:
        pdf.close()
