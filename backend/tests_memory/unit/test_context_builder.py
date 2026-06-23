"""Unit tests for context builder helpers: date markers, humanized delta, prompt assembly."""
import time
from datetime import datetime

import pytest

from open_webui.memory_layer.services.context_builder import (
    _format_humanized_delta,
    _build_timestamp_block,
    _build_memories_block,
    _build_profile_block,
    inject_date_markers,
)


class TestHumanizedDelta:
    def test_none(self):
        assert _format_humanized_delta(None) == "inconnu"

    def test_less_than_minute(self):
        now = int(time.time())
        assert _format_humanized_delta(now - 30) == "moins d'une minute"

    def test_minutes(self):
        now = int(time.time())
        assert _format_humanized_delta(now - 120) == "2 minutes"

    def test_hours(self):
        now = int(time.time())
        assert _format_humanized_delta(now - 7200) == "2 heures"

    def test_days(self):
        now = int(time.time())
        assert _format_humanized_delta(now - 2 * 86400) == "2 jours"

    def test_weeks(self):
        now = int(time.time())
        assert _format_humanized_delta(now - 14 * 86400) == "2 semaines"

    def test_months(self):
        now = int(time.time())
        assert _format_humanized_delta(now - 90 * 86400) == "3 mois"


class TestBuildTimestampBlock:
    def test_contains_now_and_delta(self):
        block = _build_timestamp_block("2026-06-02T12:00:00", "2026-06-01T10:00:00", "1 jour")
        assert "Date et heure actuelles" in block
        assert "2026-06-02T12:00:00" in block
        assert "1 jour" in block


class TestBuildMemoriesBlock:
    def test_empty(self):
        assert _build_memories_block([]) == ""

    def test_single_memory(self):
        memories = [
            {"content": "L'utilisateur aime le café.", "metadata": {"importance": 0.8, "timestamp_event": "2024-01-01"}}
        ]
        block = _build_memories_block(memories)
        assert "<relevant_memories>" in block
        assert "L'utilisateur aime le café." in block
        assert "importance:0.8" in block
        assert "</relevant_memories>" in block

    def test_multiline_content(self):
        memories = [
            {"content": "Line one\nLine two", "metadata": {"importance": 0.5, "timestamp_event": "N/A"}}
        ]
        block = _build_memories_block(memories)
        # Content should be flattened to single line
        assert "Line one Line two" in block


class TestBuildProfileBlock:
    def test_empty(self):
        assert _build_profile_block("") == ""

    def test_with_content(self):
        block = _build_profile_block("Utilisateur tech.")
        assert "<user_profile>" in block
        assert "Utilisateur tech." in block
        assert "</user_profile>" in block


class TestInjectDateMarkers:
    def test_no_messages(self):
        assert inject_date_markers([]) == []

    def test_single_day(self):
        ts = int(datetime(2024, 8, 15, 10, 0, 0).timestamp())
        msgs = [
            {"role": "user", "content": "Hello", "timestamp": ts},
            {"role": "assistant", "content": "Hi", "timestamp": ts + 60},
        ]
        result = inject_date_markers(msgs)
        # Only one day marker inserted before first message of that day
        markers = [m for m in result if m.get("role") == "system"]
        assert len(markers) == 1
        assert "15 août" in markers[0]["content"] or "15 August" in markers[0]["content"]

    def test_two_days(self):
        ts1 = int(datetime(2024, 8, 15, 22, 0, 0).timestamp())
        ts2 = int(datetime(2024, 8, 16, 9, 0, 0).timestamp())
        msgs = [
            {"role": "user", "content": "A", "timestamp": ts1},
            {"role": "assistant", "content": "B", "timestamp": ts1 + 60},
            {"role": "user", "content": "C", "timestamp": ts2},
        ]
        result = inject_date_markers(msgs)
        markers = [m for m in result if m.get("role") == "system"]
        assert len(markers) == 2
