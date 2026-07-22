#!/usr/bin/env python3
"""
rebuild_nomic_index.py
Re-encodes all passages with nomic-embed-text-v1.5 and saves pre-computed
embedding matrix alongside the JSONL so leann_daemon loads instantly.

Usage: python rebuild_nomic_index.py
"""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, "C:/vazus/pyenv")

# Remove offline lock — nomic needs to read cached custom code
for k in ["HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"]:
    os.environ.pop(k, None)

PASSAGES = Path("C:/vazus/pyenv/leann-indexes/pyenv-project.leann.passages.jsonl")
MODEL_DIR = "C:/vazus/models/nomic-embed-v1.5"
EMBED_OUT = Path("C:/vazus/pyenv/leann-indexes/pyenv-project.leann.embeddings.npy")

print(f"Loading nomic-embed-text-v1.5 from {MODEL_DIR}...")
from sentence_transformers import SentenceTransformer
import numpy as np

m = SentenceTransformer(MODEL_DIR, trust_remote_code=True)
dim = m.get_sentence_embedding_dimension()
print(f"  Model OK: {dim}-dim")

print(f"Loading passages from {PASSAGES}...")
texts = [json.loads(l)["text"] for l in PASSAGES.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"  {len(texts)} passages")

print("Encoding (nomic: prefix with 'search_document:')...")
t0 = time.time()
# nomic-embed uses task-specific prefixes
prefixed = [f"search_document: {t[:400]}" for t in texts]
embeddings = m.encode(prefixed, normalize_embeddings=True,
                       batch_size=64, show_progress_bar=True,
                       convert_to_numpy=True)
elapsed = time.time() - t0
print(f"  Done: {embeddings.shape} in {elapsed:.1f}s ({len(texts)/elapsed:.0f} texts/s)")

print(f"Saving embeddings to {EMBED_OUT}...")
np.save(EMBED_OUT, embeddings)
print(f"  Saved: {EMBED_OUT.stat().st_size // 1024 // 1024} MB")
print("DONE — restart leann_daemon to use new embeddings")
