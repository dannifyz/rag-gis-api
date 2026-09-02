from pydantic import BaseModel, Field


class RecallItem(BaseModel):
    """One substantive point from the expected letter, checked against the LLM output."""

    point: str = Field(description="ใจความสำคัญหนึ่งข้อที่ปรากฏในหนังสือเฉลย (expected)")
    covered: bool = Field(description="LLM output เขียนถึงใจความนี้หรือไม่")
    evidence: str = Field(
        description="ข้อความจาก LLM output ที่รองรับ หากไม่ครอบคลุมให้อธิบายสั้น ๆ ว่าขาดอะไร"
    )


class ExtraItem(BaseModel):
    """A point the LLM wrote that the expected letter does not contain."""

    point: str = Field(description="ใจความที่ LLM เขียนแต่ไม่มีในหนังสือเฉลย")
    note: str = Field(description="คำอธิบายสั้น ๆ")


class JudgeResult(BaseModel):
    """The raw judgement returned by the LLM judge for one case."""

    recall_items: list[RecallItem] = Field(
        description="ทุกใจความสำคัญของหนังสือเฉลย พร้อมผลตรวจว่า LLM ครอบคลุมหรือไม่"
    )
    extra_items: list[ExtraItem] = Field(description="ใจความที่ LLM เขียนเพิ่มแต่ไม่มีในหนังสือเฉลย")


class RecallScore(BaseModel):
    score: int
    max_score: int
    percent: float


class CaseScore(BaseModel):
    """The scored result written to evals/scores/<id>.json."""

    id: str
    project_name: str
    recall: RecallScore
    matched: list[RecallItem]
    missing: list[RecallItem]
    extra: list[ExtraItem]


class CaseRecall(BaseModel):
    id: str
    recall: RecallScore


class SummaryScore(BaseModel):
    """The aggregate written to evals/scores/summary.json."""

    recall: RecallScore
    case_count: int
    cases: list[CaseRecall]
