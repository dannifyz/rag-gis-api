import asyncio
from itertools import chain, zip_longest

from langchain_core.documents import Document

from rag_gis_api.repositories import vector_repository
from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.analysis.build_messages import build_messages
from rag_gis_api.services.analysis.build_rag_query import build_rag_queries
from rag_gis_api.services.analysis.build_report import build_report, format_opinions
from rag_gis_api.services.llm_service import get_llm

CHUNKS_PER_QUERY = 4
MAX_CHUNKS = 12


class EmptySummaryError(RuntimeError):
    """The LLM returned no opinion points, so the report would be incomplete."""


async def retrieve_legal_chunks(request: AnalysisRequest) -> list[Document]:
    """
    Run every retrieval query concurrently and merge the hits, best-first, without repeats.

    Merged round-robin rather than by concatenating each query's results: taking the
    first query's four chunks before the second query's first would let one theme fill
    the context window and leave the model with nothing to say about the others.
    """
    queries = build_rag_queries(request)
    results = await asyncio.gather(
        *(vector_repository.search_chunks(query, CHUNKS_PER_QUERY) for query in queries)
    )

    seen: set[str] = set()
    merged: list[Document] = []

    for chunk in chain.from_iterable(zip_longest(*results)):
        if chunk is None:
            continue

        key = chunk.metadata.get("id") or chunk.page_content

        if key in seen:
            continue

        seen.add(key)
        merged.append(chunk)

        if len(merged) == MAX_CHUNKS:
            break

    return merged


async def summarize_impact(request: AnalysisRequest) -> str:
    """
    Turn one ONEP impact-analysis payload into a Thai plain-text official-style report.
    """
    if request.summary.total_sites == 0:
        return build_report(request, "")

    legal_chunks = await retrieve_legal_chunks(request)
    response = await get_llm().ainvoke(build_messages(request, legal_chunks))
    opinions = format_opinions(response.text)

    if not opinions:
        raise EmptySummaryError("LLM returned no opinion points")

    return build_report(request, opinions)
