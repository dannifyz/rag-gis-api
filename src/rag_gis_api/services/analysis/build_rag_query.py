from rag_gis_api.schemas.analysis import AnalysisRequest


def build_rag_query(request: AnalysisRequest) -> str:
    """
    Turn the ONEP payload into one retrieval query for the legal-document corpus.

    Combines the project type with every impacted category so the retrieved
    chunks are grounded in this specific project, not just its type.
    """
    project = request.project
    # Only categories actually hit: a zero-count row would steer retrieval toward
    # law about sites this project does not touch.
    categories = [
        category.category
        for category in request.summary.by_category
        if category.category and category.site_count
    ]

    # Falls back to the site types themselves, then to a bare type-only query —
    # never to wording that claims nothing was found, which is reached only when
    # sites *were* found (the caller short-circuits total_sites == 0 first).
    if not categories:
        categories = [site.site_type for site in request.sites if site.site_type]

    query = (
        f"ผลกระทบทางกฎหมายและแนวทางปฏิบัติของโครงการประเภท {project.project_type} "
        f"({project.project_sub_type})"
    )

    if categories:
        query += f" ต่อ {', '.join(dict.fromkeys(categories))}"

    return query
