from rag_gis_api.schemas.analysis import (
    AnalysisFeature,
    AnalysisProject,
    AnalysisRequest,
    CategorySummary,
    SiteImpact,
)
from rag_gis_api.services.analysis.thai_text import format_count

NO_LOCATION = "ไม่ทราบตำแหน่ง"
UNKNOWN_CATEGORY = "ไม่ทราบหมวด"

# The six datasets the CRAFT spec names, in the order the report lists them. Every one
# is printed on every report - "ไม่พบ<หมวด>" for a zero hit - because a สผ. reviewer
# reads a stated absence as a checked-and-clear result, while a missing line reads as
# a dataset nobody looked at.
CATEGORY_ORDER = (
    "แหล่งศิลปกรรม",
    "แหล่งธรรมชาติ",
    "แหล่งมรดกโลก",
    "Tentative List",
    "พื้นที่คุ้มครอง",
    "ผังภูมินิเวศ",
)

# ONEP's `category` strings are still unconfirmed against these display names, and สผ.'s
# own letters spell the same dataset several ways ("แหล่งศิลปกรรมอันควรอนุรักษ์",
# "แหล่งธรรมชาติท้องถิ่น"), so matching is by substring rather than equality. Longest
# alias wins, which is what keeps a combined "แหล่งมรดกโลกและบัญชีรายชื่อเบื้องต้น" from
# being filed under แหล่งมรดกโลก when it is really the Tentative List row.
CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "แหล่งศิลปกรรม": ("แหล่งศิลปกรรม", "ศิลปกรรม"),
    "แหล่งธรรมชาติ": ("แหล่งธรรมชาติ", "ธรรมชาติ"),
    "แหล่งมรดกโลก": ("แหล่งมรดกโลก", "มรดกโลก"),
    "Tentative List": ("บัญชีรายชื่อเบื้องต้น", "tentative list", "tentative"),
    "พื้นที่คุ้มครอง": ("พื้นที่คุ้มครอง", "พื้นที่อนุรักษ์", "คุ้มครอง"),
    "ผังภูมินิเวศ": ("ผังภูมินิเวศ", "ภูมินิเวศ"),
}


def resolve_category(value: str | None) -> str | None:
    """
    Map one ONEP `category` string onto a display name, or None when nothing matches.

    An unmatched category is never dropped: format_category_breakdown prints it as its
    own extra row, so a name ONEP spells in a way we did not anticipate still reaches
    the reviewer instead of vanishing into a "ไม่พบ" line that would be a lie.
    """
    if not value:
        return None

    haystack = value.casefold()
    matches = [
        (len(alias), display)
        for display, aliases in CATEGORY_ALIASES.items()
        for alias in aliases
        if alias.casefold() in haystack
    ]

    return max(matches)[1] if matches else None


def format_number(value: float) -> str:
    """
    Render a measurement for the LLM's context block: separators, at most 2 decimals.

    Arabic digits on purpose - this feeds the prompt, not the letter. Plain f-string
    `:g` flips to scientific notation around 1e6, routine for a GIS area in square
    metres, which would be fed to the LLM as ground truth in a form it misreads.
    """
    rounded = round(value, 2)

    if rounded == int(rounded):
        return f"{int(rounded):,}"

    return f"{rounded:,.2f}".rstrip("0").rstrip(".")


def format_location(province: str | None, district: str | None, tambon: str | None) -> str:
    parts = [part for part in (province, district, tambon) if part]

    return ", ".join(parts) if parts else NO_LOCATION


def format_project_area(project: AnalysisProject) -> str:
    """
    The provinces and districts the project sits in, for the opening paragraph.

    CRAFT asks the opening to state where the project is. A project can carry several
    features in different provinces (worked example 5.2 of the contract does), so this
    lists every distinct one rather than the first.
    """
    provinces = dict.fromkeys(
        feature.location.province for feature in project.features if feature.location.province
    )

    if not provinces:
        return NO_LOCATION

    return " ".join(f"จังหวัด{province}" for province in provinces)


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
        f"หน่วยงานเจ้าของโครงการ: {agency}\n"
        f"ประเภทโครงการหลัก - ย่อย: {project.project_type} - {project.project_sub_type}\n"
        f"พื้นที่ที่ตั้ง: {format_project_area(project)}\n"
        f"รัศมีตรวจสอบตามกฎหมาย: {format_number(project.default_buffer_m)} ม.\n"
        f"รูปที่วาด (ข้อมูล GIS):\n{features}"
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


def resolved_categories(request: AnalysisRequest) -> dict[str, CategorySummary]:
    """{display name: merged summary} for every category that resolved to a known name."""
    resolved: dict[str, CategorySummary] = {}

    for category in merge_categories(request.summary.by_category):
        display = resolve_category(category.category)

        if display is None:
            continue

        existing = resolved.get(display)

        if existing is None:
            resolved[display] = category
        else:
            # Two ONEP spellings of one dataset, e.g. "แหล่งธรรมชาติอันควรอนุรักษ์" and
            # "แหล่งธรรมชาติท้องถิ่น": one display row, one combined count.
            existing.site_count += category.site_count

    return resolved


def category_site_type_counts(sites: list[SiteImpact], category: str | None) -> dict[str, int]:
    """
    Count `sites[]` rows of one category, grouped by their most specific known type.

    Feeds the LLM the "ประเภทแหล่งน้ำ ๑๑ แห่ง / ประเภทถ้ำ ๑ แห่ง" distinction that สผ.'s
    own letters draw. Only as complete as `sites[]` itself, which may be truncated.
    """
    counts: dict[str, int] = {}

    for site in sites:
        if site.category != category:
            continue

        label = site.site_type or site.sub_category or "ไม่ทราบประเภท"
        counts[label] = counts.get(label, 0) + 1

    return counts


def format_category_line(index: int, name: str, site_count: int) -> str:
    """One numbered line of the count section, in the wording CRAFT's example shows."""
    # "ไม่พบTentative List" runs together in Thai, which has no inter-word space; a
    # Latin name needs the space back or the two words read as one token.
    lead = f"{format_count(index)}. "
    spacer = " " if name[:1].isascii() else ""

    if site_count == 0:
        return f"{lead}ไม่พบ{spacer}{name}"

    return f"{lead}พบ{spacer}{name} จำนวน {format_count(site_count)} แห่ง"


def format_category_breakdown(request: AnalysisRequest) -> str:
    """Numbered per-category counts, fixed order, "ไม่พบ..." for every zero hit."""
    resolved = resolved_categories(request)
    lines = [
        format_category_line(index, name, resolved[name].site_count if name in resolved else 0)
        for index, name in enumerate(CATEGORY_ORDER, start=1)
    ]

    # Categories ONEP sent that matched no display name — printed rather than dropped.
    extra = [
        category
        for category in merge_categories(request.summary.by_category)
        if resolve_category(category.category) is None
    ]

    for offset, category in enumerate(extra, start=len(CATEGORY_ORDER) + 1):
        name = category.category or UNKNOWN_CATEGORY
        lines.append(format_category_line(offset, name, category.site_count))

    return "\n".join(lines)


def format_category_context(request: AnalysisRequest) -> str:
    """
    The per-category counts as context for the LLM, with the site-type breakdown.

    Arabic digits and a flat shape on purpose: this is input the model reasons over,
    not text it should echo. The report body is assembled separately.
    """
    lines = []

    for category in merge_categories(request.summary.by_category):
        if not category.site_count:
            continue

        display = resolve_category(category.category) or category.category or UNKNOWN_CATEGORY
        counts = category_site_type_counts(request.sites, category.category)
        breakdown = ", ".join(f"{label} {count} แห่ง" for label, count in counts.items())

        line = f"- {display}: {category.site_count} แห่ง"
        lines.append(f"{line} (แยกตามประเภท: {breakdown})" if breakdown else line)

    if not lines:
        return "(ไม่พบแหล่งในหมวดใด)"

    if request.sites_truncated:
        # Without this the model reads "88 แห่ง (แยกตามประเภท: วัด 1 แห่ง)" as a
        # contradiction and tends to talk itself into explaining the gap.
        lines.append(
            "(หมายเหตุ: ตัวเลขแยกตามประเภทนับจากรายการแหล่งที่ส่งมาซึ่งถูกตัดให้สั้นลง "
            "จึงน้อยกว่าจำนวนจริงในหมวดนั้น ให้ยึดจำนวนรวมของหมวดเป็นหลัก)"
        )

    return "\n".join(lines)


def format_guidance_context(request: AnalysisRequest) -> str:
    """
    ONEP's own `guidance` text per category, as background for the LLM.

    Fed as input rather than printed verbatim: สผ.'s real letters carry no bracketed
    citation numbers, and the canned text is exactly what ONEP flagged as reading
    poorly. The model may draw on it, but the wording it produces is its own.
    """
    blocks = []

    for category in merge_categories(request.summary.by_category):
        if not category.site_count or not category.guidance:
            continue

        display = resolve_category(category.category) or category.category or UNKNOWN_CATEGORY
        block = f"{display}:\n{category.guidance}"

        if category.guidance_ref:
            block += f"\nอ้างอิง: {category.guidance_ref}"

        blocks.append(block)

    return "\n\n".join(blocks) if blocks else "(ONEP ไม่ได้ส่งแนวทางเพิ่มเติมมาสำหรับหมวดที่พบ)"
