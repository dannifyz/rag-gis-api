import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

ENV = os.getenv("ENV", "production")


def main() -> None:
    print("Hello from rag-gis-api!")
