import asyncio
import logging
from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import PlainTextResponse

from rag_gis_api import ONEP_ANALYSIS_API_KEY
from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.gis_analysis_service import summarize_impact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])

# ONEP disconnects at 120s (their default) and retries. Failing first, just inside
# that window, turns a hung retrieval or LLM call into a clean retryable error
# instead of a request that hangs until their client gives up.
TIMEOUT_SECONDS = 100

ApiKey = Annotated[str | None, Header(alias="X-API-Key")]


def verify_api_key(x_api_key: ApiKey = None) -> None:
    """No-op when we haven't been given a key to check against (see .env.example)."""
    if not ONEP_ANALYSIS_API_KEY:
        return

    # compare_digest, not `!=`: a plain string compare returns as soon as it hits a
    # differing byte, which leaks the shared secret's prefix through response timing.
    if x_api_key is None or not compare_digest(x_api_key, ONEP_ANALYSIS_API_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-API-Key")


@router.post("", dependencies=[Depends(verify_api_key)])
async def analyze(request: AnalysisRequest) -> PlainTextResponse:
    """
    Receive ONEP's finished impact analysis and return a Thai narrative summary.

    ONEP retries on 5xx/429/timeout/empty-body but treats 4xx as a permanent
    rejection (see the analysis contract doc) — so a failure here must surface
    as 5xx, never as a 200 with an empty or partial body.
    """
    if request.schema_version != "1.0":
        # Process anyway: unknown versions still carry every field we read.
        logger.info(
            "unrecognized schema_version %s for project %s",
            request.schema_version,
            request.project.id,
        )

    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            summary = await summarize_impact(request)
    except TimeoutError:
        logger.exception("analysis timed out for project %s", request.project.id)
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail="analysis timed out") from None
    except Exception:
        # Logged with the traceback server-side; the response stays generic because
        # ONEP is an external caller and records the body in their own logs.
        logger.exception("analysis failed for project %s", request.project.id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="failed to generate analysis summary"
        ) from None

    return PlainTextResponse(summary)
