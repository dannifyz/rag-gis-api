import uvicorn
from fastapi import APIRouter, FastAPI

from rag_gis_api import ENV
from rag_gis_api.controllers import analysis_controller, chat_controller

app = FastAPI(title="rag-gis-api")
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


router.include_router(chat_controller.router)
router.include_router(analysis_controller.router)

app.include_router(router)


def main() -> None:
    uvicorn.run(
        "rag_gis_api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=ENV == "local",
    )
