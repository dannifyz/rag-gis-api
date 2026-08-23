import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = PROJECT_ROOT / "documents"

load_dotenv(PROJECT_ROOT / ".env")

ENV = os.getenv("ENV", "production")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

TYPHOON_API_KEY = os.getenv("TYPHOON_API_KEY")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if not GOOGLE_API_KEY:
    raise RuntimeError(f"GOOGLE_API_KEY not set. Add it to {PROJECT_ROOT / '.env'}")

if not TYPHOON_API_KEY:
    raise RuntimeError(f"TYPHOON_API_KEY not set. Add it to {PROJECT_ROOT / '.env'}")


def main() -> None:
    print("Hello from rag-gis-api!")
