import json
import pickle
import tempfile
from pathlib import Path

import numpy as np
import pytest

from tools.embeddings import (
    estimate_tokens,
    split_by_paragraphs,
    EmbeddingStore,
)


class TestEstimateTokens:
    def test_latin_text(self):
        t = estimate_tokens("hello world")
        assert t > 0

    def test_cjk_text(self):
        t = estimate_tokens("中文测试文本")
        assert t > 0

    def test_cjk_heavier_than_latin(self):
        cjk = estimate_tokens("中文测试")
        latin = estimate_tokens("test")
        assert cjk > latin

    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_mixed(self):
        t = estimate_tokens("hello 世界")
        assert t > 1


class TestSplitByParagraphs:
    def test_single_para(self):
        chunks = split_by_paragraphs("Just one paragraph.", chunk_size=500)
        assert len(chunks) == 1

    def test_multiple_paras(self):
        text = "Para A.\n\nPara B.\n\nPara C."
        chunks = split_by_paragraphs(text, chunk_size=500)
        assert len(chunks) == 1

    def test_chunk_boundary(self):
        text = "\n\n".join(["word"] * 50)
        chunks = split_by_paragraphs(text, chunk_size=10)
        assert len(chunks) > 1

    def test_empty_string(self):
        assert split_by_paragraphs("") == []

    def test_single_word(self):
        chunks = split_by_paragraphs("hello")
        assert chunks == ["hello"]

    def test_preserves_content(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = split_by_paragraphs(text, chunk_size=500)
        combined = "\n\n".join(chunks)
        assert "First paragraph." in combined
        assert "Second paragraph." in combined
        assert "Third paragraph." in combined


class TestEmbeddingStore:
    def test_empty_store_count(self, tmp_path):
        store = EmbeddingStore(tmp_path / "test.pkl")
        assert store.count() == 0

    def test_empty_store_search(self, tmp_path):
        store = EmbeddingStore(tmp_path / "test.pkl")
        assert store.search("test") == []

    def test_persist_and_reload(self, tmp_path):
        p = tmp_path / "emb.pkl"
        store = EmbeddingStore(p)
        # Manually inject an entry and embedding to avoid API call
        store._entries = {"test#0": {"source": "test.md", "text": "hello"}}
        store._embeddings = {"test#0": np.array([0.1, 0.2, 0.3], dtype=np.float32)}
        store._save()
        store2 = EmbeddingStore(p)
        assert store2.count() == 1
        assert store2._entries["test#0"]["source"] == "test.md"

    def test_remove_page(self, tmp_path):
        p = tmp_path / "emb.pkl"
        store = EmbeddingStore(p)
        store._entries = {"a#0": {"source": "a.md", "text": "a"}, "b#0": {"source": "b.md", "text": "b"}}
        store._embeddings = {"a#0": np.array([0.1]), "b#0": np.array([0.2])}
        store.remove_page("a.md")
        assert store.count() == 1
        assert "b#0" in store._entries

    def test_cosine_search(self, tmp_path):
        p = tmp_path / "emb.pkl"
        store = EmbeddingStore(p)
        store._entries = {
            "doc1#0": {"source": "doc1.md", "text": "cat"},
            "doc2#0": {"source": "doc2.md", "text": "dog"},
            "doc3#0": {"source": "doc3.md", "text": "car"},
        }
        store._embeddings = {
            "doc1#0": np.array([1.0, 0.0], dtype=np.float32),
            "doc2#0": np.array([0.0, 1.0], dtype=np.float32),
            "doc3#0": np.array([1.0, 0.5], dtype=np.float32),
        }
        # Query embedding close to doc1
        q_emb = np.array([1.0, 0.0], dtype=np.float32)
        results = store.search("cat", top_k=2, query_embedding=q_emb)
        assert len(results) <= 2
        assert results[0]["path"] == "doc1.md"
        assert results[0]["score"] > 0.5
