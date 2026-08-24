from rag_gis_api.schemas.analysis import AnalysisRequest


def build_rag_query(request: AnalysisRequest) -> str:
    """
    Turn the ONEP payload into one retrieval query for the legal-document corpus.

    Combines the project type with every impacted category so the retrieved
    chunks are grounded in this specific project, not just its type.
    """
    project = request.project
    categories = [
        category.category for category in request.summary.by_category if category.category
    ]
    categories_text = ", ".join(dict.fromkeys(categories)) if categories else "ไม่พบแหล่งที่ได้รับผลกระทบ"

    return (
        f"ผลกระทบทางกฎหมายและแนวทางปฏิบัติของโครงการประเภท {project.project_type} "
        f"({project.project_sub_type}) ต่อ {categories_text}"
    )
