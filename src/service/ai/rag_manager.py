import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
# from src.service.conf.gemini_api_key import GEMINI_API_KEY

class RAGManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RAGManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, reference_dir: str = "reference", index_path: str = "faiss_index"):
        if hasattr(self, "initialized") and self.initialized:
            return
            
        self.reference_dir = reference_dir
        self.index_path = index_path
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=os.environ.get("GEMINI_API_KEY"))
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
        documents = []
        if not os.path.exists(self.reference_dir):
            print(f"Reference directory not found: {self.reference_dir}")
            return None

        print(f"Building RAG index from {self.reference_dir}...")
        for filename in os.listdir(self.reference_dir):
            if filename.endswith(".pdf"):
                file_path = os.path.join(self.reference_dir, filename)
                try:
                    loader = PyPDFLoader(file_path)
                    documents.extend(loader.load())
                    print(f"Loaded {filename}")
                except Exception as e:
                    print(f"Failed to load {filename}: {e}")
        
        if not documents:
            print("No documents found to index.")
            return None

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(documents)
        
        vector_store = FAISS.from_documents(documents=splits, embedding=self.embeddings)
        vector_store.save_local(self.index_path)
        print("RAG index built and saved.")
        return vector_store

    def search(self, query: str, k: int = 3) -> str:
        if not self.vector_store:
            return ""
        
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return "\n\n".join([f"[참고 조항]\n{doc.page_content}" for doc in docs])
        except Exception as e:
            print(f"RAG search failed: {e}")
            return ""
