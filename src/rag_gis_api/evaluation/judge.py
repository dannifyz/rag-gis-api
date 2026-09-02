from langchain_core.messages import HumanMessage, SystemMessage

from rag_gis_api.evaluation.schemas import JudgeResult
from rag_gis_api.services.llm_service import get_llm

JUDGE_SYSTEM_PROMPT = (
    "คุณคือผู้ประเมินคุณภาพ (LLM-as-a-judge) เปรียบเทียบหนังสือราชการที่ LLM ร่าง "
    "กับหนังสือเฉลย (expected) ของ สผ.\n\n"
    "ประเมินเฉพาะส่วน 'ข้อคิดเห็น' (ข้อเสนอแนะประกอบการพิจารณาดำเนินโครงการ) เท่านั้น "
    "ซึ่งแต่ละข้อประกอบด้วย (ก) ผลกระทบที่อาจเกิดขึ้น และ (ข) แนวทางแก้ไข/มาตรการลดผลกระทบ\n"
    "ห้ามประเมินส่วนอื่น โดยเฉพาะส่วนสรุปจำนวน/ประเภทแหล่งที่ตรวจพบ (เช่น พบ/ไม่พบแหล่งประเภทใด "
    "กี่แห่ง) รวมทั้งหัวจดหมาย เลขที่หนังสือ วันที่ คำขึ้นต้น คำลงท้าย ลายเซ็น ข้อมูลติดต่อ "
    "และย่อหน้ามาตรฐานเรื่องการสำรวจพื้นที่จริง เพราะส่วนเหล่านี้ระบบประกอบขึ้นเองในรูปแบบตายตัว "
    "ที่ไม่จำเป็นต้องตรงถ้อยคำกับหนังสือเฉลย\n\n"
    "ขั้นตอน:\n"
    "1. อ่านเฉพาะส่วนข้อคิดเห็นของหนังสือเฉลย แล้วดึง 'ใจความสำคัญ' ออกมาเป็นข้อ ๆ "
    "โดยแยกเป็นหน่วยที่ตรวจสอบได้ เช่น ผลกระทบที่ระบุ ชื่อแหล่ง/ประเภทแหล่งที่เอ่ยถึง "
    "และมาตรการที่แนะนำในแต่ละข้อ\n"
    "   หมายเหตุ: หนังสือเฉลยผ่านการ OCR อาจมีตัวสะกดคลาดเคลื่อนบ้าง ให้ตีความตามความหมาย\n"
    "2. สำหรับใจความแต่ละข้อ ตัดสินว่า LLM output เขียนถึงหรือไม่ (covered) "
    "โดยยึดความหมายที่ตรงกัน ไม่จำเป็นต้องใช้ถ้อยคำเดียวกัน "
    "และยกข้อความจาก LLM output มาเป็นหลักฐาน (evidence)\n"
    "3. ระบุใจความในส่วนข้อคิดเห็นที่ LLM เขียนเพิ่มแต่ไม่มีในหนังสือเฉลย (extra_items)\n\n"
    "ตอบเป็นภาษาไทย ยึดส่วนข้อคิดเห็นของหนังสือเฉลยเป็นเกณฑ์เสมอ"
)


async def judge_recall(expected_text: str, actual_text: str) -> JudgeResult:
    """Compare one LLM output against its expected letter and return the raw judgement."""
    llm = get_llm().with_structured_output(JudgeResult)

    human = (
        f"หนังสือเฉลย (expected):\n\n{expected_text}\n\n"
        f"=====\n\nLLM output ที่ต้องประเมิน:\n\n{actual_text}"
    )

    return await llm.ainvoke([SystemMessage(JUDGE_SYSTEM_PROMPT), HumanMessage(human)])
