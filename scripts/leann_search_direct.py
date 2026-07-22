#!/usr/bin/env python3
"""
leann_search_direct.py — Direct semantic search on LEANN passages.
Bypasses LEANN's ZMQ daemon (broken on Windows) by loading the
passages JSONL + embedding model directly.

Usage (from hybrid worker via HTTP or direct import):
    from leann_search_direct import search
    results = search("spawn background worker", top_k=5)
"""
import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Optional

def normalize_memory_chunk(raw_text: str) -> str:
    """
    Episodic Memory Normalization (Concordia pattern).
    Uses a fast LLM call to rewrite raw logs/text into structured episodic memory.
    Format: [At TIME], [AGENT] did [ACTION] and observed [CONSEQUENCE].
    """
    from dnts_core.utils import load_adapter_key
    prompt = (
        "You are an episodic memory normalizer. Rewrite the following raw text into a strict, concise, chronological format:\n"
        "[At TIME/CONTEXT], [AGENT/COMPONENT] did [ACTION] and observed [CONSEQUENCE/STATE].\n\n"
        "Raw text:\n" + raw_text
    )
    try:
        api_key = load_adapter_key()
        resp = requests.post(
            "http://127.0.0.1:5001/v1/chat/completions",
            json={
                "model": "gemini-3.5-flash-lite",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 150
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[leann-direct] Memory normalization failed: {e}", file=sys.stderr)
    return raw_text


PASSAGES_FILE = os.environ.get(
    "LEANN_PASSAGES",
    "C:/vazus/pyenv/leann-indexes/pyenv-project.leann.passages.jsonl"
)
# nomic-embed-text-v1.5 (768-dim MRL, MTEB ~62) — better than all-MiniLM (384-dim, MTEB ~56)
# Override via LEANN_MODEL env var if needed
MODEL_NAME = os.environ.get(
    "LEANN_MODEL",
    "C:/vazus/models/nomic-embed-v1.5"
)
# nomic requires trust_remote_code=True
TRUST_REMOTE = os.environ.get("LEANN_TRUST_REMOTE", "1") == "1"

# Module-level cache so repeated calls in same process don't reload
_model  = None
_corpus_texts:  list[str]  = []
_corpus_embeds = None  # np.ndarray shape (N, 384)


def _load() -> None:
    global _model, _corpus_texts, _corpus_embeds
    if _model is not None:
        return  # already loaded

    try:
        if os.environ.get("USE_GOOGLE_EMBEDDING") == "1":
            raise RuntimeError("Forced Google GenAI embedding fallback")
        from sentence_transformers import SentenceTransformer
        import numpy as np

        print(f"[leann-direct] Loading model {MODEL_NAME}...", file=sys.stderr, flush=True)
        if not TRUST_REMOTE:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _model = SentenceTransformer(MODEL_NAME, trust_remote_code=TRUST_REMOTE)
    except Exception as e:
        print(f"[leann-direct] Local model failed ({e}), falling back to Google Cloud GenAI...", file=sys.stderr, flush=True)
        import numpy as np
        class GoogleEmbeddingModel:
            def __init__(self):
                from google import genai
                self.client = genai.Client()
            def encode(self, texts, convert_to_numpy=True, **kwargs):
                res = self.client.models.embed_content(
                    model='text-embedding-004',
                    contents=texts
                )
                embeds = [e.values for e in res.embeddings]
                if convert_to_numpy:
                    return np.array(embeds, dtype=np.float32)
                return embeds
        _model = GoogleEmbeddingModel()

    print(f"[leann-direct] Loading passages from {PASSAGES_FILE}...", file=sys.stderr, flush=True)
    texts = []
    with open(PASSAGES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            texts.append(obj.get("text", ""))

    # Check for pre-computed .npy embedding cache (skip re-encoding for faster startup)
    embed_cache = Path(str(PASSAGES_FILE).replace(".passages.jsonl", ".embeddings.npy"))
    if Path(embed_cache).exists():
        print(f"[leann-direct] Loading cached embeddings from {embed_cache}...", file=sys.stderr, flush=True)
        _corpus_texts  = texts
        _corpus_embeds = np.load(embed_cache)
        print(f"[leann-direct] Ready. Index shape: {_corpus_embeds.shape} (cached)", file=sys.stderr, flush=True)
        return

    print(f"[leann-direct] Encoding {len(texts)} passages...", file=sys.stderr, flush=True)
    _corpus_texts  = texts
    _corpus_embeds = _model.encode(texts, convert_to_numpy=True, show_progress_bar=False,
                                   normalize_embeddings=True, batch_size=8)
    
    # Apply Matryoshka 256-dim truncation and re-normalize
    _corpus_embeds = _corpus_embeds[:, :256]
    import numpy as np
    _corpus_embeds = _corpus_embeds / np.linalg.norm(_corpus_embeds, axis=1, keepdims=True)
    
    # Save the cache so we don't need to re-encode
    np.save(embed_cache, _corpus_embeds)
    print(f"[leann-direct] Ready. Index shape: {_corpus_embeds.shape}", file=sys.stderr, flush=True)


def search(query: str, top_k: int = 5) -> list[dict]:
    """Return top_k semantically similar passages for query."""
    import numpy as np
    _load()
    q_emb = _model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    # Apply Matryoshka 256-dim truncation and re-normalize for the query
    q_emb = q_emb[:, :256]
    q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
    
    scores = (_corpus_embeds @ q_emb.T).squeeze()  # cosine similarity (normalised)
    top_idx = scores.argsort()[::-1][:top_k]
    return [
        {"text": _corpus_texts[i], "score": float(scores[i]), "source": "leann:pyenv"}
        for i in top_idx
    ]


if __name__ == "__main__":
    # Quick self-test
    query = sys.argv[1] if len(sys.argv) > 1 else "spawn background worker async"
    t0 = time.time()
    results = search(query, top_k=3)
    print(f"\n=== Results for: '{query}' ({time.time()-t0:.1f}s) ===")
    for i, r in enumerate(results, 1):
        print(f"\n{i}. [score={r['score']:.3f}]")
        print(r["text"][:200])
