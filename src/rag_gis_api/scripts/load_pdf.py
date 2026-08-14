import argparse
import sys

from rag_gis_api import PROJECT_ROOT
from rag_gis_api.services.ingest.pdf_loader import load_pdf


DATA_PATH = PROJECT_ROOT / "documents"
# Min_Notif_028.pdf is readable by PyPDF.
DEFAULT_PDF = "law/min_notif/Min_Notif_028.pdf"


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Print page_content of a PDF under documents/."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        default=DEFAULT_PDF,
        help=f"Path relative to {DATA_PATH} (default: {DEFAULT_PDF}).",
    )
    parser.add_argument(
        "--page",
        type=int,
        help="Print only this page number (0-based, as stored in the metadata).",
    )
    args = parser.parse_args()

    path = DATA_PATH / args.pdf
    documents = load_pdf(path)

    if args.page is not None:
        documents = [d for d in documents if d.metadata.get("page") == args.page]

    print(f"{path} -> {len(documents)} pages")
    for document in documents:
        print(f"\n===== page {document.metadata.get('page')} =====")
        print(document.page_content)
