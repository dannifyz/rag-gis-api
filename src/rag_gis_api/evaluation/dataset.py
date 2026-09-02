import json

from pydantic import BaseModel

from rag_gis_api.evaluation.config import EVALS_DIR, LABELS_PATH
from rag_gis_api.schemas.analysis import AnalysisRequest
from rag_gis_api.services.ingest.loader.load_file import load_file


class Label(BaseModel):
    id: str
    project_id: str
    project_name: str
    input: str
    expected: str


def load_labels() -> list[Label]:
    return [Label(**row) for row in json.loads(LABELS_PATH.read_text(encoding="utf-8"))]


def load_request(label: Label) -> AnalysisRequest:
    payload = (EVALS_DIR / label.input).read_text(encoding="utf-8")
    return AnalysisRequest.model_validate_json(payload)


def load_expected_text(label: Label) -> str:
    pages = load_file(EVALS_DIR / label.expected)
    return "\n\n".join(page.page_content for page in pages)
