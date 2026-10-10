from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.format_payload import resolve_category

# สผ. letters group their points into at most four themes; one query per theme.
MAX_TYPE_QUERIES = 4


def site_type_themes(request: AnalysisRequest) -> list[str]:
    """
    The most common site types in `sites[]`, which is what the opinion points key on.

    สผ. advice is organised by what the site *is* (แหล่งน้ำ, วัด, ย่านชุมชนเก่า), not by
    dataset, and mitigation wording differs sharply between them.
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

    One query per impacted category and site type: a combined query mixing topics
    retrieves chunks between them and nothing squarely about either.
    """
    project = request.project
    subject = f"โครงการ{project.project_type} {project.project_sub_type}"

    queries = [f"แนวทางการประเมินและลดผลกระทบสิ่งแวดล้อมของ{subject}"]

    # Only categories actually hit; a zero-count row would skew retrieval.
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
