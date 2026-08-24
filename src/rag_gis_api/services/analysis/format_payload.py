from rag_gis_api.schemas.analysis import (
    AnalysisFeature,
    AnalysisRequest,
    CategorySummary,
    SiteImpact,
)

NO_LOCATION = "ไม่ทราบตำแหน่ง"

# Inferred from the spec doc's `category` field examples (introduced with "เช่น" / "e.g." —
# not marked as the complete, authoritative list) and from a screenshot of ONEP's own
# "วิเคราะห์โดย AI" tab, which explicitly states "ไม่พบ..." for every category with zero
# hits rather than omitting it. Confirm this list/order with ONEP before relying on it.
FIXED_CATEGORIES = [
    "แหล่งธรรมชาติ",
    "แหล่งศิลปกรรม",
    "แหล่งมรดกโลก",
    "พื้นที่อนุรักษ์/คุ้มครอง",
    "ผังพื้นที่อนุรักษ์-ภูมินิเวศ",
]


def format_location(province: str | None, district: str | None, tambon: str | None) -> str:
    parts = [part for part in (province, district, tambon) if part]

    return ", ".join(parts) if parts else NO_LOCATION


def format_feature(feature: AnalysisFeature, index: int) -> str:
    label = feature.label or f"รูปที่ {index}"
    kind = {"point": "จุด", "line": "เส้น", "polygon": "พื้นที่"}[feature.geom_type]
    buffer_note = (
        f"รัศมีตรวจสอบ {feature.buffer_m:g} ม. ({'ตามกฎหมาย' if feature.is_legal else 'ผู้ใช้กำหนดเอง'})"
        if feature.buffer_m is not None
        else "ไม่มีรัศมีตรวจสอบ"
    )
    size_note = (
        f"ยาว {feature.length_m:g} ม."
        if feature.length_m is not None
        else f"พื้นที่ {feature.area_sqm:g} ตร.ม."
        if feature.area_sqm is not None
        else None
    )
    location = format_location(
        feature.location.province, feature.location.district, feature.location.tambon
    )

    parts = [f"- {label} ({kind}) ที่ {location}"]

    if size_note:
        parts.append(size_note)

    parts.append(f"— {buffer_note}")

    return " ".join(parts)


def format_project(request: AnalysisRequest) -> str:
    project = request.project
    agency = project.agency or "ผู้ใช้ทั่วไป (guest)"
    features = "\n".join(
        format_feature(feature, index) for index, feature in enumerate(project.features, start=1)
    )

    return (
        f"ชื่อโครงการ: {project.name}\n"
        f"หน่วยงาน: {agency}\n"
        f"ประเภทโครงการ: {project.project_type} / {project.project_sub_type}\n"
        f"รัศมีตรวจสอบตามกฎหมาย: {project.default_buffer_m:g} ม.\n"
        f"รูปที่วาด:\n{features}"
    )


def format_site(site: SiteImpact) -> str:
    name = site.site_name or "(ไม่มีชื่อ)"
    kind = site.site_type or site.category or "ไม่ทราบประเภท"
    location = format_location(site.province, site.district, site.tambon)
    distance = (
        "อยู่ในพื้นที่โครงการ" if site.closest_distance_m == 0 else f"ห่าง {site.closest_distance_m:g} ม."
    )

    return f"- {name} ({kind}) ที่ {location} — {distance}"


def format_sites(request: AnalysisRequest) -> str:
    if request.summary.total_sites == 0:
        return "(ไม่พบแหล่งที่ได้รับผลกระทบ)"

    lines = [format_site(site) for site in request.sites]

    if request.sites_truncated:
        lines.append(
            f"(หมายเหตุ: แสดงเฉพาะ {len(request.sites)} แหล่งที่ใกล้ที่สุด "
            f"จากทั้งหมด {request.sites_total} แหล่ง)"
        )

    return "\n".join(lines)


def category_site_type_counts(sites: list[SiteImpact], category: str | None) -> dict[str, int]:
    """
    Count `sites[]` rows of one category, grouped by their most specific known type.

    Powers the "* น้ำตก 1 แห่ง / * แหล่งน้ำ 90 แห่ง"-style sub-bullets. Only as complete
    as `sites[]` itself — see the truncation note appended in `format_category_line`.
    """
    counts: dict[str, int] = {}

    for site in sites:
        if site.category != category:
            continue

        label = site.site_type or site.sub_category or "ไม่ทราบประเภท"
        counts[label] = counts.get(label, 0) + 1

    return counts


def format_category_line(
    index: int,
    name: str,
    summary: CategorySummary | None,
    sites: list[SiteImpact],
    sites_truncated: bool,
) -> str:
    if summary is None or summary.site_count == 0:
        return f"{index}. ไม่พบ{name}"

    header = f"{index}. พบ{name} {summary.site_count} แห่ง"
    counts = category_site_type_counts(sites, name)

    if not counts:
        # sites[] was truncated away entirely, or every row lacked a known type/name.
        return header

    breakdown = "\n".join(f"   * {label} {count} แห่ง" for label, count in counts.items())
    block = f"{header} ประกอบด้วย\n{breakdown}"

    if sites_truncated:
        block += "\n   (หมายเหตุ: รายการแหล่งถูกตัด จำนวนข้างต้นอาจไม่ครบทุกแหล่งในหมวดนี้)"

    return block


def format_category_breakdown(request: AnalysisRequest) -> str:
    """Numbered per-category breakdown, fixed category order, 'ไม่พบ...' for zero hits."""
    by_name = {
        category.category: category for category in request.summary.by_category if category.category
    }
    lines = []

    for index, name in enumerate(FIXED_CATEGORIES, start=1):
        summary = by_name.get(name)
        lines.append(
            format_category_line(index, name, summary, request.sites, request.sites_truncated)
        )

    # Categories ONEP sent that fall outside our assumed fixed list — never silently drop them.
    extra = [
        category
        for category in request.summary.by_category
        if category.category not in FIXED_CATEGORIES
    ]

    for offset, category in enumerate(extra, start=len(FIXED_CATEGORIES) + 1):
        name = category.category or "ไม่ทราบหมวด"
        lines.append(
            format_category_line(offset, name, category, request.sites, request.sites_truncated)
        )

    return "\n".join(lines)


def format_guidance_section(request: AnalysisRequest) -> str:
    """
    ONEP's own `guidance` text per category, verbatim, with its `guidance_ref` lines
    numbered directly underneath as [1], [2], ... — reproduced as-is rather than
    paraphrased, since an LLM rewording it could silently break citation numbers that
    are meaningful to ONEP's reviewers.
    """
    blocks = []

    for category in request.summary.by_category:
        if not category.site_count or not category.guidance:
            continue

        name = category.category or "ไม่ทราบหมวด"
        block = f"{name}:\n{category.guidance}"

        if category.guidance_ref:
            refs = [line for line in category.guidance_ref.splitlines() if line.strip()]
            numbered = "\n".join(f"[{n}] {line}" for n, line in enumerate(refs, start=1))
            block += f"\n{numbered}"

        blocks.append(block)

    return "\n\n".join(blocks) if blocks else "(ไม่มีข้อมูลแนวทางเพิ่มเติมจาก ONEP สำหรับหมวดที่พบ)"
