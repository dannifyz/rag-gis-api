import uvicorn
from fastapi import APIRouter, FastAPI

from rag_gis_api import ENV

app = FastAPI(title="rag-gis-api")
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)


def main() -> None:
    uvicorn.run(
        "rag_gis_api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=ENV == "local",
    )
