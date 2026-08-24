from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.format_payload import (
    format_category_breakdown,
    format_guidance_section,
)

DEPARTMENT = "กองจัดการสิ่งแวดล้อมธรรมชาติและศิลปกรรม"


def build_skeleton(request: AnalysisRequest) -> str:
    """
    Assemble the deterministic part of the report: the formal opening, the
    per-category count breakdown, and ONEP's own guidance/citations verbatim.

    Built in code rather than by the LLM so project name, counts, and legal
    citation numbers can never drift or be paraphrased away — mirrors the
    fixed structure ONEP's own "วิเคราะห์โดย AI" tab shows today.
    """
    project = request.project
    buffer_km = project.default_buffer_m / 1000
    # Both worked examples in the spec already start `project.name` with "โครงการ" — avoid
    # doubling it into "...ของโครงการโครงการปรับปรุง..." when that's the case.
    name_phrase = project.name if project.name.startswith("โครงการ") else f"โครงการ{project.name}"

    opening = (
        f"เพื่อนำข้อมูลมาประกอบการพิจารณาผลกระทบสิ่งแวดล้อมของ{name_phrase} "
        f"{DEPARTMENT}ได้ตรวจสอบในระยะ {buffer_km:.2f} กิโลเมตรจากแนวโครงการฯ "
        "พบรายละเอียดดังนี้"
    )

    return (
        f"{opening}\n\n"
        f"{format_category_breakdown(request)}\n\n"
        f"ทั้งนี้ {DEPARTMENT} มีข้อคิดเห็นเพื่อพิจารณาประกอบการดำเนินโครงการฯ ดังนี้\n\n"
        f"{format_guidance_section(request)}"
    )
