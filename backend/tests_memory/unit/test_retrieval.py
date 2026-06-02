"""Unit tests for memory retrieval, scoring and re-ranking."""
import math
import time

import pytest

from open_webui.memory_layer.retrieval.retriever import (
    _recency_decay,
    _sensitivity_penalty,
    _score_memory,
)


class TestRecencyDecay:
    def test_today(self):
        now = int(time.time())
        assert _recency_decay(now) == pytest.approx(1.0, rel=1e-3)

    def test_future(self):
        future = int(time.time()) + 86400
        assert _recency_decay(future) == pytest.approx(1.0, rel=1e-3)

    def test_one_month_ago(self):
        now = int(time.time())
        one_month = now - 30 * 86400
        # half-life = 30 days, so after exactly 30 days decay = exp(-1) ≈ 0.368
        assert _recency_decay(one_month) == pytest.approx(0.368, abs=0.05)

    def test_none(self):
        assert _recency_decay(None) == pytest.approx(0.5, rel=1e-3)


class TestSensitivityPenalty:
    def test_high_sensitivity_unrelated_query(self):
        # Embeddings are orthogonal → similarity = 0
        q = [1.0, 0.0, 0.0]
        m = [0.0, 1.0, 0.0]
        pen = _sensitivity_penalty(0.8, q, m)
        # sim = 0, so max(0, 0-0.6)=0, penalty = 0.8 * 1 = 0.8
        assert pen == pytest.approx(0.8, abs=1e-3)

    def test_high_sensitivity_related_query(self):
        # Embeddings are identical → similarity = 1
        q = [1.0, 0.0, 0.0]
        m = [1.0, 0.0, 0.0]
        pen = _sensitivity_penalty(0.8, q, m)
        # sim = 1, max(0, 1-0.6)=0.4, penalty = 0.8 * (1-0.4) = 0.8 * 0.6 = 0.48
        assert pen == pytest.approx(0.48, abs=1e-3)

    def test_zero_sensitivity(self):
        q = [1.0, 0.0, 0.0]
        m = [0.0, 1.0, 0.0]
        pen = _sensitivity_penalty(0.0, q, m)
        assert pen == pytest.approx(0.0, abs=1e-3)


class TestScoreMemory:
    def test_perfect_score(self):
        # distance=0, importance=1, today, pinned, sensitivity=0
        now = int(time.time())
        q = [1.0, 0.0]
        m = [1.0, 0.0]
        score = _score_memory(
            cosine_distance=0.0,
            importance=1.0,
            timestamp=now,
            pinned=True,
            sensitivity=0.0,
            query_embedding=q,
            memory_embedding=m,
        )
        # 0.6*1 + 0.2*1 + 0.1*1 + 0.1*1 - 0.3*0 = 1.0
        assert score == pytest.approx(1.0, abs=1e-3)

    def test_old_unpinned_low_importance(self):
        now = int(time.time())
        old = now - 90 * 86400
        q = [1.0, 0.0]
        m = [0.0, 1.0]
        score = _score_memory(
            cosine_distance=0.5,  # sim=0.5
            importance=0.0,
            timestamp=old,
            pinned=False,
            sensitivity=0.0,
            query_embedding=q,
            memory_embedding=m,
        )
        recency = _recency_decay(old)
        expected = 0.6 * 0.5 + 0.2 * 0.0 + 0.1 * recency + 0.1 * 0.0 - 0.3 * 0.0
        assert score == pytest.approx(expected, abs=1e-3)

    def test_pinned_boost(self):
        now = int(time.time())
        q = [1.0, 0.0]
        m = [0.0, 1.0]
        score_unpinned = _score_memory(
            cosine_distance=0.5, importance=0.5, timestamp=now,
            pinned=False, sensitivity=0.0,
            query_embedding=q, memory_embedding=m,
        )
        score_pinned = _score_memory(
            cosine_distance=0.5, importance=0.5, timestamp=now,
            pinned=True, sensitivity=0.0,
            query_embedding=q, memory_embedding=m,
        )
        assert score_pinned > score_unpinned
        assert score_pinned - score_unpinned == pytest.approx(0.1, abs=1e-3)
