import argparse
import sys
from pathlib import Path

from rag_gis_api import DATA_PATH
from rag_gis_api.services.chunk_service import clear_chunks
from rag_gis_api.services.ingest.loader.load_file import SUPPORTED_SUFFIXES
from rag_gis_api.services.ingest_service import IngestResult, ingest_file


def ingest_all_files(paths: list[Path]) -> tuple[list[IngestResult], list[str]]:
    """Ingest every path and return what succeeded, and the sources that failed."""
    print(f"Found {len(paths)} files")

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
        description="Ingest documents under documents/ into the vector store."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help=(
            f"File or folder relative to {DATA_PATH}; a folder ingests every "
            "supported file under it (default: every supported file found)."
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear stored chunks under path first, then ingest from scratch.",
    )
    args = parser.parse_args()

    if args.reset:
        removed_chunks, removed_pages = clear_chunks(args.path)
        print(f"Reset: removed {removed_chunks} chunks and {removed_pages} cached pages")

    target = DATA_PATH / args.path if args.path else DATA_PATH

    # A folder ingests every supported file under it, a file ingests just itself.
    if target.is_dir():
        paths = sorted(p for p in target.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES)
    else:
        paths = [target]

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
