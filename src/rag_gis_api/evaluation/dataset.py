import json
from pathlib import Path

from pydantic import BaseModel

from rag_gis_api.evaluation.config import EVALS_DIR, LABELS_PATH
from rag_gis_api.schemas.analysis import AnalysisRequest


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


def expected_pdf_path(label: Label) -> Path:
    return EVALS_DIR / label.expected
