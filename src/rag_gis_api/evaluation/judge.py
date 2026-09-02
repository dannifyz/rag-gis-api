from langchain_core.messages import HumanMessage, SystemMessage

from rag_gis_api.evaluation.schemas import JudgeResult
from rag_gis_api.services.llm_service import get_llm

# Recall here means: of the substantive points the official letter makes, how many did
# the LLM output also make. Boilerplate is excluded on purpose — letterhead, greeting,
# signature, the standing survey advice and closing are template text the system fills
# in deterministically, so counting them would only inflate recall.
JUDGE_SYSTEM_PROMPT = (
    "คุณคือผู้ประเมินคุณภาพ (LLM-as-a-judge) เปรียบเทียบหนังสือราชการที่ LLM ร่าง "
    "กับหนังสือเฉลย (expected) ของ สผ.\n\n"
    "ขั้นตอน:\n"
    "1. อ่านหนังสือเฉลย แล้วดึง 'ใจความสำคัญ' ที่ตรวจสอบได้ออกมาเป็นข้อ ๆ "
    "โดยเน้นเนื้อหาสาระ ได้แก่ ผลการตรวจสอบ (เช่น พบ/ไม่พบแหล่งประเภทใด จำนวนแหล่ง) "
    "และข้อคิดเห็น/ข้อเสนอแนะแต่ละข้อ (ผลกระทบที่ระบุ ชื่อแหล่งที่เอ่ยถึง และมาตรการที่แนะนำ)\n"
    "   ห้ามนับข้อความสำเร็จรูปเป็นใจความ ได้แก่ หัวจดหมาย เลขที่หนังสือ วันที่ คำขึ้นต้น "
    "คำลงท้าย ลายเซ็น ข้อมูลติดต่อ และย่อหน้ามาตรฐานเรื่องการสำรวจพื้นที่จริง\n"
    "   หมายเหตุ: หนังสือเฉลยผ่านการ OCR อาจมีตัวสะกดคลาดเคลื่อนบ้าง ให้ตีความตามความหมาย\n"
    "2. สำหรับใจความแต่ละข้อ ตัดสินว่า LLM output เขียนถึงหรือไม่ (covered) "
    "โดยยึดความหมายที่ตรงกัน ไม่จำเป็นต้องใช้ถ้อยคำเดียวกัน "
    "และยกข้อความจาก LLM output มาเป็นหลักฐาน (evidence)\n"
    "3. ระบุใจความที่ LLM เขียนเพิ่มแต่ไม่มีในหนังสือเฉลย (extra_items)\n\n"
    "ตอบเป็นภาษาไทย ยึดหนังสือเฉลยเป็นเกณฑ์เสมอ"
)


async def judge_recall(expected_text: str, actual_text: str) -> JudgeResult:
    """Compare one LLM output against its expected letter and return the raw judgement."""
    llm = get_llm().with_structured_output(JudgeResult)

    human = (
        f"หนังสือเฉลย (expected):\n\n{expected_text}\n\n"
        f"=====\n\nLLM output ที่ต้องประเมิน:\n\n{actual_text}"
    )

    return await llm.ainvoke([SystemMessage(JUDGE_SYSTEM_PROMPT), HumanMessage(human)])
