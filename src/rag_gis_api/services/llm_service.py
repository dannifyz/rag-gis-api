from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from rag_gis_api import GOOGLE_API_KEY


@lru_cache(maxsize=1)
def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=GOOGLE_API_KEY,
    )
