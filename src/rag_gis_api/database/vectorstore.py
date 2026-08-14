from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from rag_gis_api import PROJECT_ROOT


embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001", output_dimensionality=768
)

vectorstore = Chroma(
    collection_name="my_collection",
    embedding_function=embeddings,
    persist_directory=str(PROJECT_ROOT / "chroma_db"),
)
