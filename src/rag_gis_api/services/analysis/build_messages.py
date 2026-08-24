from langchain_core.documents import Document

from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.format_payload import format_project, format_sites

SYSTEM_PROMPT = (
    "คุณเขียนย่อหน้าสรุปปิดท้ายต่อจากรายงานผลวิเคราะห์ผลกระทบสิ่งแวดล้อมที่ประกอบไปด้วย "
    "รายการแหล่งที่ได้รับผลกระทบและแนวทางที่ ONEP กำหนดไว้แล้วด้านบน (ให้มาเป็นบริบท ไม่ต้องพิมพ์ซ้ำ)\n\n"
    "งานของคุณ: เขียนเพิ่มอีก 1 ย่อหน้าเท่านั้น เป็นภาษาไทยล้วน แบบข้อความธรรมดา (plain text) "
    "ห้ามใช้ Markdown หรือ HTML ความยาวประมาณ 300-800 ตัวอักษร\n\n"
    "ห้ามใส่หมายเลขอ้างอิงแบบ [1] [2] ใหม่ — ตัวเลขอ้างอิงในรายงานด้านบนเป็นของ ONEP เท่านั้น "
    "ถ้าเอกสารกฎหมายที่แนบมามีข้อกำหนดที่เกี่ยวข้องเพิ่มเติม (เช่น ระยะที่ต้องทำ EIA) "
    "ให้อ้างถึงโดยระบุชื่อไฟล์/หมวดตรง ๆ ในเนื้อความแทน ไม่ใช้เลขอ้างอิง "
    "ห้ามเดาข้อเท็จจริงที่ไม่มีในข้อมูลผลวิเคราะห์หรือเอกสารที่ให้มา "
    "ถ้าโครงการมีหลายรูปในคนละพื้นที่ ให้กล่าวถึงทุกพื้นที่ที่เกี่ยวข้อง ไม่ใช่แค่พื้นที่เดียว"
)

NO_CONTEXT = "(ไม่พบเอกสารกฎหมายที่เกี่ยวข้องเพิ่มเติม)"


def format_legal_context(chunks: list[Document]) -> str:
    if not chunks:
        return NO_CONTEXT

    return "\n\n".join(
        f"[{index}] {chunk.metadata['source']} หน้า {chunk.metadata['page']}\n{chunk.page_content}"
        for index, chunk in enumerate(chunks, start=1)
    )


def build_messages(
    request: AnalysisRequest, skeleton: str, legal_chunks: list[Document]
) -> list[tuple[str, str]]:
    human = (
        f"ข้อมูลโครงการ:\n{format_project(request)}\n\n"
        f"รายละเอียดแหล่งที่ได้รับผลกระทบ:\n{format_sites(request)}\n\n"
        f"รายงานที่เขียนไว้แล้ว (บริบท ไม่ต้องพิมพ์ซ้ำ):\n{skeleton}\n\n"
        f"เอกสารกฎหมายที่อาจเกี่ยวข้องเพิ่มเติม:\n{format_legal_context(legal_chunks)}"
    )

    return [("system", SYSTEM_PROMPT), ("human", human)]
