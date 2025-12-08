from src.service.ai.rag_manager import RAGManager
import os

def test_rag():
    print("Testing RAGManager...")
    rag = RAGManager()
    
    query = "저작권 귀속"
    print(f"Searching for: {query}")
    result = rag.search(query)
    
    if result:
        print("Search successful!")
        print("--- Result Preview ---")
        print(result[:500])
        print("----------------------")
    else:
        print("Search returned no results.")

if __name__ == "__main__":
    test_rag()
