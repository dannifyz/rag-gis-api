from langchain_core.documents import Document

SYSTEM_PROMPT = (
    "คุณเป็นผู้ช่วยตอบคำถามจากเอกสารกฎหมายและข้อมูลด้าน GIS "
    "ตอบเป็นภาษาไทย กระชับ โดยอ้างอิงจาก context ที่ให้มาเท่านั้น "
    "ถ้า context ไม่มีข้อมูลพอที่จะตอบ ให้บอกตรง ๆ ว่าไม่พบข้อมูลในเอกสาร ห้ามเดา"
)

NO_CONTEXT = "(ไม่พบเอกสารที่เกี่ยวข้อง)"


def format_context(chunks: list[Document]) -> str:
    """Join the retrieved chunks into one block, each tagged with where it came from."""
    if not chunks:
        return NO_CONTEXT

    return "\n\n".join(
        f"[{index}] {chunk.metadata['source']} หน้า {chunk.metadata['page']}\n{chunk.page_content}"
        for index, chunk in enumerate(chunks, start=1)
    )


def build_messages(
    question: str,
    chunks: list[Document],
    history: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """
    Build the messages sent to the LLM, with the retrieved chunks as context.

    `history` is this session's past (question, answer) turns, oldest first, so
    the model can resolve references like "it" or "ต่อจากข้อก่อนหน้า". Only the
    current question gets fresh RAG context — past turns are replayed as plain
    conversation, not re-retrieved.
    """
    messages: list[tuple[str, str]] = [("system", SYSTEM_PROMPT)]

    for past_question, past_answer in history or []:
        messages.append(("human", past_question))
        messages.append(("ai", past_answer))

    messages.append(("human", f"context:\n{format_context(chunks)}\n\nคำถาม: {question}"))

    return messages
