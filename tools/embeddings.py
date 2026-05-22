from __future__ import annotations

import os
import re
import json
import pickle
import hashlib
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from tools.llm_client import get_client, LLMClient

REPO_ROOT = Path(__file__).parent.parent
EMBEDDINGS_FILE = REPO_ROOT / "wiki" / ".embeddings.pkl"

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def estimate_tokens(text: str) -> int:
    cjk_count = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    latin_count = len(text) - cjk_count
    return int(cjk_count * 1.5 + latin_count * 0.3)


def split_by_paragraphs(content: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not content.strip():
        return []
    paragraphs = re.split(r'\n\s*\n', content)
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = current + "\n\n" + para if current else para
        if estimate_tokens(candidate) > chunk_size and current:
            chunks.append(current.strip())
            overlap_text = current
            tokens_in_overlap = 0
            overlap_paras = overlap_text.split("\n\n")
            keep = []
            for op in reversed(overlap_paras):
                t = estimate_tokens(op)
                if tokens_in_overlap + t > overlap:
                    break
                keep.insert(0, op)
                tokens_in_overlap += t
            current = "\n\n".join(keep)
            if current:
                current += "\n\n" + para
            else:
                current = para
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks or [content.strip()]


def embed_text(text: str | list[str], model: str | None = None) -> list[float] | list[list[float]]:
    if model is None:
        model = os.environ.get("LLM_EMBEDDING_MODEL", "text-embedding-3-small")
    try:
        from litellm import embedding
    except ImportError:
        raise RuntimeError("litellm not installed")
    single = isinstance(text, str)
    inputs = [text] if single else text
    resp = embedding(model=model, input=inputs)
    results = [item["embedding"] for item in resp.data]
    return results[0] if single else results


class EmbeddingStore:
    def __init__(self, persist_path: str | Path | None = None):
        self._path = Path(persist_path) if persist_path else EMBEDDINGS_FILE
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}
        self._embeddings: dict[str, np.ndarray] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "rb") as f:
                    data = pickle.load(f)
                self._entries = data.get("entries", {})
                self._embeddings = {k: np.array(v) for k, v in data.get("embeddings", {}).items()}
            except Exception:
                self._entries = {}
                self._embeddings = {}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "wb") as f:
            pickle.dump({
                "entries": self._entries,
                "embeddings": {k: v.tolist() for k, v in self._embeddings.items()},
            }, f)

    def index_page(self, page_path: str, content: str) -> int:
        chunks = split_by_paragraphs(content)
        if not chunks:
            return 0
        with self._lock:
            keys_to_remove = [k for k in self._entries if self._entries[k]["source"] == page_path]
            for k in keys_to_remove:
                self._entries.pop(k, None)
                self._embeddings.pop(k, None)
            ids = [f"{page_path}#{i}" for i in range(len(chunks))]
            batch = []
            batch_ids = []
            for i, chunk in enumerate(chunks):
                batch.append(chunk)
                batch_ids.append(ids[i])
                if len(batch) >= 20:
                    embs = embed_text(batch)
                    for bid, emb, orig_chunk in zip(batch_ids, embs, batch):
                        self._entries[bid] = {"source": page_path, "text": orig_chunk}
                        self._embeddings[bid] = np.array(emb, dtype=np.float32)
                    batch = []
                    batch_ids = []
            if batch:
                embs = embed_text(batch)
                for bid, emb, orig_chunk in zip(batch_ids, embs, batch):
                    self._entries[bid] = {"source": page_path, "text": orig_chunk}
                    self._embeddings[bid] = np.array(emb, dtype=np.float32)
            self._save()
        return len(chunks)

    def search(self, query: str, top_k: int = 20, query_embedding: np.ndarray | None = None) -> list[dict]:
        with self._lock:
            if not self._embeddings:
                return []
            q_emb = np.array(query_embedding if query_embedding is not None else embed_text(query), dtype=np.float32)
            keys = list(self._embeddings.keys())
            if not keys:
                return []
            matrix = np.stack([self._embeddings[k] for k in keys])
            sims = matrix @ q_emb
            top_indices = np.argsort(-sims)[:top_k]
            seen_sources: dict[str, float] = {}
            for idx in top_indices:
                key = keys[idx]
                source = self._entries[key]["source"]
                score = float(sims[idx])
                if source not in seen_sources or score > seen_sources[source]:
                    seen_sources[source] = score
            sorted_sources = sorted(seen_sources.items(), key=lambda x: -x[1])
            return [{"path": src, "score": scr} for src, scr in sorted_sources]

    def remove_page(self, page_path: str):
        with self._lock:
            keys_to_remove = [k for k in self._entries if self._entries[k]["source"] == page_path]
            for k in keys_to_remove:
                self._entries.pop(k, None)
                self._embeddings.pop(k, None)
            self._save()

    def count(self) -> int:
        with self._lock:
            return len(self._embeddings)


_store: Optional[EmbeddingStore] = None


def get_store() -> EmbeddingStore:
    global _store
    if _store is None:
        _store = EmbeddingStore()
    return _store


def init_store(persist_path: str | Path | None = None):
    global _store
    _store = EmbeddingStore(persist_path)
