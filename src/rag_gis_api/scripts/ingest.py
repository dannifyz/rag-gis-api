import argparse
import sys
from pathlib import Path

from rag_gis_api import DATA_PATH
from rag_gis_api.services.ingest_service import IngestResult, ingest_file


def ingest_all_files(paths: list[Path]) -> list[IngestResult]:
    print(f"Found {len(paths)} PDF files")

    results = []

    for path in paths:
        source = path.relative_to(DATA_PATH).as_posix()

        try:
            result = ingest_file(path)
        except Exception as e:
            print(f"FAILED: {source}")
            print(e)
            continue

        results.append(result)

        if result.status == "skipped":
            print(f"SKIP  {source} (unchanged)")
        else:
            print(
                f"{result.status.upper():6}{source} "
                f"(+{result.inserted} ~{result.updated} -{result.deleted})"
            )

    return results


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Ingest PDFs under documents/ into the vector store."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        help=f"Path relative to {DATA_PATH} (default: every PDF found).",
    )
    args = parser.parse_args()

    if args.pdf:
        paths = [DATA_PATH / args.pdf]
    else:
        paths = sorted(DATA_PATH.rglob("*.pdf"))

    results = ingest_all_files(paths)

    print(
        f"\nDone: {len(results)} files, "
        f"+{sum(r.inserted for r in results)} "
        f"~{sum(r.updated for r in results)} "
        f"-{sum(r.deleted for r in results)} chunks"
    )
