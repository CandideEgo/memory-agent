"""Tests for MemoryStore — three-layer memory and session persistence."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from memory_store import MemoryStore


@pytest.fixture
def store():
    """Create a fresh MemoryStore for each test."""
    return MemoryStore()


class TestMemoryStoreBasic:
    """Tests for basic add/retrieve operations."""

    def test_add_and_retrieve(self, store):
        store.add("user", "hello")
        store.add("assistant", "hi there")
        assert len(store.working) == 2
        assert store.working[0]["role"] == "user"
        assert store.working[0]["content"] == "hello"
        assert store.working[1]["role"] == "assistant"

    def test_estimate_tokens_zero_initially(self, store):
        assert store.estimate_tokens() == 0

    def test_estimate_tokens_after_add(self, store):
        store.add("user", "hello world")
        # ~11 chars / 3
        assert store.estimate_tokens() > 0


class TestMemoryStoreCompaction:
    """Tests for compaction threshold."""

    def test_should_compact_below_threshold(self, store):
        store.add("user", "short message")
        assert not store.should_compact()

    def test_should_compact_above_threshold(self, store):
        # Set a low threshold and add enough content to trigger
        store.compaction_threshold = 10
        store.add("user", "a" * 100)
        assert store.should_compact()


class TestMemoryStorePersistence:
    """Tests for session save/load round-trip."""

    def test_save_and_load_roundtrip(self, store, tmp_path):
        import os
        # Override sessions dir to use tmp_path
        original_dir = Path(sys.modules["memory_store"]._SESSIONS_DIR)
        try:
            sessions_dir = tmp_path / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            import memory_store
            memory_store._SESSIONS_DIR = sessions_dir

            store.add("user", "test message")
            store.add("assistant", "test response")

            sid = "test-session-001"
            saved_path = store.save_session(sid)
            assert saved_path.exists()

            data = json.loads(saved_path.read_text(encoding="utf-8"))
            assert data["session_id"] == sid
            assert len(data["messages"]) == 2

            # Load into a fresh store
            store2 = MemoryStore()
            count = store2.load_session(sid)
            assert count == 2
            assert store2.working[0]["content"] == "test message"
        finally:
            memory_store._SESSIONS_DIR = original_dir

    def test_load_nonexistent_session(self, store):
        count = store.load_session("nonexistent-id")
        assert count == 0


class TestMemoryStoreFormat:
    """Tests for message format conversion."""

    def test_to_anthropic_messages_format(self, store):
        store.add("user", "hello")
        store.add("assistant", "hi")
        msgs = store.to_anthropic_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "hi"
