import hashlib
from pathlib import Path

# Read large PDFs block by block instead of loading them into memory at once.
READ_BLOCK_SIZE = 1024 * 1024


def calculate_file_hash(path: Path) -> str:
    """Calculate SHA-256 hash of the entire file."""
    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(READ_BLOCK_SIZE), b""):
            sha256.update(block)

    return sha256.hexdigest()


def calculate_content_hash(content: str) -> str:
    """Calculate SHA-256 hash of chunk content."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
