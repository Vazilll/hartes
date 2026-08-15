import os

def search_text():
    search_terms = ["kg_nodes", "kg_edges", "llm_cache", "vazus.db"]
    results = []
    base_dir = r"C:\vazus"
    
    for root, dirs, files in os.walk(base_dir):
        if any(skip in root for skip in [".git", ".venv", "__pycache__", "node_modules", ".agents"]):
            continue
        for f in files:
            if f.endswith((".py", ".sql", ".go", ".json", ".md")):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as file_content:
                        content = file_content.read()
                        for term in search_terms:
                            if term in content:
                                results.append(f"{term} found in {path}")
                except Exception:
                    pass
    print("Search results:")
    for r in results:
        print(r)

if __name__ == "__main__":
    search_text()
