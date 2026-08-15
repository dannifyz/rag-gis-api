import argparse
import sys

from rag_gis_api.services.llm_service import get_llm

DEFAULT_QUESTION = "ประเทศไทยมีกี่จังหวัด"
SYSTEM_PROMPT = "ตอบสั้น ๆ ไม่เกิน 2 ประโยค ไม่ต้องอธิบายเพิ่ม"


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Send one prompt to the LLM and print the answer.")
    parser.add_argument(
        "question",
        nargs="?",
        default=DEFAULT_QUESTION,
        help=f"Question to ask (default: {DEFAULT_QUESTION}).",
    )
    args = parser.parse_args()

    llm = get_llm()
    response = llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            ("human", args.question),
        ]
    )

    print(f"Q: {args.question}")
    print(f"A: {response.text}")
