"""Unit tests for duplicate detection and conflict detection logic."""
import math

import pytest

from open_webui.memory_layer.services.extractor import _detect_duplicates, _detect_conflicts


class TestDetectDuplicates:
    @pytest.mark.anyio
    async def test_exact_duplicate(self, monkeypatch, mock_embedding):
        emb = mock_embedding("duplicate text")

        # Mock query_memories to return a near-identical result
        def fake_query(embedding, filter_dict, k):
            return {
                "ids": [["chroma_1"]],
                "distances": [[0.02]],  # similarity = 0.98
                "metadatas": [[{"user_id": "u1"}]],
            }

        monkeypatch.setattr(
            "open_webui.memory_layer.services.extractor.query_memories", fake_query
        )

        result = await _detect_duplicates(emb, user_id="u1", threshold=0.92)
        assert result is not None
        assert result["similarity"] == pytest.approx(0.98, abs=1e-2)

    @pytest.mark.anyio
    async def test_no_duplicate(self, monkeypatch, mock_embedding):
        emb = mock_embedding("unique text")

        def fake_query(embedding, filter_dict, k):
            return {
                "ids": [[]],
                "distances": [[]],
                "metadatas": [[]],
            }

        monkeypatch.setattr(
            "open_webui.memory_layer.services.extractor.query_memories", fake_query
        )

        result = await _detect_duplicates(emb, user_id="u1", threshold=0.92)
        assert result is None


class TestDetectConflicts:
    @pytest.mark.anyio
    async def test_conflict_detected(self, monkeypatch, mock_embedding):
        emb = mock_embedding("j'ai arrêté le café")

        def fake_query(embedding, filter_dict, k):
            return {
                "ids": [["chroma_old"]],
                "distances": [[0.15]],  # similarity = 0.85
                "documents": [["J'adore le café le matin"]],
                "metadatas": [[{"user_id": "u1"}]],
            }

        monkeypatch.setattr(
            "open_webui.memory_layer.services.extractor.query_memories", fake_query
        )

        conflicts = await _detect_conflicts(
            new_embedding=emb,
            new_content="j'ai arrêté le café",
            user_id="u1",
            low_threshold=0.75,
            high_threshold=0.92,
        )
        assert len(conflicts) == 1
        assert conflicts[0]["similarity"] == pytest.approx(0.85, abs=1e-2)

    @pytest.mark.anyio
    async def test_no_conflict_too_similar(self, monkeypatch, mock_embedding):
        # Similarity above high_threshold (0.92) → duplicate, not conflict
        emb = mock_embedding("j'aime le café")

        def fake_query(embedding, filter_dict, k):
            return {
                "ids": [["chroma_same"]],
                "distances": [[0.05]],  # similarity = 0.95
                "documents": [["J'aime le café"]],
                "metadatas": [[{"user_id": "u1"}]],
            }

        monkeypatch.setattr(
            "open_webui.memory_layer.services.extractor.query_memories", fake_query
        )

        conflicts = await _detect_conflicts(
            new_embedding=emb,
            new_content="j'aime le café",
            user_id="u1",
            low_threshold=0.75,
            high_threshold=0.92,
        )
        assert len(conflicts) == 0

    @pytest.mark.anyio
    async def test_no_conflict_too_different(self, monkeypatch, mock_embedding):
        emb = mock_embedding("je préfère le thé")

        def fake_query(embedding, filter_dict, k):
            return {
                "ids": [["chroma_diff"]],
                "distances": [[0.5]],  # similarity = 0.5
                "documents": [["J'aime le café"]],
                "metadatas": [[{"user_id": "u1"}]],
            }

        monkeypatch.setattr(
            "open_webui.memory_layer.services.extractor.query_memories", fake_query
        )

        conflicts = await _detect_conflicts(
            new_embedding=emb,
            new_content="je préfère le thé",
            user_id="u1",
            low_threshold=0.75,
            high_threshold=0.92,
        )
        assert len(conflicts) == 0
