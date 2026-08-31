from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.format_payload import resolve_category

# Enough to cover the site types one project realistically touches without turning
# retrieval into a scan of the whole corpus: the reference letters group their points
# into at most four themes, and each theme needs one query.
MAX_TYPE_QUERIES = 4


def site_type_themes(request: AnalysisRequest) -> list[str]:
    """
    The most common site types in `sites[]`, which is what the opinion points key on.

    สผ.'s letters organise their advice by what the site *is* — แหล่งน้ำ, วัด, ย่านชุมชนเก่า,
    เมืองเก่า — not by which dataset it came from, and the mitigation wording differs
    sharply between those. Retrieving per category alone would miss that split.
    """
    counts: dict[str, int] = {}

    for site in request.sites:
        label = site.site_type or site.sub_category

        if label:
            counts[label] = counts.get(label, 0) + 1

    ranked = sorted(counts, key=lambda label: counts[label], reverse=True)

    return ranked[:MAX_TYPE_QUERIES]


def build_rag_queries(request: AnalysisRequest) -> list[str]:
    """
    Turn one ONEP payload into several retrieval queries against the legal corpus.

    One query per impacted category and per recurring site type, rather than a single
    combined one: a lone query mixing "แหล่งศิลปกรรม" and "แหล่งธรรมชาติ" retrieves the
    chunks that sit between the two topics and nothing that is squarely about either.
    """
    project = request.project
    subject = f"โครงการ{project.project_type} {project.project_sub_type}"

    queries = [f"แนวทางการประเมินและลดผลกระทบสิ่งแวดล้อมของ{subject}"]

    # Only categories actually hit: a zero-count row would steer retrieval toward
    # law about sites this project does not touch.
    categories = dict.fromkeys(
        resolve_category(category.category) or category.category
        for category in request.summary.by_category
        if category.category and category.site_count
    )

    queries += [f"ผลกระทบและมาตรการป้องกันแก้ไขต่อ{name}จาก{subject}" for name in categories]
    queries += [
        f"มาตรการลดผลกระทบต่อ{theme}จากการก่อสร้างถนนและสะพาน" for theme in site_type_themes(request)
    ]

    return queries
