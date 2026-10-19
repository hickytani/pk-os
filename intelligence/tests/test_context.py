"""
Tests for PK Intelligence Context Engine (Phase 2D)
"""

import json
import os
import tempfile
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from intelligence.src.context import (
    QueryRecord,
    UserPreferences,
    QueryHistory,
    ContextEngine,
    DEFAULT_PREFERENCES,
)


class TestQueryRecord:
    """Tests for the QueryRecord data class."""

    def test_creation(self):
        r = QueryRecord(query="check status", intent="get_system_status", success=True)
        assert r.query == "check status"
        assert r.intent == "get_system_status"
        assert r.success is True
        assert r.timestamp > 0

    def test_serialization_roundtrip(self):
        r = QueryRecord(query="launch terminal", intent="launch_application", success=True)
        d = r.to_dict()
        r2 = QueryRecord.from_dict(d)
        assert r2.query == r.query
        assert r2.intent == r.intent
        assert r2.success == r.success


class TestUserPreferences:
    """Tests for the UserPreferences store."""

    def test_defaults_loaded(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            prefs = UserPreferences(path=path)
            assert prefs.get("display.brightness") == 80
            assert prefs.get("system.dark_mode") is True
        finally:
            os.unlink(path)

    def test_set_and_get(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            prefs = UserPreferences(path=path)
            prefs.set("display.brightness", 50)
            assert prefs.get("display.brightness") == 50
        finally:
            os.unlink(path)

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            prefs = UserPreferences(path=path)
            prefs.set("audio.volume", 75)
            # Load from same file
            prefs2 = UserPreferences(path=path)
            assert prefs2.get("audio.volume") == 75
        finally:
            os.unlink(path)

    def test_reset_key(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            prefs = UserPreferences(path=path)
            prefs.set("display.brightness", 10)
            prefs.reset("display.brightness")
            assert prefs.get("display.brightness") == DEFAULT_PREFERENCES["display.brightness"]
        finally:
            os.unlink(path)

    def test_reset_all(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            prefs = UserPreferences(path=path)
            prefs.set("display.brightness", 10)
            prefs.set("audio.volume", 10)
            prefs.reset_all()
            assert prefs.all_preferences() == DEFAULT_PREFERENCES
        finally:
            os.unlink(path)

    def test_known_keys(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            prefs = UserPreferences(path=path)
            assert "display.brightness" in prefs.known_keys
            assert "audio.volume" in prefs.known_keys
        finally:
            os.unlink(path)


class TestQueryHistory:
    """Tests for the QueryHistory circular buffer."""

    def test_add_and_count(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=10, path=path)
            history.add("test query", intent="test", success=True)
            assert history.count == 1
        finally:
            os.unlink(path)

    def test_circular_buffer(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=5, path=path)
            for i in range(10):
                history.add(f"query {i}")
            assert history.count == 5
            # Should have kept the most recent 5
            recent = history.recent
            assert recent[0].query == "query 9"
        finally:
            os.unlink(path)

    def test_recent_order(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=100, path=path)
            history.add("first")
            history.add("second")
            history.add("third")
            recent = history.recent
            assert recent[0].query == "third"
            assert recent[2].query == "first"
        finally:
            os.unlink(path)

    def test_search(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=100, path=path)
            history.add("launch terminal")
            history.add("check system status")
            history.add("launch browser")
            results = history.search("launch")
            assert len(results) == 2
        finally:
            os.unlink(path)

    def test_frequent_intents(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=100, path=path)
            for _ in range(5):
                history.add("launch terminal", intent="launch_application")
            for _ in range(3):
                history.add("check status", intent="get_system_status")
            freq = history.get_frequent_intents(limit=2)
            assert len(freq) == 2
            assert freq[0]["intent"] == "launch_application"
            assert freq[0]["count"] == 5
        finally:
            os.unlink(path)

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=100, path=path)
            history.add("saved query", intent="test", success=True)
            history2 = QueryHistory(max_size=100, path=path)
            assert history2.count == 1
            assert history2.recent[0].query == "saved query"
        finally:
            os.unlink(path)

    def test_clear(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            history = QueryHistory(max_size=100, path=path)
            history.add("test")
            history.clear()
            assert history.count == 0
        finally:
            os.unlink(path)


class TestContextEngine:
    """Tests for the ContextEngine."""

    def test_record_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ContextEngine(
                prefs_path=os.path.join(tmpdir, "prefs.json"),
                history_path=os.path.join(tmpdir, "history.json"),
            )
            rec = engine.record_query("test query", intent="test", success=True)
            assert rec.query == "test query"
            assert engine.history.count == 1

    def test_get_suggestions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ContextEngine(
                prefs_path=os.path.join(tmpdir, "prefs.json"),
                history_path=os.path.join(tmpdir, "history.json"),
            )
            for _ in range(5):
                engine.record_query("launch terminal", intent="launch_application", success=True)
            suggestions = engine.get_suggestions(limit=5)
            assert len(suggestions) > 0
            # Should include frequent intent suggestion
            assert any(s["type"] == "frequent" for s in suggestions)

    def test_context_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ContextEngine(
                prefs_path=os.path.join(tmpdir, "prefs.json"),
                history_path=os.path.join(tmpdir, "history.json"),
            )
            engine.record_query("test query")
            summary = engine.get_context_summary()
            assert "recent_queries" in summary
            assert "preferences" in summary
            assert summary["history_count"] == 1

    def test_preferences_integration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = ContextEngine(
                prefs_path=os.path.join(tmpdir, "prefs.json"),
                history_path=os.path.join(tmpdir, "history.json"),
            )
            engine.preferences.set("display.brightness", 30)
            assert engine.preferences.get("display.brightness") == 30
            summary = engine.get_context_summary()
            assert summary["preferences"]["brightness"] == 30
