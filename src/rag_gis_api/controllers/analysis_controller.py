from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import PlainTextResponse

from rag_gis_api import ONEP_ANALYSIS_API_KEY
from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.gis_analysis_service import summarize_impact

router = APIRouter(prefix="/analysis", tags=["analysis"])

ApiKey = Annotated[str | None, Header(alias="X-API-Key")]


def verify_api_key(x_api_key: ApiKey = None) -> None:
    """No-op when we haven't been given a key to check against (see .env.example)."""
    if ONEP_ANALYSIS_API_KEY and x_api_key != ONEP_ANALYSIS_API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-API-Key")


@router.post("", dependencies=[Depends(verify_api_key)])
async def analyze(request: AnalysisRequest) -> PlainTextResponse:
    """
    Receive ONEP's finished impact analysis and return a Thai narrative summary.

    ONEP retries on 5xx/429/timeout/empty-body but treats 4xx as a permanent
    rejection (see the analysis contract doc) — so an LLM failure must surface
    as 502, never as a 200 with an empty or missing body.
    """
    try:
        summary = await summarize_impact(request)
    except Exception as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"{type(error).__name__}: {error}"
        ) from error

    if not summary:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="empty summary generated")

    return PlainTextResponse(summary)
