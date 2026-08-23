import json

from rag_gis_api.database.redis_client import redis_client

TTL_SECONDS = 60 * 60 * 24  # session history expires after a day of inactivity
MAX_TURNS = 10  # bound how many past turns get replayed into the prompt


def _key(session_id: str) -> str:
    return f"session:{session_id}:history"


async def get_history(session_id: str) -> list[tuple[str, str]]:
    """Return this session's past (question, answer) turns, oldest first."""
    raw = await redis_client.get(_key(session_id))

    if not raw:
        return []

    return [tuple(turn) for turn in json.loads(raw)]


async def append_turn(session_id: str, question: str, answer: str) -> None:
    """Add one (question, answer) turn to the session, keeping only the most recent MAX_TURNS."""
    history = await get_history(session_id)
    history.append((question, answer))
    history = history[-MAX_TURNS:]

    await redis_client.set(_key(session_id), json.dumps(history), ex=TTL_SECONDS)
