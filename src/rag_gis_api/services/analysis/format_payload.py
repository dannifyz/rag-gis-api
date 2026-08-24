from rag_gis_api.schemas.analysis import (
    AnalysisFeature,
    AnalysisRequest,
    CategorySummary,
    SiteImpact,
)

NO_LOCATION = "ไม่ทราบตำแหน่ง"
UNKNOWN_CATEGORY = "ไม่ทราบหมวด"

# Inferred from the spec doc's `category` field examples (introduced with "เช่น" / "e.g." —
# not marked as the complete, authoritative list) and from a screenshot of ONEP's own
# "วิเคราะห์โดย AI" tab, which explicitly states "ไม่พบ..." for every category with zero
# hits rather than omitting it. Confirm this list/order with ONEP before relying on it:
# a category ONEP spells differently is reported as absent here *and* again as an extra.
FIXED_CATEGORIES = [
    "แหล่งธรรมชาติ",
    "แหล่งศิลปกรรม",
    "แหล่งมรดกโลก",
    "พื้นที่อนุรักษ์/คุ้มครอง",
    "ผังพื้นที่อนุรักษ์-ภูมินิเวศ",
]


def format_number(value: float) -> str:
    """
    Render a measurement for Thai prose: thousands separators, at most 2 decimals.

    Plain f-string `:g` flips to scientific notation around 1e6 — routine for a GIS
    area in square metres — which reads as broken text mid-sentence and would be fed
    to the LLM as ground truth.
    """
    rounded = round(value, 2)

    if rounded == int(rounded):
        return f"{int(rounded):,}"

    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def format_location(province: str | None, district: str | None, tambon: str | None) -> str:
    parts = [part for part in (province, district, tambon) if part]

    return ", ".join(parts) if parts else NO_LOCATION


def format_feature(feature: AnalysisFeature, index: int) -> str:
    label = feature.label or f"รูปที่ {index}"
    kind = {"point": "จุด", "line": "เส้น", "polygon": "พื้นที่"}[feature.geom_type]
    buffer_note = (
        f"รัศมีตรวจสอบ {format_number(feature.buffer_m)} ม."
        f" ({'ตามกฎหมาย' if feature.is_legal else 'ผู้ใช้กำหนดเอง'})"
        if feature.buffer_m is not None
        else "ไม่มีรัศมีตรวจสอบ"
    )

    # Keyed off geom_type, not "whichever field is non-null first": a polygon may carry
    # both a perimeter length and an area, and for a polygon the area is the real metric.
    if feature.geom_type == "polygon" and feature.area_sqm is not None:
        size_note = f"พื้นที่ {format_number(feature.area_sqm)} ตร.ม."
    elif feature.geom_type == "line" and feature.length_m is not None:
        size_note = f"ยาว {format_number(feature.length_m)} ม."
    elif feature.length_m is not None:
        size_note = f"ยาว {format_number(feature.length_m)} ม."
    elif feature.area_sqm is not None:
        size_note = f"พื้นที่ {format_number(feature.area_sqm)} ตร.ม."
    else:
        size_note = None

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
        f"รัศมีตรวจสอบตามกฎหมาย: {format_number(project.default_buffer_m)} ม.\n"
        f"รูปที่วาด:\n{features}"
    )


def format_overlap(site: SiteImpact) -> str | None:
    """
    The magnitude of the impact — how much of the site actually falls in the buffer.

    Distance alone can't distinguish a project clipping a wetland's edge from one
    covering 40% of it, so these go into the prompt rather than being dropped.
    A 0/None value means "not applicable to this geometry kind" per the spec.
    """
    parts = []

    if site.overlap_area_sqm:
        parts.append(f"พื้นที่ทับซ้อน {format_number(site.overlap_area_sqm)} ตร.ม.")

    if site.overlap_length_m:
        parts.append(f"ความยาวทับซ้อน {format_number(site.overlap_length_m)} ม.")

    if site.overlap_percentage:
        parts.append(f"คิดเป็น {format_number(site.overlap_percentage)}% ของแหล่ง")

    return ", ".join(parts) if parts else None


def format_site(site: SiteImpact) -> str:
    name = site.site_name or "(ไม่มีชื่อ)"
    kind = site.site_type or site.category or "ไม่ทราบประเภท"
    location = format_location(site.province, site.district, site.tambon)
    # Rounded before comparing: a computed distance can land on float residue like
    # 1e-08, which is an overlap in practice but would print as "ห่าง 0 ม.".
    distance = (
        "อยู่ในพื้นที่โครงการ"
        if round(site.closest_distance_m, 1) == 0
        else f"ห่าง {format_number(site.closest_distance_m)} ม."
    )

    parts = [f"- {name} ({kind}) ที่ {location} — {distance}"]

    overlap = format_overlap(site)

    if overlap:
        parts.append(overlap)

    if site.geometry_count > 1:
        parts.append(f"ประกอบด้วย {site.geometry_count} ชิ้น")

    if site.provincial_heritage_be:
        parts.append(f"ขึ้นทะเบียนมรดกจังหวัด พ.ศ. {site.provincial_heritage_be}")

    return ", ".join(parts)


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


def merge_categories(by_category: list[CategorySummary]) -> list[CategorySummary]:
    """
    Collapse repeated `category` names into one row, preserving first-seen order.

    The breakdown and the guidance section must not disagree about the same
    category — one reading a dict that keeps the last duplicate while the other
    walks the raw list would print one count above two contradictory guidances.
    """
    merged: dict[str | None, CategorySummary] = {}

    for category in by_category:
        existing = merged.get(category.category)

        if existing is None:
            merged[category.category] = category.model_copy(deep=True)
            continue

        existing.site_count += category.site_count

        for field in ("guidance", "guidance_ref"):
            new_value = getattr(category, field)
            old_value = getattr(existing, field)

            if new_value and new_value not in (old_value or ""):
                setattr(existing, field, f"{old_value}\n{new_value}" if old_value else new_value)

    return list(merged.values())


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
    # Matched on the raw category value, not the display name: a null category
    # renders as "ไม่ทราบหมวด" but still has to be looked up as None.
    counts = category_site_type_counts(sites, summary.category)

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
    categories = merge_categories(request.summary.by_category)
    by_name = {category.category: category for category in categories if category.category}
    lines = []

    for index, name in enumerate(FIXED_CATEGORIES, start=1):
        lines.append(
            format_category_line(
                index, name, by_name.get(name), request.sites, request.sites_truncated
            )
        )

    # Categories ONEP sent that fall outside our assumed fixed list — never silently drop them.
    extra = [category for category in categories if category.category not in FIXED_CATEGORIES]

    for offset, category in enumerate(extra, start=len(FIXED_CATEGORIES) + 1):
        name = category.category or UNKNOWN_CATEGORY
        lines.append(
            format_category_line(offset, name, category, request.sites, request.sites_truncated)
        )

    return "\n".join(lines)


def format_guidance_section(request: AnalysisRequest) -> str:
    """
    ONEP's own `guidance` text per category, verbatim, with its `guidance_ref` lines
    numbered as [1], [2], ... — reproduced as-is rather than paraphrased, since an LLM
    rewording it could silently break citation numbers meaningful to ONEP's reviewers.

    Numbering runs continuously across categories so two different sources can never
    share a number within one report.
    """
    blocks = []
    next_ref = 1

    for category in merge_categories(request.summary.by_category):
        if not category.site_count or not category.guidance:
            continue

        name = category.category or UNKNOWN_CATEGORY
        block = f"{name}:\n{category.guidance}"

        if category.guidance_ref:
            refs = [line for line in category.guidance_ref.splitlines() if line.strip()]
            numbered = "\n".join(
                f"[{number}] {line}" for number, line in enumerate(refs, start=next_ref)
            )
            next_ref += len(refs)
            block += f"\n{numbered}"

        blocks.append(block)

    return "\n\n".join(blocks) if blocks else "(ไม่มีข้อมูลแนวทางเพิ่มเติมจาก ONEP สำหรับหมวดที่พบ)"
