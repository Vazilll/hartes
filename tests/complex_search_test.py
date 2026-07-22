import sys
import os
sys.path.insert(0, r"C:\vazus")
sys.path.insert(0, r"C:\vazus\scripts")
import os
import sys

# Временно убираем лимиты потоков, чтобы ZMQ-сервер унаследовал многопоточность
omp_val = os.environ.pop("OMP_NUM_THREADS", None)
mkl_val = os.environ.pop("MKL_NUM_THREADS", None)
faiss_val = os.environ.pop("FAISS_NUM_THREADS", None)
os.environ["LEANN_LOG_LEVEL"] = "INFO"

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')

import json
import re
import subprocess
from pathlib import Path
from leann.api import LeannSearcher

# Путь к CBM
CBM_EXE = r"C:\vazus\bin\codebase-memory-mcp.exe"

def run_cypher_query(query):
    """Выполняет Cypher-запрос к codebase-memory-mcp"""
    args = [
        CBM_EXE,
        "cli",
        "query_graph",
        json.dumps({
            "project": "C-dnts-pyenv",
            "query": query
        })
    ]
    proc = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    try:
        return json.loads(proc.stdout)
    except Exception as e:
        return {"error": str(e), "raw": proc.stdout}

def get_structural_info(func_name):
    """Собирает структурную информацию об узле из AST-графа"""
    # 1. Кто вызывает эту функцию (CALLS)
    caller_query = f"MATCH (caller)-[:CALLS]->(func) WHERE func.name = '{func_name}' RETURN caller.name, caller.file_path LIMIT 5"
    caller_data = run_cypher_query(caller_query)
    callers = []
    if "rows" in caller_data:
        for row in caller_data["rows"]:
            callers.append({"name": row[0], "file_path": row[1]})
            
    # 2. Кого вызывает эта функция (CALLS)
    callee_query = f"MATCH (func)-[:CALLS]->(callee) WHERE func.name = '{func_name}' RETURN callee.name, callee.file_path LIMIT 5"
    callee_data = run_cypher_query(callee_query)
    callees = []
    if "rows" in callee_data:
        for row in callee_data["rows"]:
            callees.append({"name": row[0], "file_path": row[1]})
            
    # 3. В каком модуле/файле определена
    def_query = f"MATCH (m)-[:DEFINES]->(func) WHERE func.name = '{func_name}' RETURN m.name, m.file_path LIMIT 1"
    def_data = run_cypher_query(def_query)
    defined_in = None
    if "rows" in def_data and def_data["rows"]:
        defined_in = {"name": def_data["rows"][0][0], "file_path": def_data["rows"][0][1]}

    return {
        "callers": callers,
        "callees": callees,
        "defined_in": defined_in
    }

def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "project indexer"
    print("=" * 80)
    print(f"🤖 ГИБРИДНЫЙ ПОИСК ПО КОДУ (AST + ВЕКТОР)")
    print(f"Запрос: «{query}»")
    print("=" * 80)
    
    # Шаг 1: Семантический поиск по LEANN
    index_path = "C:/vazus/leann-indexes/pyenv-project.leann"
    if not os.path.exists(index_path):
        index_path = "C:/vazus/leann-indexes/gomcp-functions-v2.leann"
    if not os.path.exists(index_path):
        index_path = "C:/vazus/leann-indexes/gomcp-functions.leann"
        
    searcher = LeannSearcher(index_path, enable_warmup=False)
    
    # Теперь применяем однопоточные ограничения к текущему клиенту, чтобы избежать дедлока в C++ FAISS
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["FAISS_NUM_THREADS"] = "1"
    os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
    
    results = searcher.search(query, top_k=3, complexity=10, batch_size=2)
    
    print(f"✅ Найдено {len(results)} семантически близких функций.\n")
    
    # Шаг 2: Структурный анализ через CBM
    print(f"🔗 [2/2] Анализ связей в AST-графе codebase-memory-mcp...\n")
    
    for i, r in enumerate(results):
        text = r.text
        # Извлекаем имя функции
        match = re.search(r"Function:\s*(\w+)", text)
        func_name = match.group(1) if match else None
        
        if not func_name:
            # Ищем def name( или func name(
            def_match = re.search(r"(?:def|func)\s+(\w+)\s*\(", text)
            func_name = def_match.group(1) if def_match else "Unknown"
        
        print(f"📌 Результат #{i+1}: {func_name} (Схожесть: {r.score:.4f})")
        
        # Печатаем сигнатуру и комменты из текста
        sig_match = re.search(r"Signature:\s*(.*?)\n", text)
        comment_match = re.search(r"Comment:\s*(.*?)\n", text)
        
        if sig_match:
            print(f"  Сигнатура:  {sig_match.group(1)}")
        if comment_match and comment_match.group(1).strip():
            print(f"  Описание:    {comment_match.group(1)}")
            
        # Запрашиваем CBM
        if func_name != "Unknown":
            struct = get_structural_info(func_name)
            
            if struct["defined_in"]:
                print(f"  Определена в: {struct['defined_in']['file_path']} ({struct['defined_in']['name']})")
            
            if struct["callers"]:
                print(f"  Вызывается в:")
                for caller in struct["callers"]:
                    print(f"    - {caller['name']} ({caller['file_path']})")
            else:
                print(f"  Вызывается в: (нет входящих вызовов в графе)")
                
            if struct["callees"]:
                print(f"  Вызывает функции:")
                for callee in struct["callees"]:
                    print(f"    - {callee['name']} ({callee['file_path']})")
        
        print("-" * 80)

if __name__ == "__main__":
    main()
