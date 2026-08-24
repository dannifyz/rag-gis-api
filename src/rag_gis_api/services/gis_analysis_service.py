from rag_gis_api.repositories import vector_repository
from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.build_messages import build_messages
from rag_gis_api.services.analysis.build_rag_query import build_rag_query
from rag_gis_api.services.analysis.build_report import build_skeleton, project_name_phrase
from rag_gis_api.services.llm_service import get_llm

RETRIEVE_LIMIT = 5


class EmptySummaryError(RuntimeError):
    """The LLM returned no closing paragraph, so the report would be incomplete."""


def no_sites_summary(request: AnalysisRequest) -> str:
    return (
        f"จากการตรวจสอบพื้นที่{project_name_phrase(request.project)} "
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

    Raises EmptySummaryError when the LLM produces nothing: the skeleton alone
    would still be non-empty, so without this an incomplete report would be
    delivered as a 200 instead of a retryable failure.
    """
    if request.summary.total_sites == 0:
        return no_sites_summary(request)

    skeleton = build_skeleton(request)
    legal_chunks = await vector_repository.search_chunks(build_rag_query(request), RETRIEVE_LIMIT)
    response = await get_llm().ainvoke(build_messages(request, skeleton, legal_chunks))
    closing = response.text.strip()

    if not closing:
        raise EmptySummaryError("LLM returned an empty closing paragraph")

    return f"{skeleton}\n\n{closing}"
