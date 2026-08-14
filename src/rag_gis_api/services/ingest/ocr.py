import asyncio

from langchain_core.documents import Document


async def consume_ocr_queue(ocr_queue: asyncio.Queue[Document]) -> None:
    """
    Drain the pages PyPDF could not read.

    OCR is not wired up yet, so a page taken off the queue is only reported and
    then dropped: its text never reaches the vector store. Runs until the task
    is cancelled.
    """
    while True:
        page = await ocr_queue.get()

        try:
            print(
                f"OCR  {page.metadata.get('source')} "
                f"page {page.metadata.get('page')} (dropped)"
            )
        finally:
            ocr_queue.task_done()
