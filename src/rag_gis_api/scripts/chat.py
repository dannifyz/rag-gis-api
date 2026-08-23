import argparse
import asyncio
import json
import sys
import time

import httpx
from httpx_sse import aconnect_sse

DEFAULT_QUESTION = "การขออนุญาตก่อสร้างมีขั้นตอนอย่างไร"
DEFAULT_URL = "http://127.0.0.1:8000/api/chat/stream"

# Retrieval plus a full answer can take a while; the default 5s would cut it off.
TIMEOUT = 120


async def stream_answer(url: str, question: str, session_id: str | None = None) -> int:
    """Print every SSE event as it arrives. Returns the exit code."""
    started = time.monotonic()

    def elapsed() -> str:
        return f"[{time.monotonic() - started:5.1f}s]"

    params = {"question": question}

    if session_id:
        params["session_id"] = session_id

    async with (
        httpx.AsyncClient(timeout=TIMEOUT) as client,
        # httpx encodes the params, so a Thai question needs no escaping here.
        aconnect_sse(client, "GET", url, params=params) as events,
    ):
        async for event in events.aiter_sse():
            data = json.loads(event.data)

            if event.event == "status":
                print(f"{elapsed()} {data['message']}")

            elif event.event == "token":
                # No newline: tokens are printed where they land, as they land.
                print(data["text"], end="", flush=True)

            elif event.event == "done":
                print(f"\n\n{elapsed()} done")

                for source in data["sources"]:
                    pages = ", ".join(str(page) for page in source["pages"])
                    print(f"  - {source['source']} หน้า {pages}")

            elif event.event == "error":
                print(f"\n{elapsed()} ERROR: {data['message']}")
                return 1

    return 0


def main() -> None:
    # The Windows console defaults to cp1252, which cannot print Thai.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Ask the running API and print each SSE event as it arrives."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=DEFAULT_QUESTION,
        help=f"Question to ask (default: {DEFAULT_QUESTION}).",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Stream endpoint to call (default: {DEFAULT_URL}).",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Conversation id to keep history for (requires Redis). Omit for a stateless call.",
    )
    args = parser.parse_args()

    print(f"Q: {args.question}\n")

    try:
        exit_code = asyncio.run(stream_answer(args.url, args.question, args.session_id))
    except httpx.ConnectError:
        print(f"ต่อ {args.url} ไม่ได้ — สั่ง uv run rag-gis-api ในอีก terminal ก่อน")
        exit_code = 1

    sys.exit(exit_code)
