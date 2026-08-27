import argparse
import sys

from rag_gis_api import DATA_PATH
from rag_gis_api.services.chunk_service import clear_chunks


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Delete stored chunks and their page cache, all of them or one path."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help=(
            f"File or folder relative to {DATA_PATH}; a folder clears every file "
            "under it (default: every stored chunk)."
        ),
    )
    args = parser.parse_args()

    target = args.path or "everything"
    print(f"About to clear: {target}")
    confirmation = input('Type "CLEAR" to confirm: ')
    if confirmation != "CLEAR":
        print("Aborted; nothing was cleared.")
        return

    removed_chunks, removed_pages = clear_chunks(args.path)

    print(f"Cleared {target}: removed {removed_chunks} chunks and {removed_pages} cached pages")
