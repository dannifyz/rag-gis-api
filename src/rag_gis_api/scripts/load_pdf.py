import argparse
import sys

from rag_gis_api import DATA_PATH
from rag_gis_api.services.ingest.load_pdf import load_pdf

SUFFIX = ".pdf"


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Print page_content of a PDF under documents/.")
    parser.add_argument(
        "--directory",
        default=".",
        help=f"Path relative to {DATA_PATH}",
    )
    parser.add_argument(
        "--pdf",
        help=f"Path relative to {DATA_PATH} to PDF.",
    )
    parser.add_argument(
        "--page",
        type=int,
        help="Print only this page number (0-based, as stored in the metadata).",
    )
    args = parser.parse_args()

    if args.pdf is not None:
        paths = [DATA_PATH / args.pdf]
    else:
        paths = []
        path_dir = DATA_PATH / args.directory
        if path_dir.is_file():
            raise SystemExit(f"{args.directory} is a file. Use --pdf for a single file.")

        for path in sorted(path_dir.rglob("*")):
            if path.suffix.lower() == SUFFIX:
                paths.append(path)

    for path in paths:
        documents = load_pdf(path)

        if args.page is not None:
            documents = [d for d in documents if d.metadata.get("page") == args.page]

        print(f"{path} -> {len(documents)} pages")

        for document in documents:
            print(f"\n===== page {document.metadata.get('page')} =====")
            print(document.page_content)
