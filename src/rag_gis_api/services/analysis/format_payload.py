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

# Up to this many sites of one type, a point may name each; past it the group is named
# collectively. All-or-nothing per group, else it reads as สผ. weighting sites unequally.
# Per site_type, not category: a project can touch 86 waterways and one still-nameable cave.
NAME_LIMIT = 2

NAME_ALLOWED = "ระบุชื่อแหล่งได้"
NAME_DENIED = "ไม่ต้องไล่ชื่อแหล่ง ให้กล่าวรวมเป็นประเภท"

# The six CRAFT datasets, in report order. Every one is printed even at zero ("ไม่พบ<หมวด>"):
# a stated absence reads as checked-and-clear, a missing line as a dataset nobody checked.
CATEGORY_ORDER = (
    "แหล่งศิลปกรรม",
    "แหล่งธรรมชาติ",
    "แหล่งมรดกโลก",
    "Tentative List",
    "พื้นที่คุ้มครอง",
    "ผังภูมินิเวศ",
)

# ONEP spells each dataset several ways, so matching is by substring, not equality.
# Longest alias wins, so "แหล่งมรดกโลกและบัญชีรายชื่อเบื้องต้น" files under Tentative List.
CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "แหล่งศิลปกรรม": ("แหล่งศิลปกรรม", "ศิลปกรรม"),
    "แหล่งธรรมชาติ": ("แหล่งธรรมชาติ", "ธรรมชาติ"),
    "แหล่งมรดกโลก": ("แหล่งมรดกโลก", "มรดกโลก"),
    "Tentative List": ("บัญชีรายชื่อเบื้องต้น", "tentative list", "tentative"),
    "พื้นที่คุ้มครอง": ("พื้นที่คุ้มครอง", "พื้นที่อนุรักษ์", "คุ้มครอง"),
    # ONEP sends "ผังพื้นที่อนุรักษ์-ภูมินิเวศ", which contains the longer "พื้นที่อนุรักษ์";
    # without the full string here it misfiles under พื้นที่คุ้มครอง.
    "ผังภูมินิเวศ": ("ผังพื้นที่อนุรักษ์-ภูมินิเวศ", "ผังพื้นที่อนุรักษ์", "ผังภูมินิเวศ", "ภูมินิเวศ"),
}


def resolve_category(value: str | None) -> str | None:
    """
    Map one ONEP `category` string onto a display name, or None when nothing matches.

    An unmatched category is not dropped: format_category_breakdown prints it as an
    extra row rather than let it vanish into a false "ไม่พบ" line.
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

    Arabic digits on purpose (feeds the prompt, not the letter). Avoids `:g`, which
    flips to scientific notation around 1e6 — routine for a GIS area, and misread.
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
    The provinces the project sits in, for the opening paragraph.

    A project can carry features in different provinces, so this lists every distinct
    one rather than the first.
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

    # Keyed off geom_type: a polygon carries both length and area, and area is its metric.
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
    The magnitude of the impact — how much of the site falls in the buffer.

    Distance alone can't tell a clipped edge from a 40% overlap. A 0/None value means
    "not applicable to this geometry kind" per the spec.
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
    # Rounded before comparing: float residue like 1e-08 is an overlap but prints as "0 ม.".
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


def site_group_key(site: SiteImpact) -> tuple[str | None, str]:
    """The (category, type) pair a site is counted and named under."""
    return site.category, site.site_type or site.sub_category or "ไม่ทราบประเภท"


def naming_verdicts(request: AnalysisRequest) -> dict[tuple[str | None, str], bool]:
    """Which (category, type) groups are small enough for the prose to name."""
    counts: dict[tuple[str | None, str], int] = {}

    for site in request.sites:
        key = site_group_key(site)
        counts[key] = counts.get(key, 0) + 1

    totals = {
        category.category: category.site_count
        for category in merge_categories(request.summary.by_category)
    }

    # A truncated sites[] makes each count a floor, so a small-looking group in an
    # oversized category isn't proven small.
    return {
        (category, label): count <= NAME_LIMIT
        and not (request.sites_truncated and totals.get(category, count) > NAME_LIMIT)
        for (category, label), count in counts.items()
    }


def format_site_group(label: str, sites: list[SiteImpact]) -> str:
    """
    One aggregate line standing in for a group with too many sites to name.

    Names are withheld from the model, not just forbidden: handed all 52 waterway names
    despite the prompt, the model listed eight. What it isn't given, it can't copy out.
    """
    provinces = " ".join(dict.fromkeys(site.province for site in sites if site.province))
    inside = any(round(site.closest_distance_m, 1) == 0 for site in sites)
    nearest = min(site.closest_distance_m for site in sites)

    parts = [f"- {label} (พบหลายแห่ง) ในพื้นที่ {provinces or NO_LOCATION}"]

    # No count, deliberately: an earlier "ตัดผ่าน 16 แห่ง" got printed against a count
    # section saying 52. Distances are safe to hand over; counts belong to that section.
    if inside:
        parts.append("มีบางแห่งที่แนวเส้นทางโครงการตัดผ่านหรืออยู่ในพื้นที่โครงการ")
    else:
        parts.append(f"ใกล้ที่สุดห่าง {format_number(nearest)} ม.")

    parts.append("(ไม่ส่งรายชื่อและจำนวนรายแหล่งของกลุ่มนี้มาให้)")

    return ", ".join(parts)


def format_sites(request: AnalysisRequest) -> str:
    """
    The site detail block, with over-sized groups collapsed to one aggregate line.

    Groups keep the position of their first member so the whole block stays in
    ONEP's nearest-first order.
    """
    if request.summary.total_sites == 0:
        return "(ไม่พบแหล่งที่ได้รับผลกระทบ)"

    verdicts = naming_verdicts(request)
    lines: list[str] = []
    groups: dict[tuple[str | None, str], list[SiteImpact]] = {}
    slots: dict[tuple[str | None, str], int] = {}

    for site in request.sites:
        key = site_group_key(site)

        if verdicts[key]:
            lines.append(format_site(site))
            continue

        if key not in groups:
            groups[key] = []
            slots[key] = len(lines)
            lines.append("")

        groups[key].append(site)

    for key, members in groups.items():
        lines[slots[key]] = format_site_group(key[1], members)

    if request.sites_truncated:
        lines.append(
            f"(หมายเหตุ: แสดงเฉพาะ {len(request.sites)} แหล่งที่ใกล้ที่สุด "
            f"จากทั้งหมด {request.sites_total} แหล่ง)"
        )

    return "\n".join(lines)


def merge_categories(by_category: list[CategorySummary]) -> list[CategorySummary]:
    """
    Collapse repeated `category` names into one row, preserving first-seen order.

    So the breakdown and guidance sections can't disagree about the same category.
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
            # Two ONEP spellings of one dataset: one display row, one combined count.
            existing.site_count += category.site_count

    return resolved


def category_site_type_counts(sites: list[SiteImpact], category: str | None) -> dict[str, int]:
    """
    Count `sites[]` rows of one category, grouped by their most specific known type.

    Feeds the LLM the per-type distinction สผ. letters draw. Only as complete as
    `sites[]`, which may be truncated.
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
    # "ไม่พบTentative List" runs together; a Latin name needs the space restored.
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

    Each type carries its naming verdict in brackets, so the model sees why a group
    arrived without names instead of reading the gap as missing data. Arabic digits
    on purpose: input the model reasons over, not text to echo.
    """
    verdicts = naming_verdicts(request)
    lines = []

    for category in merge_categories(request.summary.by_category):
        if not category.site_count:
            continue

        display = resolve_category(category.category) or category.category or UNKNOWN_CATEGORY
        counts = category_site_type_counts(request.sites, category.category)
        breakdown = ", ".join(
            f"{label} {count} แห่ง "
            f"[{NAME_ALLOWED if verdicts.get((category.category, label)) else NAME_DENIED}]"
            for label, count in counts.items()
        )

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

    Fed as input, not printed verbatim: the canned text is what ONEP flagged as
    reading poorly, so the model rewords it.
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
