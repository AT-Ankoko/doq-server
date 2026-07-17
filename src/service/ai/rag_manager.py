import os
import orjson
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from src.service.conf.gemini_api_key import GEMINI_API_KEY

class RAGManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RAGManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, chunks_path: str = "reference/doq_chunks.json", index_path: str = "faiss_index_chunks"):
        if hasattr(self, "initialized") and self.initialized:
            return
            
        self.chunks_path = chunks_path
        self.index_path = index_path
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GEMINI_API_KEY)
        self.vector_store = self._load_or_create_index()
        self.initialized = True

    def _load_or_create_index(self):
        if os.path.exists(self.index_path):
            try:
                # allow_dangerous_deserialization is needed for loading local FAISS index
                return FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                print(f"Failed to load index: {e}. Rebuilding...")
        
        return self._build_index()

    def _build_index(self):
        if not os.path.exists(self.chunks_path):
            print(f"Chunks file not found: {self.chunks_path}")
            return None

        print(f"Building RAG index from {self.chunks_path}...")
        try:
            with open(self.chunks_path, "rb") as f:
                chunks = orjson.loads(f.read())
        except Exception as e:
            print(f"Failed to load chunks: {e}")
            return None

        texts = []
        metadatas = []

        for chunk in chunks:
            text = (chunk.get("text") or "").strip()
            if not text:
                continue

            texts.append(text)
            metadatas.append(
                {
                    "file_name": chunk.get("file_name", ""),
                    "chunk_index": chunk.get("chunk_index", -1),
                    "article_title": chunk.get("article_title", ""),
                }
            )

        if not texts:
            print("No chunk texts found to index.")
            return None

        vector_store = FAISS.from_texts(texts=texts, embedding=self.embeddings, metadatas=metadatas)
        vector_store.save_local(self.index_path)
        print("RAG index built and saved.")
        return vector_store

    def search(self, query: str, k: int = 3) -> str:
        if not self.vector_store:
            return ""
        
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            formatted_results = []
            for doc in docs:
                article_title = doc.metadata.get("article_title") if hasattr(doc, "metadata") else ""
                if article_title:
                    formatted_results.append(f"[참고 조항: {article_title}]\n{doc.page_content}")
                else:
                    formatted_results.append(f"[참고 조항]\n{doc.page_content}")

            return "\n\n".join(formatted_results)
        except Exception as e:
            print(f"RAG search failed: {e}")
            return ""
