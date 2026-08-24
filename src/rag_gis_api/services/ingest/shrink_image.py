import io

from PIL import Image, ImageChops

# A fold-out map page renders far larger than the A4 scans RENDER_DPI was
# picked for, and at 400 DPI one runs to hundreds of megapixels. Capping the
# longest edge keeps that off the heap before anything is encoded.
MAX_EDGE_PIXELS = 4000

# The endpoint's proxy rejects anything larger with HTTP 413.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024

# Below this the tone marks are gone and OCR has nothing left to read, so a
# page that still will not fit has to fail rather than shrink further.
MIN_EDGE_PIXELS = 1000


class ImageTooLargeError(Exception):
    """A page will not fit the upload limit at a resolution worth reading."""


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
            raise ImageTooLargeError(
                f"the page is still {len(data) / 1048576:.1f} MB at {max(image.size)} px"
            )

        image = image.resize(size, Image.LANCZOS)
        data = encode(image)

    return data
