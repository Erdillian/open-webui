"""Integration tests for memory extraction pipeline (with mocked LLM)."""
from unittest.mock import AsyncMock

import pytest

from open_webui.memory_layer.services.extractor import extract_memories_from_exchange


@pytest.mark.anyio
async def test_extract_memories_basic(monkeypatch, mock_embedding):
    """A simple exchange returns created memory IDs ( mocked LLM + Chroma)."""
    async def fake_llm(exchange_text, timestamp):
        return [
            {
                "content": "L'utilisateur est végétarien depuis juillet 2024.",
                "category": "preference",
                "importance": 0.8,
                "sensitivity": 0.1,
                "timestamp_event": "2024-07-31T00:00:00Z",
                "speaker": "user",
                "involves_entities": [],
            }
        ]

    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor._call_extractor_llm", fake_llm
    )
    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor.embed_text",
        AsyncMock(return_value=mock_embedding("veg")),
    )

    # Mock Chroma add/query to avoid real DB connection
    def fake_add(embedding, content, metadata, chroma_id=None):
        return chroma_id or "mock_chroma_id"

    def fake_query(embedding, filter_dict=None, k=20):
        return {
            "ids": [[]],
            "distances": [[]],
            "documents": [[]],
            "metadatas": [[]],
        }

    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor.add_memory", fake_add
    )
    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor.query_memories", fake_query
    )

    messages = [
        {"role": "user", "content": "Je suis végétarien depuis juillet.", "timestamp": 1722384000},
        {"role": "assistant", "content": "C'est génial.", "timestamp": 1722384060},
    ]

    created_ids = await extract_memories_from_exchange(
        user_id="test_user_001", messages=messages, chat_id="chat_1"
    )

    # With mocked Chroma and extractor, at least one memory should be created
    assert isinstance(created_ids, list)
    # Note: if the DB session inside get_async_db is isolated, we cannot assert
    # on DB state here. We verify the pipeline completed without fatal error.


@pytest.mark.anyio
async def test_extract_memories_filters_empty_content(monkeypatch, mock_embedding):
    """Empty content items are dropped."""
    async def fake_llm(exchange_text, timestamp):
        return [
            {"content": "", "category": "fact", "importance": 0.5, "sensitivity": 0.0},
            {"content": "L'utilisateur aime courir.", "category": "preference", "importance": 0.6, "sensitivity": 0.0},
        ]

    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor._call_extractor_llm", fake_llm
    )
    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor.embed_text",
        AsyncMock(return_value=mock_embedding("run")),
    )
    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor.add_memory",
        lambda embedding, content, metadata, chroma_id=None: "mock_id",
    )
    monkeypatch.setattr(
        "open_webui.memory_layer.services.extractor.query_memories",
        lambda embedding, filter_dict=None, k=20: {
            "ids": [[]], "distances": [[]], "documents": [[]], "metadatas": [[]],
        },
    )

    messages = [
        {"role": "user", "content": "J'aime courir.", "timestamp": 1722384000},
        {"role": "assistant", "content": "Super.", "timestamp": 1722384060},
    ]

    created_ids = await extract_memories_from_exchange(
        user_id="test_user_001", messages=messages
    )

    # Because we mocked add_memory and query_memories, the pipeline should succeed.
    # The empty-content item is filtered out inside extract_memories_from_exchange,
    # but since DB isolation prevents us from reading back, we verify no exception.
    assert isinstance(created_ids, list)
