import argparse
import sys
from itertools import groupby
from pathlib import Path

from rag_gis_api import DATA_PATH
from rag_gis_api.repositories import vector_repository


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Print the stored chunks of one document, page by page."
    )
    parser.add_argument(
        "path",
        help=f"Path relative to {DATA_PATH}, e.g. law/min_notif/Min_Notif_028.pdf.",
    )
    parser.add_argument(
        "--page",
        type=int,
        help="Print only chunks of this page (0-based, as stored in the metadata).",
    )
    args = parser.parse_args()

    # Chunks are stored under a posix path relative to DATA_PATH.
    source = Path(args.path).as_posix()
    chunks = vector_repository.get_chunks(source)

    if not chunks:
        print(f"{source} -> no chunks stored (run rag-gis-ingest first)")
        return

    if args.page is not None:
        chunks = [c for c in chunks if c.metadata.get("page") == args.page]

    pages = [
        list(page_chunks)
        for _, page_chunks in groupby(chunks, key=lambda chunk: chunk.metadata.get("page"))
    ]

    print(f"{source} -> {len(chunks)} chunks on {len(pages)} pages")

    for page_chunks in pages:
        page = page_chunks[0].metadata.get("page")
        print(f"\n===== page {page} ({len(page_chunks)} chunks) =====")

        for chunk in page_chunks:
            print(f"\n--- {chunk.id} ({len(chunk.page_content)} chars) ---")
            print(chunk.page_content)
