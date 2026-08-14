from rag_gis_api.services.llm_service import get_llm


SYSTEM_PROMPT = "ตอบเป็นภาษาไทย กระชับ ความยาวไม่เกิน 4 บรรทัด ห้ามตอบเกิน 4 บรรทัดเด็ดขาด"


def ask(question: str) -> str:
    llm = get_llm()
    response = llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            ("human", question),
        ]
    )
    return response.text
