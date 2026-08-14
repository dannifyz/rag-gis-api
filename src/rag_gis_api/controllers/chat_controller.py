import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from rag_gis_api.services.chat_service import ask, ask_stream


DEFAULT_QUESTION = "สวัสดีครับคุณคือใคร"

router = APIRouter(prefix="/chat", tags=["chat"])

Question = Annotated[str, Query(description="Question to ask the LLM.")]


@router.get("")
async def chat(question: Question = DEFAULT_QUESTION) -> dict[str, object]:
    return {"question": question, **await ask(question)}


@router.get("/stream")
async def chat_stream(question: Question = DEFAULT_QUESTION) -> EventSourceResponse:
    """Same answer as GET /chat, but streamed as it is produced."""

    async def events() -> AsyncIterator[dict[str, str]]:
        async for event in ask_stream(question):
            yield {
                "event": event.name,
                # Every payload is JSON: it keeps the shape uniform, and it
                # escapes the newlines inside a token, which would otherwise be
                # read as the end of the event.
                "data": json.dumps(event.data, ensure_ascii=False),
            }

    # EventSourceResponse sets the no-buffering headers and cancels the
    # generator when the client goes away, so an abandoned tab stops the LLM.
    return EventSourceResponse(events())
