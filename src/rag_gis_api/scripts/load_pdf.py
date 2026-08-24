import argparse
import sys

from rag_gis_api import DATA_PATH
from rag_gis_api.services.ingest.load_pdf import load_pdf


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Print page_content of a PDF under documents/.")
    parser.add_argument(
        "pdf",
        nargs="?",
        help=(
            f"File or folder relative to {DATA_PATH}; a folder ingests every PDF "
            "under it (default: every PDF found)."
        ),
    )
    parser.add_argument(
        "--page",
        type=int,
        help="Print only this page number (0-based, as stored in the metadata).",
    )
    args = parser.parse_args()

    target = DATA_PATH / args.pdf if args.pdf else DATA_PATH

    paths = sorted(target.rglob("*.pdf")) if target.is_dir() else [target]

    results, failed = [], []

    for path in paths:
        try:
            documents = load_pdf(path)
        except Exception as e:
            failed.append((path, e))
            continue

        if args.page is not None:
            documents = [d for d in documents if d.metadata.get("page") == args.page]

        results.append((path, documents))

    for path, result in results:
        print(f"{path} -> {len(result)} pages")

        for page in result:
            print(f"\n===== page {page.metadata.get('page')} =====")
            print(page.page_content)

    if failed:
        print("\n===== failed path =====")

        for i in range(len(failed)):
            print(f"{i}: {failed[i][0]}")
