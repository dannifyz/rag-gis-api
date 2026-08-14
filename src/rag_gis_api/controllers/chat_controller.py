from typing import Annotated

from fastapi import APIRouter, Query

from rag_gis_api.services.chat_service import ask


DEFAULT_QUESTION = "สวัสดีครับคุณคือใคร"

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("")
def chat(
    question: Annotated[
        str, Query(description="Question to ask the LLM.")
    ] = DEFAULT_QUESTION,
) -> dict[str, str]:
    return {"question": question, "answer": ask(question)}
