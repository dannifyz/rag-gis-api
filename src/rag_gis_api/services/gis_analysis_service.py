from rag_gis_api.repositories import vector_repository
from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.build_messages import build_messages
from rag_gis_api.services.analysis.build_rag_query import build_rag_query
from rag_gis_api.services.analysis.build_report import build_skeleton
from rag_gis_api.services.llm_service import get_llm

RETRIEVE_LIMIT = 5


def no_sites_summary(request: AnalysisRequest) -> str:
    return (
        f'จากการตรวจสอบพื้นที่โครงการ "{request.project.name}" '
        "ไม่พบแหล่งธรรมชาติ แหล่งศิลปกรรม พื้นที่อนุรักษ์ หรือแหล่งอื่นที่ต้องพิจารณา "
        "อยู่ภายในรัศมีตรวจสอบตามที่กฎหมายกำหนดสำหรับโครงการประเภทนี้"
    )


async def summarize_impact(request: AnalysisRequest) -> str:
    """
    Turn one ONEP impact-analysis payload into a Thai plain-text summary.

    The opening, category breakdown, and ONEP's own guidance/citations are
    assembled deterministically (`build_skeleton`) so counts and citation
    numbers can't drift; the LLM only adds a closing synthesis paragraph,
    grounded in the ingested legal corpus, on top of that fixed skeleton.
    """
    if request.summary.total_sites == 0:
        return no_sites_summary(request)

    skeleton = build_skeleton(request)
    legal_chunks = await vector_repository.search_chunks(build_rag_query(request), RETRIEVE_LIMIT)
    response = await get_llm().ainvoke(build_messages(request, skeleton, legal_chunks))
    closing = response.text.strip()

    return f"{skeleton}\n\n{closing}".strip()
