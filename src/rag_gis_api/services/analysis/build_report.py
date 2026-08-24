from rag_gis_api.schemas.analysis import AnalysisProject, AnalysisRequest
from rag_gis_api.services.analysis.format_payload import (
    format_category_breakdown,
    format_guidance_section,
    format_number,
)

DEPARTMENT = "กองจัดการสิ่งแวดล้อมธรรมชาติและศิลปกรรม"


def project_name_phrase(project: AnalysisProject) -> str:
    """
    The project name as it reads after "โครงการ" in a sentence.

    Both worked examples in the spec already start `name` with "โครงการ", which would
    otherwise stutter into "...ของโครงการโครงการปรับปรุง...".
    """
    return project.name if project.name.startswith("โครงการ") else f"โครงการ{project.name}"


def buffer_phrase(project: AnalysisProject) -> str:
    """
    Describe the radius actually inspected, in km.

    Features can each carry their own `buffer_m` (a user may widen one beyond the
    legal default), so stating `default_buffer_m` alone would understate the scope
    of the check in the one sentence meant to state it precisely.
    """
    radii = {feature.buffer_m for feature in project.features if feature.buffer_m is not None}

    if not radii:
        radii = {project.default_buffer_m}

    smallest, largest = min(radii) / 1000, max(radii) / 1000

    if smallest == largest:
        return f"ระยะ {smallest:.2f} กิโลเมตร"

    return f"ระยะ {smallest:.2f} ถึง {largest:.2f} กิโลเมตร"


def build_skeleton(request: AnalysisRequest) -> str:
    """
    Assemble the deterministic part of the report: the formal opening, the
    per-category count breakdown, and ONEP's own guidance/citations verbatim.

    Built in code rather than by the LLM so project name, counts, and legal
    citation numbers can never drift or be paraphrased away — mirrors the
    fixed structure ONEP's own "วิเคราะห์โดย AI" tab shows today.
    """
    project = request.project
    summary = request.summary

    opening = (
        f"เพื่อนำข้อมูลมาประกอบการพิจารณาผลกระทบสิ่งแวดล้อมของ{project_name_phrase(project)} "
        f"{DEPARTMENT}ได้ตรวจสอบใน{buffer_phrase(project)}จากแนวโครงการฯ "
        "พบรายละเอียดดังนี้"
    )

    totals = (
        f"รวมพบแหล่งที่ได้รับผลกระทบทั้งสิ้น {format_number(summary.total_sites)} แห่ง "
        f"({format_number(summary.total_geometries)} ชิ้นข้อมูลเชิงพื้นที่)"
    )

    return (
        f"{opening}\n\n"
        f"{format_category_breakdown(request)}\n\n"
        f"{totals}\n\n"
        f"ทั้งนี้ {DEPARTMENT} มีข้อคิดเห็นเพื่อพิจารณาประกอบการดำเนินโครงการฯ ดังนี้\n\n"
        f"{format_guidance_section(request)}"
    )
