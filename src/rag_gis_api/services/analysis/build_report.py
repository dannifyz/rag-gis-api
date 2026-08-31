import re

from rag_gis_api.schemas.analysis import AnalysisProject, AnalysisRequest
from rag_gis_api.services.analysis.format_payload import (
    format_category_breakdown,
    format_project_area,
)
from rag_gis_api.services.analysis.thai_text import format_count, format_measure

OFFICE = "สำนักงานนโยบายและแผนทรัพยากรธรรมชาติและสิ่งแวดล้อม"
DEFAULT_AGENCY = "หน่วยงานเจ้าของโครงการ"

# The datasets named in the opening, phrased as สผ.'s letters name them. Kept as its own
# string rather than derived from CATEGORY_ORDER: the letter reads "แหล่งที่มีชื่ออยู่ใน
# บัญชีรายชื่อเบื้องต้น (Tentative List)" in prose but "Tentative List" in the numbered list.
CHECKED_DATASETS = (
    "แหล่งศิลปกรรม แหล่งธรรมชาติ แหล่งมรดกโลก "
    "แหล่งที่มีชื่ออยู่ในบัญชีรายชื่อเบื้องต้น (Tentative List) "
    "พื้นที่คุ้มครอง และผังภูมินิเวศ"
)

OPINION_LEAD_IN = f"ทั้งนี้ {OFFICE} มีข้อคิดเห็นประกอบการพิจารณาดำเนินโครงการ ดังนี้"

# Present near-verbatim in six of the seven reference letters, so it is a template
# sentence rather than something the model should be asked to reinvent each time.
# The survey-QR sentence that follows it in the originals is dropped: it belongs to
# สผ.'s own correspondence, not to an analysis this API hands back.
STANDING_ADVICE = (
    "อย่างไรก็ตามเพื่อความครบถ้วน ถูกต้อง และชัดเจนของข้อมูล "
    "ควรมีการสำรวจพื้นที่จริงร่วมกับการประสานสอบถามจากหน่วยงานที่เกี่ยวข้องในพื้นที่อีกทางหนึ่ง "
    "หากปรากฏในภายหลังตามสภาพข้อเท็จจริงของพื้นที่ว่ามีแหล่งธรรมชาติท้องถิ่น "
    "แหล่งศิลปกรรมอันควรอนุรักษ์ และพื้นที่อื่น ๆ ที่เกี่ยวข้อง "
    "ขอให้ประเมินผลกระทบที่เกิดจากโครงการฯ ทั้งในช่วงก่อสร้างและช่วงเปิดดำเนินการด้วย"
)

CLOSING = "จึงเรียนมาเพื่อโปรดพิจารณา"

# Leading list markers the model may add despite being told not to: an Arabic or Thai
# numeral with a dot or paren, or a bullet character. Stripped so the Thai numbering
# below is the only numbering in the output and can never disagree with itself.
LIST_MARKER = re.compile(r"^\s*(?:[\d๐-๙]+\s*[.)]|[-*•])\s*")


def project_name_phrase(project: AnalysisProject) -> str:
    """
    The project name as it reads after "โครงการ" in a sentence.

    Both worked examples in the spec already start `name` with "โครงการ", which would
    otherwise stutter into "...ของโครงการโครงการปรับปรุง...".
    """
    return project.name if project.name.startswith("โครงการ") else f"โครงการ{project.name}"


def buffer_phrase(project: AnalysisProject) -> str:
    """
    The radius actually inspected, in km, in Thai digits.

    Features can each carry their own `buffer_m` (a user may widen one beyond the
    legal default), so stating `default_buffer_m` alone would understate the scope
    of the check in the one sentence meant to state it precisely.
    """
    radii = {feature.buffer_m for feature in project.features if feature.buffer_m is not None}

    if not radii:
        radii = {project.default_buffer_m}

    smallest, largest = format_measure(min(radii) / 1000), format_measure(max(radii) / 1000)

    if smallest == largest:
        return f"ในระยะ {smallest} กิโลเมตร"

    return f"ในระยะ {smallest} ถึง {largest} กิโลเมตร"


def build_opening(request: AnalysisRequest) -> str:
    """
    The CRAFT "ส่วนนำ": what the project is, where it is, and how far out we checked.

    Written in code rather than by the model because it restates the project type,
    the agency, and the buffer — three facts a reviewer cross-checks against the
    covering letter, and three the model has no reason to be trusted to restate.
    """
    project = request.project
    agency = project.agency or DEFAULT_AGENCY

    return (
        f"{OFFICE}ได้ตรวจสอบข้อมูลพื้นที่ศึกษาของ{project_name_phrase(project)} "
        f"ซึ่งเป็นโครงการประเภท{project.project_type} - {project.project_sub_type} "
        f"ตั้งอยู่ในพื้นที่{format_project_area(project)}\n\n"
        f"เพื่อให้{agency}ได้รับข้อมูลที่ครอบคลุมประเด็นที่อาจเกิดผลกระทบ"
        "ต่อสิ่งแวดล้อมธรรมชาติและศิลปกรรม และแหล่งมรดกโลกอย่างรอบด้าน "
        f"จึงได้ตรวจสอบข้อมูลที่เกี่ยวข้องทั้งหมด ได้แก่ {CHECKED_DATASETS} "
        f"{buffer_phrase(project)}จากบริเวณพื้นที่โครงการฯ สรุปได้ ดังนี้"
    )


def build_totals(request: AnalysisRequest) -> str:
    return (
        "รวมแหล่งที่ได้รับผลกระทบในบริเวณพื้นที่ศึกษาโครงการฯ ทั้งสิ้น "
        f"จำนวน {format_count(request.summary.total_sites)} แห่ง"
    )


def format_opinions(text: str) -> str:
    """
    Number the model's opinion lines ๑. ๒. ๓., discarding any numbering it wrote itself.

    The model is asked for one point per line precisely so the numbering can be applied
    here: a reviewer who reads "ข้อ ๓" in a covering note has to find the same point at
    ๓ in the report, and a model that miscounts mid-list would break that quietly.
    """
    points = [
        stripped for line in text.splitlines() if (stripped := LIST_MARKER.sub("", line).strip())
    ]

    return "\n".join(
        f"{format_count(number)}. {point}" for number, point in enumerate(points, start=1)
    )


def build_report(request: AnalysisRequest, opinions: str) -> str:
    """
    Assemble the finished letter around the opinion points the model wrote.

    Everything except `opinions` is deterministic: counts and the total carry legal
    weight for the สผ. reviewer who copies them onward, and the standing advice and
    closing are template sentences the reference letters repeat unchanged.
    """
    sections = [
        build_opening(request),
        format_category_breakdown(request),
        build_totals(request),
    ]

    if opinions:
        sections += [OPINION_LEAD_IN, opinions]

    sections += [STANDING_ADVICE, CLOSING]

    return "\n\n".join(sections)
