from dataclasses import dataclass, field

from langchain_core.documents import Document


@dataclass
class ChunkDiff:
    """What has to happen in the vector store to catch up with a file."""

    to_insert: list[Document] = field(default_factory=list)
    to_update: list[Document] = field(default_factory=list)
    unchanged: list[Document] = field(default_factory=list)
    to_delete_ids: list[str] = field(default_factory=list)


def compare_chunks(
    new_chunks: list[Document],
    existing_hashes: dict[str, str],
) -> ChunkDiff:
    """
    Compare freshly chunked documents against what is already stored.

    existing_hashes maps chunk id -> content hash, e.g.

        {"law/act/law_001.pdf:6:0": "abc123"}
    """
    new_by_id = {chunk.metadata["id"]: chunk for chunk in new_chunks}

    diff = ChunkDiff()

    for chunk_id, chunk in new_by_id.items():
        old_hash = existing_hashes.get(chunk_id)
        new_hash = chunk.metadata["content_hash"]

        if old_hash is None:
            diff.to_insert.append(chunk)
        elif old_hash != new_hash:
            diff.to_update.append(chunk)
        else:
            diff.unchanged.append(chunk)

    diff.to_delete_ids = [chunk_id for chunk_id in existing_hashes if chunk_id not in new_by_id]

    return diff
