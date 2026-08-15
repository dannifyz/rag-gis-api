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


def build_messages(question: str, chunks: list[Document]) -> list[tuple[str, str]]:
    """Build the messages sent to the LLM, with the retrieved chunks as context."""
    return [
        ("system", SYSTEM_PROMPT),
        ("human", f"context:\n{format_context(chunks)}\n\nคำถาม: {question}"),
    ]
