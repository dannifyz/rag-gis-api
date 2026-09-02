from rag_gis_api.evaluation.config import ACTUAL_DIR, SCORES_DIR, SUMMARY_PATH
from rag_gis_api.evaluation.dataset import Label
from rag_gis_api.evaluation.schemas import (
    CaseRecall,
    CaseScore,
    JudgeResult,
    RecallScore,
    SummaryScore,
)


def _recall_score(score: int, max_score: int) -> RecallScore:
    percent = round(score / max_score * 100, 1) if max_score else 0.0
    return RecallScore(score=score, max_score=max_score, percent=percent)


def score_case(label: Label, judgement: JudgeResult) -> CaseScore:
    matched = [item for item in judgement.recall_items if item.covered]
    missing = [item for item in judgement.recall_items if not item.covered]

    return CaseScore(
        id=label.id,
        project_name=label.project_name,
        recall=_recall_score(len(matched), len(judgement.recall_items)),
        matched=matched,
        missing=missing,
        extra=judgement.extra_items,
    )


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_actual(label: Label, output: str) -> None:
    _write(ACTUAL_DIR / f"{label.id}.md", f"# {label.id} — {label.project_name}\n\n{output}\n")


def _render_case_score(case: CaseScore) -> str:
    recall = case.recall
    lines = [
        f"# {case.id} — {case.project_name}",
        "",
        "## Recall",
        f"{recall.score}/{recall.max_score} ({recall.percent}%)",
        "",
        "## สิ่งที่ LLM เขียนตรงกับ dataset",
    ]
    if case.matched:
        for item in case.matched:
            lines.append(f"- {item.point}")
            lines.append(f"  - หลักฐาน: {item.evidence}")
    else:
        lines.append("- (ไม่มี)")

    lines += ["", "## สิ่งที่ LLM ไม่เขียนแต่ dataset เขียน"]
    if case.missing:
        for item in case.missing:
            lines.append(f"- {item.point}")
    else:
        lines.append("- (ไม่มี)")

    lines += ["", "## สิ่งที่ LLM เขียนแต่ dataset ไม่ได้เขียน"]
    if case.extra:
        for item in case.extra:
            lines.append(f"- {item.point} — {item.note}")
    else:
        lines.append("- (ไม่มี)")

    return "\n".join(lines) + "\n"


def write_case_score(case: CaseScore) -> None:
    _write(SCORES_DIR / f"{case.id}.md", _render_case_score(case))


def build_summary(case_scores: list[CaseScore]) -> SummaryScore:
    total_score = sum(case.recall.score for case in case_scores)
    total_max = sum(case.recall.max_score for case in case_scores)

    return SummaryScore(
        recall=_recall_score(total_score, total_max),
        case_count=len(case_scores),
        cases=[CaseRecall(id=case.id, recall=case.recall) for case in case_scores],
    )


def _render_summary(summary: SummaryScore) -> str:
    total = summary.recall
    lines = [
        "# สรุปผลการประเมิน (Recall)",
        "",
        "## รวมทั้งหมด",
        f"{total.score}/{total.max_score} ({total.percent}%) จาก {summary.case_count} เคส",
        "",
        "## แยกรายเคส",
        "| Case | Recall | Percent |",
        "| --- | --- | --- |",
    ]
    for case in summary.cases:
        recall = case.recall
        lines.append(f"| {case.id} | {recall.score}/{recall.max_score} | {recall.percent}% |")

    return "\n".join(lines) + "\n"


def write_summary(summary: SummaryScore) -> None:
    _write(SUMMARY_PATH, _render_summary(summary))
