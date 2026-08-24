import argparse
import sys
from pathlib import Path

from rag_gis_api import DATA_PATH
from rag_gis_api.services.chunk_service import clear_vectorstore
from rag_gis_api.services.ingest_service import IngestResult, ingest_file


def ingest_all_files(paths: list[Path]) -> tuple[list[IngestResult], list[str]]:
    """Ingest every path and return what succeeded, and the sources that failed."""
    print(f"Found {len(paths)} PDF files")

    results, failed = [], []

    for path in paths:
        source = path.relative_to(DATA_PATH).as_posix()

        try:
            result = ingest_file(path)
        except Exception as e:
            print(f"FAILED: {source}")
            print(e)
            failed.append(source)
            continue

        results.append(result)

        if result.status == "skipped":
            print(f"SKIP  {source} (unchanged)")
        else:
            print(
                f"{result.status.upper():6}{source} "
                f"(+{result.inserted} ~{result.updated} -{result.deleted})"
            )

    return results, failed


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Ingest PDFs under documents/ into the vector store."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        help=(
            f"File or folder relative to {DATA_PATH}; a folder ingests every PDF "
            "under it (default: every PDF found)."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete every stored chunk first, then ingest from scratch.",
    )
    args = parser.parse_args()

    if args.reset:
        print(f"Reset: removed {clear_vectorstore()} chunks")

    target = DATA_PATH / args.pdf if args.pdf else DATA_PATH

    # A folder ingests every PDF under it, a file ingests just that file.
    paths = sorted(target.rglob("*.pdf")) if target.is_dir() else [target]

    results, failed = ingest_all_files(paths)

    print(
        f"\nDone: {len(results)} files, "
        f"+{sum(r.inserted for r in results)} "
        f"~{sum(r.updated for r in results)} "
        f"-{sum(r.deleted for r in results)} chunks"
    )

    if failed:
        print(f"\nFailed: {len(failed)} files - nothing stored, run again to retry")

        for source in failed:
            print(f"  - {source}")

        sys.exit(1)
