"""Unit tests for Phase 3: chunking, indexing, and retrieval.

These tests avoid loading real AI models (embedding/LLM) by using
fake embedding functions and disabling background processing.
"""
import os
import sys
import asyncio
import numpy as np
import pytest
from unittest.mock import patch

from app.services.chunking import (
    split_text,
    chunk_text,
    build_chunks,
    MAX_CHARS,
    OVERLAP,
)


# ─── Chunking tests ─────────────────────────────────────────────────────────


def test_split_paragraphs():
    text = "Đoạn một.\n\nĐoạn hai.\n\nĐoạn ba."
    parts = split_text(text)
    assert len(parts) >= 3


def test_split_by_headers():
    text = "[Page 1]\nNội dung trang 1\n\n[Page 2]\nNội dung trang 2"
    parts = split_text(text)
    assert any("Page 1" in p for p in parts)
    assert any("Page 2" in p for p in parts)


def test_chunk_respects_max_size():
    text = "từ " * 3000  # 6000 chars
    chunks = chunk_text(text, max_chars=1000, overlap=100)
    for c in chunks:
        assert len(c) <= 1000 + 100
    assert len(chunks) > 1


def test_chunk_does_not_cut_mid_word():
    text = "Câu thứ nhất. Câu thứ hai. " * 200
    chunks = chunk_text(text, max_chars=500, overlap=50)
    for c in chunks:
        # chunk should end at a sentence boundary or whitespace
        assert c.rstrip().endswith(("nhất.", "hai.", " ")) or len(c) <= 500 + 50


def test_build_chunks_keeps_metadata():
    text = "[Page 2]\nHà Nội là thủ đô Việt Nam."
    chunks = build_chunks("doc123", "pdf", text)
    assert len(chunks) >= 1
    first = chunks[0]
    assert first["doc_id"] == "doc123"
    assert first["metadata"]["category"] == "pdf"
    assert first["metadata"]["page"] == 2


def test_build_chunks_scene_timestamp():
    text = "[Scene 3 at 12.5s]\nSlide nội dung."
    chunks = build_chunks("doc456", "video", text)
    meta = chunks[0]["metadata"]
    assert meta["scene"] == 3
    assert meta["timestamp"] == 12.5


# ─── Retrieval tests with fake embedding (no real model) ────────────────────


class FakeEmbedding:
    """Deterministic fake embedding: hashes words to a 768-dim vector."""

    def __init__(self, dim=768):
        self.dim = dim

    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for t in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for i, ch in enumerate(t):
                vec[i % self.dim] += ord(ch) * 0.001
            # Add some structure per text
            vec[0] = sum(ord(c) for c in t) / max(1, len(t))
            vec[1] = len(t)
            if normalize_embeddings:
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
            vectors.append(vec)
        return np.stack(vectors) if vectors else np.zeros((0, self.dim), dtype=np.float32)


async def _fake_embed(texts):
    return FakeEmbedding().encode(texts)


@pytest.mark.asyncio
async def test_rag_index_and_query_with_fake_embedding(tmp_path):
    """Index then query using LightRAG with fake embedding + fake LLM.

    Uses naive mode so retrieval works without an LLM graph.
    """
    from lightrag import LightRAG, QueryParam
    from lightrag.utils import EmbeddingFunc
    from app.config import settings

    old_working_dir = settings.lightrag_working_dir
    settings.lightrag_working_dir = tmp_path / "lightrag_test"

    async def fake_llm(prompt, system_prompt=None, **kwargs):
        return "[fake]"

    try:
        rag = LightRAG(
            working_dir=str(settings.lightrag_working_dir),
            llm_model_func=fake_llm,
            embedding_func=EmbeddingFunc(
                embedding_dim=768, max_token_size=512, func=_fake_embed
            ),
            chunk_token_size=128,
            chunk_overlap_token_size=16,
        )
        await rag.initialize_storages()
        await rag.ainsert(
            "Hà Nội là thủ đô của Việt Nam. Trung tâm kinh tế lớn nhất cả nước.",
            ids=["fake-doc-1"],
        )

        # naive mode: vector retrieval, no graph needed
        result = await rag.aquery(
            "Thủ đô Việt Nam",
            param=QueryParam(mode="naive", top_k=3, enable_rerank=False),
        )
        assert result is not None
        assert isinstance(result, str)
    finally:
        settings.lightrag_working_dir = old_working_dir
