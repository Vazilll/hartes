#!/usr/bin/env python3
"""Populate RAG with ArXiv papers on DNTS-relevant topics."""
import json, sqlite3, httpx, asyncio, sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\vazus\pyenv\scripts')
from dnts_rag import ArxivClient, TextChunker

# Topics relevant to DNTS
TOPICS = [
    "llm agent tool calling MCP protocol",
    "multi-agent orchestration framework",
    "retrieval augmented generation knowledge graph",
    "AI agent observability tracing",
    "function calling LLM benchmark",
]

async def main():
    client = ArxivClient(rate_limit_delay=3.0)
    chunker = TextChunker(chunk_size=400, overlap=50)
    
    conn = sqlite3.connect(r'C:\vazus\memory\vazus.db')
    conn.execute("PRAGMA journal_mode=WAL")
    
    total_inserted = 0
    
    for topic in TOPICS:
        print(f"Searching: {topic}")
        try:
            papers = await client.search(topic, max_results=5)
        except Exception as e:
            print(f"  Search failed: {e}")
            continue
        
        for paper in papers:
            text = f"Title: {paper.title}\nAuthors: {', '.join(paper.authors)}\nAbstract: {paper.abstract}"
            chunks = chunker.chunk_text(text, source=paper.arxiv_id)
            
            for chunk in chunks:
                content = f"{chunk.text} [arxiv:{paper.arxiv_id}]"
                conn.execute("INSERT INTO rag_fts(content, source) VALUES (?, ?)",
                            (content, f"arxiv:{paper.arxiv_id}"))
                total_inserted += 1
            
            print(f"  + {paper.arxiv_id}: {paper.title[:60]}... ({len(chunks)} chunks)")
    
    conn.commit()
    # Verify
    cur = conn.execute("SELECT count(*) FROM rag_fts")
    count = cur.fetchone()[0]
    conn.close()
    print(f"\nDone! {total_inserted} chunks inserted. Total in RAG: {count}")

if __name__ == "__main__":
    asyncio.run(main())
