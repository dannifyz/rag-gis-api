import re

from rag_gis_api.schemas.analysis import AnalysisProject, AnalysisRequest
from rag_gis_api.services.analysis.format_payload import (
    format_category_breakdown,
    format_project_area,
)
from rag_gis_api.services.analysis.thai_text import (
    format_count,
    format_measure,
    normalize_sara_am,
    thai_digits_in_prose,
)

OFFICE = "สำนักงานนโยบายและแผนทรัพยากรธรรมชาติและสิ่งแวดล้อม"
DEFAULT_AGENCY = "หน่วยงานเจ้าของโครงการ"

# Datasets named in the opening, in สผ. prose wording. Kept separate from CATEGORY_ORDER:
# prose reads "...บัญชีรายชื่อเบื้องต้น (Tentative List)" but the list reads "Tentative List".
CHECKED_DATASETS = (
    "แหล่งศิลปกรรม แหล่งธรรมชาติ แหล่งมรดกโลก "
    "แหล่งที่มีชื่ออยู่ในบัญชีรายชื่อเบื้องต้น (Tentative List) "
    "พื้นที่คุ้มครอง และผังภูมินิเวศ"
)

OPINION_LEAD_IN = f"ทั้งนี้ {OFFICE} มีข้อคิดเห็นประกอบการพิจารณาดำเนินโครงการ ดังนี้"

# Near-verbatim in six of seven reference letters, so it's a template, not model output.
# The survey-QR sentence that follows in the originals is dropped as สผ.-internal.
STANDING_ADVICE = (
    "อย่างไรก็ตามเพื่อความครบถ้วน ถูกต้อง และชัดเจนของข้อมูล "
    "ควรมีการสำรวจพื้นที่จริงร่วมกับการประสานสอบถามจากหน่วยงานที่เกี่ยวข้องในพื้นที่อีกทางหนึ่ง "
    "หากปรากฏในภายหลังตามสภาพข้อเท็จจริงของพื้นที่ว่ามีแหล่งธรรมชาติท้องถิ่น "
    "แหล่งศิลปกรรมอันควรอนุรักษ์ และพื้นที่อื่น ๆ ที่เกี่ยวข้อง "
    "ขอให้ประเมินผลกระทบที่เกิดจากโครงการฯ ทั้งในช่วงก่อสร้างและช่วงเปิดดำเนินการด้วย"
)

CLOSING = "จึงเรียนมาเพื่อโปรดพิจารณา"

# Leading list markers the model may add despite the prompt. Stripped so the Thai
# numbering below is the only numbering and can never disagree with itself.
LIST_MARKER = re.compile(r"^\s*(?:[\d๐-๙]+\s*[.)]|[-*•])\s*")

# Below this a line can't be a real point (impact + mitigation never fits in a few
# dozen chars). Drops the "ข้อคิดเห็น" heading the model echoes, which would else be ๑.
MIN_POINT_CHARS = 40


def project_name_phrase(project: AnalysisProject) -> str:
    """
    The project name as it reads after "โครงการ", avoiding "โครงการโครงการ..." when
    `name` already starts with "โครงการ".
    """
    return project.name if project.name.startswith("โครงการ") else f"โครงการ{project.name}"


def buffer_phrase(project: AnalysisProject) -> str:
    """
    The radius actually inspected, in km, in Thai digits.

    Features can each carry their own `buffer_m`, so `default_buffer_m` alone would
    understate the scope.
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

    In code, not model output: the project type, agency, and buffer are facts a
    reviewer cross-checks against the covering letter.
    """
    project = request.project
    agency = project.agency or DEFAULT_AGENCY

    opening = (
        f"{OFFICE}ได้ตรวจสอบข้อมูลพื้นที่ศึกษาของ{project_name_phrase(project)} "
        f"ซึ่งเป็นโครงการประเภท{project.project_type} - {project.project_sub_type} "
        f"ตั้งอยู่ในพื้นที่{format_project_area(project)}\n\n"
        f"เพื่อให้{agency}ได้รับข้อมูลที่ครอบคลุมประเด็นที่อาจเกิดผลกระทบ"
        "ต่อสิ่งแวดล้อมธรรมชาติและศิลปกรรม และแหล่งมรดกโลกอย่างรอบด้าน "
        f"จึงได้ตรวจสอบข้อมูลที่เกี่ยวข้องทั้งหมด ได้แก่ {CHECKED_DATASETS} "
        f"{buffer_phrase(project)} จากบริเวณพื้นที่โครงการฯ สรุปได้ ดังนี้"
    )

    # ONEP sends Arabic digits; converted here, not at the source, so the stored
    # payload keeps ONEP's own spelling.
    return thai_digits_in_prose(opening)


def build_totals(request: AnalysisRequest) -> str:
    return (
        "รวมแหล่งที่ได้รับผลกระทบในบริเวณพื้นที่ศึกษาโครงการฯ ทั้งสิ้น "
        f"จำนวน {format_count(request.summary.total_sites)} แห่ง"
    )


def format_opinions(text: str) -> str:
    """
    Number the model's opinion lines ๑. ๒. ๓., discarding any numbering it wrote itself.

    Applied here, not by the model, so the count can't drift. Figures are converted to
    Thai digits here too, so a model reverting to Arabic can't leave this paragraph
    looking unlike the rest.
    """
    points = [
        stripped
        for line in text.splitlines()
        if len(stripped := LIST_MARKER.sub("", line).strip()) >= MIN_POINT_CHARS
    ]

    return "\n".join(
        f"{format_count(number)}. {normalize_sara_am(thai_digits_in_prose(point))}"
        for number, point in enumerate(points, start=1)
    )


def build_report(request: AnalysisRequest, opinions: str) -> str:
    """
    Assemble the finished letter around the opinion points the model wrote.

    Everything except `opinions` is deterministic: counts carry legal weight, and the
    standing advice and closing are template sentences.
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
