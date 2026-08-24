import argparse
import sys

from rag_gis_api import DATA_PATH
from rag_gis_api.services.ingest.loader.load_file import load_file

# Extensions load_file knows how to read.
SUPPORTED_SUFFIXES = (".pdf", ".docx")


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Print page_content of a file under documents/.")
    parser.add_argument(
        "file",
        nargs="?",
        help=(
            f"File or folder relative to {DATA_PATH}; a folder reads every supported "
            "file under it (default: every supported file found)."
        ),
    )
    parser.add_argument(
        "--page",
        type=int,
        help="Print only this page number (0-based, as stored in the metadata; PDF only).",
    )
    args = parser.parse_args()

    target = DATA_PATH / args.file if args.file else DATA_PATH

    if target.is_dir():
        paths = sorted(p for p in target.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES)
    else:
        paths = [target]

    results, failed = [], []

    for path in paths:
        try:
            documents = load_file(path)
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
