from rag_gis_api import PROJECT_ROOT

EVALS_DIR = PROJECT_ROOT / "evals"

LABELS_PATH = EVALS_DIR / "labels.json"
INPUTS_DIR = EVALS_DIR / "inputs"
EXPECTED_DIR = EVALS_DIR / "expected"
ACTUAL_DIR = EVALS_DIR / "actual"
SCORES_DIR = EVALS_DIR / "scores"

SUMMARY_PATH = SCORES_DIR / "summary.md"
