import argparse
import asyncio
import sys

from tqdm import tqdm

from rag_gis_api.evaluation.dataset import (
    Label,
    load_expected_text,
    load_labels,
    load_request,
)
from rag_gis_api.evaluation.judge import judge_recall
from rag_gis_api.evaluation.report import (
    build_summary,
    score_case,
    write_actual,
    write_case_score,
    write_summary,
)
from rag_gis_api.evaluation.schemas import CaseScore, SummaryScore
from rag_gis_api.services.gis_analysis_service import summarize_impact


async def evaluate_case(label: Label) -> CaseScore:
    request = load_request(label)

    output = await summarize_impact(request)
    write_actual(label, output)

    expected_text = await asyncio.to_thread(load_expected_text, label)
    judgement = await judge_recall(expected_text, output)

    case_score = score_case(label, judgement)
    write_case_score(case_score)
    return case_score


def select_labels(case_ids: list[str]) -> list[Label]:
    """Every case, or just the requested ids in the order given."""
    labels = load_labels()

    if not case_ids:
        return labels

    by_id = {label.id: label for label in labels}
    unknown = [case_id for case_id in case_ids if case_id not in by_id]

    if unknown:
        available = ", ".join(by_id)
        raise SystemExit(f"unknown case id(s): {', '.join(unknown)}\navailable: {available}")

    return [by_id[case_id] for case_id in case_ids]


async def run(labels: list[Label]) -> list[CaseScore]:
    scores: list[CaseScore] = []

    with tqdm(labels, desc="Evaluating", unit="case") as bar:
        for label in bar:
            bar.set_postfix_str(label.id)
            case_score = await evaluate_case(label)
            scores.append(case_score)
            bar.write(
                f"{case_score.id}: recall {case_score.recall.score}/"
                f"{case_score.recall.max_score} ({case_score.recall.percent}%)"
            )

    return scores


def print_summary(summary: SummaryScore) -> None:
    print("\nRecall summary (LLM-as-a-judge)")
    print("-" * 48)
    for case in summary.cases:
        recall = case.recall
        print(f"  {case.id:<12} {recall.score:>3}/{recall.max_score:<3}  {recall.percent:>5}%")
    print("-" * 48)
    total = summary.recall
    print(f"  {'TOTAL':<12} {total.score:>3}/{total.max_score:<3}  {total.percent:>5}%")


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Run the LLM-as-a-judge recall evaluation over the cases in evals/."
    )
    parser.add_argument(
        "cases",
        nargs="*",
        help="case id ที่จะรัน เช่น case_001 case_003 (เว้นว่าง = ทุกเคส)",
    )
    args = parser.parse_args()

    labels = select_labels(args.cases)
    scores = asyncio.run(run(labels))

    summary = build_summary(scores)
    print_summary(summary)

    if not args.cases:
        write_summary(summary)
