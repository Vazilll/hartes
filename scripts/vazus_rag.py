#!/usr/bin/env python3
"""
vazus_rag.py — ArXiv API, Text Chunker, and RAG Prompt tools for DNTS.

Integrated from jamwithai/production-agentic-rag-course into DNTS ecosystem.

Components:
  - ArxivClient: Поиск и загрузка статей с arXiv.org
  - TextChunker: Умное разбиение текста на чанки (section-based + overlap)
  - RAGPromptBuilder: Сборка RAG промптов для LLM
"""

import asyncio
import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urlencode

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("dnts-rag")

# ════════════════════════════════════════════════════════════
# ArXiv API Client
# ════════════════════════════════════════════════════════════

ARXIV_BASE_URL = "https://export.arxiv.org/api/query"
ARXIV_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}


@dataclass
class ArxivPaper:
    """Structured data for an arXiv paper."""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published_date: str
    categories: List[str]
    pdf_url: str
    link: str = ""


class ArxivClient:
    """Client for arXiv API — search, fetch, download papers."""

    def __init__(self, rate_limit_delay: float = 3.0, timeout: int = 30):
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self._last_request: float = 0.0

    async def _rate_limit(self):
        """Respect arXiv's rate limit (3s between requests)."""
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request = time.time()

    async def search(
        self,
        query: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> List[ArxivPaper]:
        """Search arXiv papers by query string.
        
        Args:
            query: arXiv search query (supports prefixes: ti:, au:, cat:, all:)
            max_results: Maximum number of results
            start: Pagination offset
            sort_by: relevance | submittedDate | lastUpdatedDate
            sort_order: ascending | descending
        """
        params = {
            "search_query": query,
            "start": start,
            "max_results": min(max_results, 2000),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        safe = ":+[]*"
        url = f"{ARXIV_BASE_URL}?{urlencode(params, quote_via=quote, safe=safe)}"
        return await self._fetch(url)

    async def search_by_category(
        self,
        category: str = "cs.AI",
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "submittedDate",
    ) -> List[ArxivPaper]:
        """Fetch recent papers from a category."""
        return await self.search(
            query=f"cat:{category}",
            max_results=max_results,
            start=start,
            sort_by=sort_by,
        )

    async def fetch_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """Fetch a single paper by its arXiv ID."""
        clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
        params = {"id_list": clean_id, "max_results": 1}
        url = f"{ARXIV_BASE_URL}?{urlencode(params, quote_via=quote, safe=':+[]*')}"
        papers = await self._fetch(url)
        return papers[0] if papers else None

    async def search_by_author(self, author: str, max_results: int = 10) -> List[ArxivPaper]:
        """Search papers by author name."""
        return await self.search(query=f'au:"{author}"', max_results=max_results)

    async def search_by_title(self, title: str, max_results: int = 10) -> List[ArxivPaper]:
        """Search papers by title keywords."""
        return await self.search(query=f'ti:"{title}"', max_results=max_results)

    async def _fetch(self, url: str) -> List[ArxivPaper]:
        """Execute API request and parse XML response."""
        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return self._parse_response(resp.text)
        except httpx.TimeoutException:
            logger.error(f"arXiv API timeout: {url[:80]}")
            raise
        except Exception as e:
            logger.error(f"arXiv API error: {e}")
            raise

    def _parse_response(self, xml: str) -> List[ArxivPaper]:
        """Parse arXiv API XML response."""
        papers = []
        try:
            root = ET.fromstring(xml)
            for entry in root.findall("atom:entry", ARXIV_NAMESPACES):
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        return papers

    def _parse_entry(self, entry: ET.Element) -> Optional[ArxivPaper]:
        """Parse a single Atom entry."""
        try:
            # ID
            id_elem = entry.find("atom:id", ARXIV_NAMESPACES)
            arxiv_id = id_elem.text.split("/")[-1] if id_elem is not None and id_elem.text else ""

            # Title
            title_elem = entry.find("atom:title", ARXIV_NAMESPACES)
            title = (title_elem.text or "").strip().replace("\n", " ") if title_elem is not None else ""

            # Authors
            authors = []
            for author in entry.findall("atom:author", ARXIV_NAMESPACES):
                name_elem = author.find("atom:name", ARXIV_NAMESPACES)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            # Abstract
            abs_elem = entry.find("atom:summary", ARXIV_NAMESPACES)
            abstract = (abs_elem.text or "").strip().replace("\n", " ") if abs_elem is not None else ""

            # Published date
            pub_elem = entry.find("atom:published", ARXIV_NAMESPACES)
            published = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

            # Categories
            categories = []
            for cat in entry.findall("atom:category", ARXIV_NAMESPACES):
                term = cat.get("term")
                if term:
                    categories.append(term)

            # PDF URL
            pdf_url = ""
            link = ""
            for link_elem in entry.findall("atom:link", ARXIV_NAMESPACES):
                href = link_elem.get("href", "")
                if link_elem.get("title") == "pdf":
                    pdf_url = href.replace("http://", "https://")
                elif link_elem.get("rel") == "alternate" and not link:
                    link = href

            return ArxivPaper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                published_date=published,
                categories=categories,
                pdf_url=pdf_url,
                link=link,
            )
        except Exception as e:
            logger.warning(f"Failed to parse entry: {e}")
            return None

    async def download_pdf(self, paper: ArxivPaper, cache_dir: str = "./data/arxiv_pdfs") -> Optional[str]:
        """Download PDF for a paper, return local path."""
        if not paper.pdf_url:
            return None
        cache = Path(cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        safe_name = paper.arxiv_id.replace("/", "_") + ".pdf"
        pdf_path = cache / safe_name

        if pdf_path.exists():
            return str(pdf_path)

        await self._rate_limit()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("GET", paper.pdf_url) as resp:
                    resp.raise_for_status()
                    with open(pdf_path, "wb") as f:
                        async for chunk in resp.aiter_bytes():
                            f.write(chunk)
            logger.info(f"Downloaded PDF: {pdf_path}")
            return str(pdf_path)
        except Exception as e:
            logger.error(f"PDF download failed: {e}")
            if pdf_path.exists():
                pdf_path.unlink()
            return None


# ════════════════════════════════════════════════════════════
# Text Chunker
# ════════════════════════════════════════════════════════════

@dataclass
class ChunkMetadata:
    chunk_index: int
    word_count: int
    overlap_with_previous: int = 0
    overlap_with_next: int = 0
    section_title: Optional[str] = None
    source: str = ""


@dataclass
class TextChunk:
    text: str
    metadata: ChunkMetadata


class TextChunker:
    """Intelligent text chunker with section-aware and overlap strategies.

    Supports:
    - Section-based chunking (combines small sections, splits large ones)
    - Traditional word-based chunking with configurable overlap
    - Metadata tracking per chunk
    """

    def __init__(self, chunk_size: int = 600, overlap: int = 100, min_chunk: int = 100):
        if overlap >= chunk_size:
            raise ValueError("Overlap must be < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk = min_chunk

    def chunk_text(self, text: str, source: str = "") -> List[TextChunk]:
        """Split text into overlapping word-based chunks."""
        if not text or not text.strip():
            return []

        words = re.findall(r"\S+", text)
        if len(words) < self.min_chunk:
            return [TextChunk(
                text=text,
                metadata=ChunkMetadata(
                    chunk_index=0, word_count=len(words), source=source
                ),
            )] if words else []

        chunks = []
        pos = 0
        idx = 0
        while pos < len(words):
            end = min(pos + self.chunk_size, len(words))
            chunk_words = words[pos:end]
            chunk_text = " ".join(chunk_words)

            chunks.append(TextChunk(
                text=chunk_text,
                metadata=ChunkMetadata(
                    chunk_index=idx,
                    word_count=len(chunk_words),
                    overlap_with_previous=min(self.overlap, pos) if pos > 0 else 0,
                    overlap_with_next=self.overlap if end < len(words) else 0,
                    source=source,
                ),
            ))

            pos += self.chunk_size - self.overlap
            idx += 1
            if end >= len(words):
                break

        return chunks

    def chunk_with_sections(
        self,
        text: str,
        sections: Optional[Union[Dict[str, str], str, list]] = None,
        title: str = "",
        abstract: str = "",
        source: str = "",
    ) -> List[TextChunk]:
        """Chunk text using section boundaries when available.
        
        Strategy:
        - Sections 100-800 words: Use as single chunk
        - Sections <100 words: Combine with adjacent sections
        - Sections >800 words: Split with traditional chunking
        - Fallback: traditional chunking
        """
        if not sections:
            return self.chunk_text(text, source=source)

        sections_dict = self._parse_sections(sections)
        if not sections_dict:
            return self.chunk_text(text, source=source)

        header = f"{title}\n\nAbstract: {abstract}\n\n" if title or abstract else ""
        chunks = []
        small_sections: List[tuple] = []
        section_items = list(sections_dict.items())

        for i, (sec_title, content) in enumerate(section_items):
            content_str = str(content) if content else ""
            words = len(content_str.split())

            if words < self.min_chunk:
                small_sections.append((sec_title, content_str, words))
                if i == len(section_items) - 1 or len(str(section_items[i+1][1]).split()) >= self.min_chunk:
                    combined = self._combine_small(small_sections, header, chunks, idx=len(chunks), source=source)
                    chunks.extend(combined)
                    small_sections = []
            elif words <= 800:
                chunk_text = f"{header}Section: {sec_title}\n\n{content_str}"
                chunks.append(TextChunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        chunk_index=len(chunks),
                        word_count=len(chunk_text.split()),
                        section_title=sec_title,
                        source=source,
                    ),
                ))
            else:
                section_text = f"Section: {sec_title}\n\n{content_str}"
                full = f"{header}{section_text}"
                sub_chunks = self.chunk_text(section_text, source=source)
                for sc in sub_chunks:
                    sc.metadata.chunk_index = len(chunks)
                    sc.metadata.section_title = f"{sec_title} (part)"
                    sc.text = f"{header}{sc.text}"
                    chunks.append(sc)

        return chunks

    def _parse_sections(self, sections: Union[Dict[str, str], str, list]) -> Dict[str, str]:
        if isinstance(sections, dict):
            return sections
        elif isinstance(sections, list):
            result = {}
            for i, s in enumerate(sections):
                if isinstance(s, dict):
                    result[s.get("title", s.get("heading", f"Section {i+1}"))] = s.get("content", s.get("text", ""))
                else:
                    result[f"Section {i+1}"] = str(s)
            return result
        elif isinstance(sections, str):
            try:
                parsed = json.loads(sections)
                return self._parse_sections(parsed)
            except json.JSONDecodeError:
                return {}
        return {}

    def _combine_small(
        self,
        small_sections: List[tuple],
        header: str,
        _existing_chunks: List[TextChunk],
        idx: int,
        source: str,
    ) -> List[TextChunk]:
        if not small_sections:
            return []
        combined = []
        for title, content, _ in small_sections:
            combined.append(f"Section: {title}\n\n{content}")
        separator = "\n\n"
        text = f"{header}{separator.join(combined)}"
        titles = [t for t, _, _ in small_sections]
        label = " + ".join(titles[:3])
        if len(titles) > 3:
            label = label + " + " + str(len(titles)-3) + " more"
        return [TextChunk(
            text=text,
            metadata=ChunkMetadata(
                chunk_index=idx, word_count=len(text.split()),
                section_title=label, source=source,
            ),
        )]


# ════════════════════════════════════════════════════════════
# RAG Prompt Builder
# ════════════════════════════════════════════════════════════

RAG_SYSTEM_PROMPT = """You are an AI assistant specialized in answering questions about academic papers from arXiv. Your task is to provide accurate, helpful answers based ONLY on the provided paper excerpts.

Instructions:
1. Base your answer STRICTLY on the provided paper excerpts
2. If the excerpts don't contain enough information to answer the question, say so clearly
3. Cite the specific papers (by arXiv ID) when providing information
4. Be concise but comprehensive in your response
5. Maintain academic accuracy and precision
6. If multiple papers discuss the topic, synthesize the information coherently
7. Keep it less than 300 words

Remember:
- Do NOT make up information not present in the excerpts
- Do NOT use knowledge beyond what's provided in the paper excerpts
- Always acknowledge uncertainty when the excerpts are ambiguous or incomplete"""


class RAGPromptBuilder:
    """Build RAG prompts for LLM querying with context."""

    def __init__(self, system_prompt: str = RAG_SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    def build_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Build a RAG prompt from query and context chunks.
        
        Args:
            query: User's question
            chunks: List of dicts with keys: text (str), source (str, optional)
        """
        prompt = f"{self.system_prompt}\n\n### Context from Papers:\n\n"
        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", chunk.get("chunk_text", chunk.get("content", "")))
            source = chunk.get("source", chunk.get("arxiv_id", ""))
            ref = f"[{i}]" + (f" (arXiv:{source})" if source else "")
            prompt += f"{ref}\n{text}\n\n"

        prompt += f"### Question:\n{query}\n\n### Answer:\n"
        return prompt

    def build_agentic_prompt(self, query: str, context: Optional[str] = None) -> str:
        """Build a prompt for agentic RAG (determine if retrieval is needed)."""
        prompt = self.system_prompt + "\n\n"
        if context:
            prompt += f"### Previous context:\n{context}\n\n"
        prompt += f"### Question:\n{query}\n\n"
        prompt += (
            "First, determine: Does this question require information from academic papers?\n"
            "If YES, respond with 'NEED_RETRIEVAL: <rewritten search query>'\n"
            "If NO, respond with 'NO_RETRIEVAL: <direct answer>'\n"
            "### Response:\n"
        )
        return prompt

    @staticmethod
    def parse_agentic_response(response: str) -> Dict[str, str]:
        """Parse agentic RAG response into action and content."""
        if response.startswith("NEED_RETRIEVAL:"):
            return {"action": "retrieve", "query": response[15:].strip()}
        elif response.startswith("NO_RETRIEVAL:"):
            return {"action": "answer", "answer": response[13:].strip()}
        return {"action": "retrieve", "query": response.strip()}


# ════════════════════════════════════════════════════════════
# Caching utility (simple in-memory + file)
# ════════════════════════════════════════════════════════════

class SimpleCache:
    """Simple TTL cache for API responses."""

    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, tuple] = {}
        self.ttl = ttl_seconds

    def _key(self, *args, **kwargs) -> str:
        raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, *args, **kwargs) -> Optional[Any]:
        key = self._key(*args, **kwargs)
        if key in self._cache:
            val, ts = self._cache[key]
            if time.time() - ts < self.ttl:
                return val
            del self._cache[key]
        return None

    def set(self, value: Any, *args, **kwargs):
        key = self._key(*args, **kwargs)
        self._cache[key] = (value, time.time())

    def clear(self):
        self._cache.clear()


# Singleton instances
arxiv_client = ArxivClient()
text_chunker = TextChunker()
prompt_builder = RAGPromptBuilder()
arxiv_cache = SimpleCache(ttl_seconds=1800)  # 30 min cache for arXiv queries


# ════════════════════════════════════════════════════════════
# Convenience functions for MCP integration
# ════════════════════════════════════════════════════════════

async def mcp_arxiv_search(query: str, max_results: int = 10, use_cache: bool = True) -> str:
    """Search arXiv papers. Returns JSON with title, authors, abstract, pdf_url."""
    cache_key = f"arxiv_search:{query}:{max_results}"
    if use_cache:
        cached = arxiv_cache.get(cache_key)
        if cached:
            return cached

    papers = await arxiv_client.search(query=query, max_results=max_results)
    result = json.dumps([asdict(p) for p in papers], ensure_ascii=False, indent=2)

    if use_cache:
        arxiv_cache.set(result, cache_key)
    return result


async def mcp_arxiv_fetch_by_id(arxiv_id: str) -> str:
    """Fetch a single arXiv paper by ID."""
    paper = await arxiv_client.fetch_by_id(arxiv_id)
    if not paper:
        return json.dumps({"error": f"Paper {arxiv_id} not found"})
    return json.dumps(asdict(paper), ensure_ascii=False, indent=2)


async def mcp_chunk_text(text: str, chunk_size: int = 600, overlap: int = 100, source: str = "") -> str:
    """Split text into chunks. Returns JSON array of chunks with metadata."""
    chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
    chunks = chunker.chunk_text(text, source=source)
    result = []
    for c in chunks:
        result.append({"text": c.text, "metadata": asdict(c.metadata)})
    return json.dumps(result, ensure_ascii=False)


async def mcp_build_rag_prompt(query: str, chunks_json: str) -> str:
    """Build a RAG prompt from query and JSON array of chunks."""
    chunks = json.loads(chunks_json) if isinstance(chunks_json, str) else chunks_json
    return prompt_builder.build_prompt(query, chunks)


async def mcp_arxiv_recent(category: str = "cs.AI", max_results: int = 10) -> str:
    """Fetch recent papers from an arXiv category."""
    papers = await arxiv_client.search_by_category(category=category, max_results=max_results)
    return json.dumps([asdict(p) for p in papers], ensure_ascii=False, indent=2)


async def mcp_arxiv_search_author(author: str, max_results: int = 10) -> str:
    """Search arXiv papers by author."""
    papers = await arxiv_client.search_by_author(author, max_results=max_results)
    return json.dumps([asdict(p) for p in papers], ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════
# Agentic RAG Workflow
# ════════════════════════════════════════════════════════════

async def agentic_rag_search(
    query: str,
    max_results: int = 5,
    ollama_model: str = "",
    ollama_base_url: str = "http://localhost:11434",
    use_ollama: bool = False,
) -> str:
    """End-to-end Agentic RAG: guardrail → retrieve → grade → rewrite → generate.
    
    1. Guardrail: определяет, нужен ли поиск по arXiv
    2. Retrieve: ищет релевантные статьи
    3. Grade: оценивает релевантность найденного
    4. Rewrite: при необходимости переписывает запрос
    5. Generate: генерирует ответ на основе контекста
    
    Returns JSON with structured result and reasoning trace.
    """
    trace = []
    result = {"query": query, "steps": []}
    
    # Step 1: Guardrail
    trace.append("guardrail: checking if query needs arxiv retrieval")
    guardrail = _guardrail_check(query)
    result["guardrail"] = guardrail
    result["steps"].append({"step": "guardrail", "decision": guardrail["action"]})
    
    if guardrail["action"] == "answer":
        result["answer"] = guardrail.get("answer", "I can answer directly.")
        result["trace"] = trace
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    search_query = guardrail.get("rewritten_query", query)
    
    # Step 2: Retrieve
    trace.append(f"retrieve: searching arxiv for '{search_query}'")
    papers = await arxiv_client.search(query=search_query, max_results=max_results)
    
    if not papers:
        result["answer"] = "No relevant papers found on arXiv for this query."
        result["trace"] = trace
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    result["papers_found"] = len(papers)
    result["steps"].append({"step": "retrieve", "papers": len(papers), "query": search_query})
    
    # Step 3: Grade documents
    trace.append("grade: evaluating relevance of retrieved papers")
    graded = _grade_papers(query, papers)
    relevant = [g for g in graded if g["is_relevant"]]
    result["grading"] = {"total": len(graded), "relevant": len(relevant)}
    result["steps"].append({"step": "grade", "relevant": len(relevant), "total": len(graded)})
    
    if not relevant:
        # Step 3b: Rewrite and retry once
        trace.append("rewrite: no relevant papers, trying rewritten query")
        rewritten = _rewrite_query(query)
        result["steps"].append({"step": "rewrite", "original": search_query, "rewritten": rewritten})
        
        papers2 = await arxiv_client.search(query=rewritten, max_results=max_results)
        if papers2:
            graded2 = _grade_papers(query, papers2)
            relevant = [g for g in graded2 if g["is_relevant"]]
            result["grading"]["retry_relevant"] = len(relevant)
            if relevant:
                papers = papers2
                graded = graded2
    
    if not relevant:
        result["answer"] = (
            "Searched arXiv but found no directly relevant papers. "
            "Try a different query or check the search results below."
        )
        result["fallback_papers"] = [asdict(p) for p in papers[:3]]
        result["trace"] = trace
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    # Step 5: Generate answer
    trace.append(f"generate: building answer from {len(relevant)} relevant papers")
    
    # Build context from relevant papers
    chunks = []
    for g in relevant:
        chunks.append({
            "text": g["paper"].abstract,
            "source": g["paper"].arxiv_id,
        })
    
    # Try Ollama generation if available
    answer = ""
    if use_ollama and ollama_model:
        try:
            prompt = prompt_builder.build_prompt(query, chunks)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{ollama_base_url}/api/generate",
                    json={"model": ollama_model, "prompt": prompt, "stream": False},
                )
                if resp.status_code == 200:
                    answer = resp.json().get("response", "")
        except Exception as e:
            trace.append(f"ollama error: {e}")
    
    # Fallback: structured summary
    if not answer:
        answer = _build_fallback_answer(query, relevant)
    
    result["answer"] = answer
    result["sources"] = [
        {"arxiv_id": g["paper"].arxiv_id, "title": g["paper"].title, "authors": g["paper"].authors[:3]}
        for g in relevant[:5]
    ]
    result["trace"] = trace
    return json.dumps(result, ensure_ascii=False, indent=2)


def _guardrail_check(query: str) -> Dict[str, str]:
    """Check if query needs arxiv retrieval or can be answered directly."""
    research_keywords = [
        "paper", "arxiv", "research", "study", "method", "algorithm", "model",
        "transformer", "attention", "neural", "deep learning", "LLM", "GPT",
        "diffusion", "reinforcement", "embedding", "attention", "CNN", "RNN",
        "publication", "sota", "state of the art", "SOTA", "survey", "review",
        "latest", "recent", "trend", "breakthrough", "novel", "approach"
    ]
    q = query.lower()
    found = [kw for kw in research_keywords if kw in q]
    
    if len(found) >= 1 or len(query.split()) > 5:
        return {"action": "retrieve", "rewritten_query": query}
    else:
        return {"action": "answer", "answer": f"This appears to be a general question. For academic paper search, try rephrasing with specific research terms."}


def _grade_papers(query: str, papers: List[ArxivPaper]) -> List[Dict]:
    """Grade papers for relevance to the query."""
    q_words = set(query.lower().split())
    q_words -= {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or"}
    
    graded = []
    for paper in papers:
        text = f"{paper.title} {paper.abstract}".lower()
        text_words = set(text.split())
        
        # Simple keyword overlap scoring
        overlap = len(q_words & text_words)
        score = overlap / max(len(q_words), 1) if q_words else 0
        
        graded.append({
            "paper": paper,
            "score": round(score, 3),
            "is_relevant": score > 0.1 or any(w in text for w in q_words if len(w) > 4),
        })
    
    # Sort by relevance
    graded.sort(key=lambda x: x["score"], reverse=True)
    return graded


def _rewrite_query(query: str) -> str:
    """Rewrite query for better academic paper retrieval."""
    prefixes = ["ti:", "abs:"]
    # If query is short, add broad context
    if len(query.split()) <= 3:
        return f"all:{query}"
    return query


def _build_fallback_answer(query: str, relevant: List[Dict]) -> str:
    """Build a structured answer from relevant papers without LLM."""
    lines = [f"Based on arXiv papers, here's what I found about '{query}':\n"]
    for i, g in enumerate(relevant[:5], 1):
        paper = g["paper"]
        lines.append(f"{i}. {paper.title} (arXiv:{paper.arxiv_id})")
        lines.append(f"   Authors: {', '.join(paper.authors[:3])}")
        lines.append(f"   Published: {paper.published_date[:10]}")
        # First 150 chars of abstract
        abs_preview = paper.abstract[:200] + "..." if len(paper.abstract) > 200 else paper.abstract
        lines.append(f"   Abstract: {abs_preview}\n")
    
    lines.append(f"\nRetrieved {len(relevant)} relevant papers from arXiv.")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# MCP convenience wrapper for Agentic RAG
# ════════════════════════════════════════════════════════════

async def mcp_agentic_rag(query: str, max_results: int = 5) -> str:
    """Run agentic RAG workflow: search arxiv, evaluate relevance, generate answer."""
    return await agentic_rag_search(query=query, max_results=max_results)


# Cleanup
if __name__ == "__main__":
    # Quick test
    async def test():
        papers = await arxiv_client.search(query="cat:cs.AI AND ti:transformer", max_results=3)
        print(f"Found {len(papers)} papers")
        for p in papers:
            print(f"  - {p.title[:80]}... ({p.arxiv_id})")

    asyncio.run(test())
