from collections.abc import AsyncIterator
from dataclasses import dataclass

from rag_gis_api.repositories import vector_repository
from rag_gis_api.services.chat.build_messages import build_messages
from rag_gis_api.services.chat.list_sources import list_sources
from rag_gis_api.services.llm_service import get_llm


RETRIEVE_LIMIT = 5


@dataclass
class ChatEvent:
    """One step of the pipeline. `name` is the SSE event name, `data` its payload."""

    name: str  # "status" | "token" | "done" | "error"
    data: dict[str, object]


async def ask(question: str) -> dict[str, object]:
    """Run the whole RAG pipeline and return the finished answer."""
    chunks = await vector_repository.search_chunks(question, RETRIEVE_LIMIT)
    response = await get_llm().ainvoke(build_messages(question, chunks))

    return {"answer": response.text, "sources": list_sources(chunks)}


async def ask_stream(question: str) -> AsyncIterator[ChatEvent]:
    """
    Run the RAG pipeline and report every stage while it happens.

    Retrieval takes seconds before the first token exists, so the caller gets
    `status` events to show meanwhile, then one `token` event per LLM chunk,
    then `done` carrying the full answer.

    A failure is reported as an `error` event rather than raised: an aborted
    stream makes the browser's EventSource reconnect, which would silently
    replay the whole question and pay for the embedding and LLM calls again.
    """
    try:
        yield ChatEvent(
            "status", {"stage": "retrieving", "message": "กำลังค้นหาเอกสาร..."}
        )

        chunks = await vector_repository.search_chunks(question, RETRIEVE_LIMIT)

        yield ChatEvent(
            "status",
            {
                "stage": "retrieved",
                "message": f"พบเอกสารที่เกี่ยวข้อง {len(chunks)} รายการ",
                "count": len(chunks),
            },
        )
        yield ChatEvent(
            "status", {"stage": "generating", "message": "กำลังสร้างคำตอบ..."}
        )

        answer = ""

        async for chunk in get_llm().astream(build_messages(question, chunks)):
            # Gemini also emits chunks that only carry metadata, with no text.
            if not chunk.text:
                continue

            answer += chunk.text

            yield ChatEvent("token", {"text": chunk.text})

        yield ChatEvent("done", {"answer": answer, "sources": list_sources(chunks)})
    except Exception as error:
        yield ChatEvent("error", {"message": f"{type(error).__name__}: {error}"})
