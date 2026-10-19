"""
PK Intelligence Context Engine (Phase 2D)
==========================================
Provides persistent user preference storage, recent query history,
and context-aware suggestion generation for the PK Intelligence assistant.

Architecture:
  - UserPreferences: JSON-backed persistent key/value preference store.
  - QueryHistory: Timestamped circular buffer of recent queries.
  - ContextEngine: Combines preferences + history to produce contextual
    suggestions and augment the intent planner with user context.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pk.intelligence.context")

# Default preference values
DEFAULT_PREFERENCES: Dict[str, Any] = {
    "display.brightness": 80,
    "audio.volume": 50,
    "system.dark_mode": True,
    "voice.wake_word_enabled": True,
    "voice.wake_word": "Hey PK",
    "shell.workspace_count": 3,
    "intelligence.suggestion_limit": 5,
    "intelligence.history_size": 100,
}


SCHEMA_VERSION = 1


def atomic_write_json(path: Path, data: Any, mode: int = 0o600) -> None:
    """
    Safely persist JSON data via atomic temporary file rename.
    Ensures data integrity during unexpected process termination or power loss.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp_path, mode)
        except OSError:
            pass
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


@dataclass
class QueryRecord:
    """Single query history entry."""
    query: str
    intent: str = ""
    success: bool = False
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent,
            "success": self.success,
            "timestamp": self.timestamp,
            "context": self.context,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "QueryRecord":
        return QueryRecord(
            query=data.get("query", ""),
            intent=data.get("intent", ""),
            success=data.get("success", False),
            timestamp=data.get("timestamp", 0.0),
            context=data.get("context", {}),
        )


class UserPreferences:
    """
    JSON-backed persistent user preference store with atomic write
    guarantees, schema versioning, and corruption recovery.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = Path(path) if path else Path("/var/lib/pk-os/preferences.json")
        self._prefs: Dict[str, Any] = dict(DEFAULT_PREFERENCES)
        self._load()

    def _load(self) -> None:
        """Load preferences from disk with corruption recovery and schema support."""
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Support both versioned envelope and legacy flat dict
                if "schema_version" in data and "preferences" in data:
                    self._prefs.update(data["preferences"])
                else:
                    self._prefs.update(data)
            logger.debug("Loaded preferences from %s", self._path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupted preferences at %s: %s (backing up and resetting)", self._path, exc)
            self._backup_corrupted()

    def _backup_corrupted(self) -> None:
        try:
            bak_path = self._path.with_name(f"{self._path.name}.corrupt.{int(time.time())}")
            import shutil
            shutil.copy2(self._path, bak_path)
            logger.info("Backed up corrupted file to %s", bak_path)
        except Exception as exc:
            logger.warning("Could not backup corrupted file: %s", exc)

    def _save(self) -> None:
        """Persist current preferences atomically with schema envelope."""
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": time.time(),
            "preferences": self._prefs,
        }
        try:
            atomic_write_json(self._path, payload, mode=0o600)
        except OSError as exc:
            logger.warning("Could not save preferences: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._prefs.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._prefs[key] = value
        self._save()

    def reset(self, key: str) -> None:
        """Reset a key to its default value."""
        if key in DEFAULT_PREFERENCES:
            self._prefs[key] = DEFAULT_PREFERENCES[key]
            self._save()

    def reset_all(self) -> None:
        """Reset all preferences to defaults."""
        self._prefs = dict(DEFAULT_PREFERENCES)
        self._save()

    def all_preferences(self) -> Dict[str, Any]:
        return dict(self._prefs)

    @property
    def known_keys(self) -> List[str]:
        return list(DEFAULT_PREFERENCES.keys())


class QueryHistory:
    """
    Circular buffer of recent query records with atomic persistence
    and corruption recovery.
    """

    def __init__(self, max_size: int = 100, path: Optional[str] = None) -> None:
        self._max_size = max_size
        self._path = Path(path) if path else Path("/var/lib/pk-os/query_history.json")
        self._records: List[QueryRecord] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Support versioned envelope {"schema_version": 1, "records": [...]} or legacy [...]
            raw_records = data.get("records", []) if isinstance(data, dict) else data
            if isinstance(raw_records, list):
                self._records = [QueryRecord.from_dict(r) for r in raw_records]
            logger.debug("Loaded %d history records", len(self._records))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupted query history at %s: %s (backing up and resetting)", self._path, exc)
            try:
                bak_path = self._path.with_name(f"{self._path.name}.corrupt.{int(time.time())}")
                import shutil
                shutil.copy2(self._path, bak_path)
            except Exception:
                pass
            self._records = []

    def _save(self) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": time.time(),
            "count": len(self._records),
            "records": [r.to_dict() for r in self._records],
        }
        try:
            atomic_write_json(self._path, payload, mode=0o600)
        except OSError as exc:
            logger.warning("Could not save query history: %s", exc)

    def add(self, query: str, intent: str = "", success: bool = False,
            context: Optional[Dict[str, Any]] = None) -> QueryRecord:
        """Record a query."""
        rec = QueryRecord(
            query=query,
            intent=intent,
            success=success,
            context=context or {},
        )
        self._records.append(rec)
        if len(self._records) > self._max_size:
            self._records = self._records[-self._max_size:]
        self._save()
        return rec

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def recent(self) -> List[QueryRecord]:
        """Return last 10 queries, most recent first."""
        return list(reversed(self._records[-10:]))

    def search(self, keyword: str) -> List[QueryRecord]:
        """Search history for queries containing keyword."""
        kw = keyword.lower()
        return [r for r in self._records if kw in r.query.lower()]

    def get_frequent_intents(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return most frequently used intents."""
        intent_counts: Dict[str, int] = {}
        for r in self._records:
            if r.intent:
                intent_counts[r.intent] = intent_counts.get(r.intent, 0) + 1
        sorted_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"intent": k, "count": v} for k, v in sorted_intents[:limit]]

    def clear(self) -> None:
        self._records.clear()
        self._save()


class ContextEngine:
    """
    Combines user preferences and query history to produce
    context-aware suggestions for the PK Intelligence assistant.
    """

    def __init__(
        self,
        prefs_path: Optional[str] = None,
        history_path: Optional[str] = None,
        history_size: int = 100,
    ) -> None:
        self.preferences = UserPreferences(prefs_path)
        self.history = QueryHistory(max_size=history_size, path=history_path)

    def record_query(self, query: str, intent: str = "", success: bool = False,
                     context: Optional[Dict[str, Any]] = None) -> QueryRecord:
        """Record a query in history."""
        return self.history.add(query, intent, success, context)

    def get_suggestions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Generate context-aware suggestions based on:
        1. Frequently used intents
        2. Time-of-day patterns
        3. User preferences
        """
        suggestions: List[Dict[str, Any]] = []

        # 1. Suggest based on frequent intents
        frequent = self.history.get_frequent_intents(limit=3)
        for fi in frequent:
            intent = fi["intent"]
            suggestions.append({
                "type": "frequent",
                "label": f"Run '{intent}' (used {fi['count']}x)",
                "intent": intent,
                "confidence": min(0.9, 0.5 + fi["count"] * 0.05),
            })

        # 2. Time-based suggestions
        hour = time.localtime().tm_hour
        if hour >= 22 or hour < 6:
            suggestions.append({
                "type": "time_based",
                "label": "Lower brightness for night use",
                "intent": "adjust_setting",
                "params": {"key": "display.brightness", "value": 30},
                "confidence": 0.6,
            })
        elif hour >= 6 and hour < 9:
            suggestions.append({
                "type": "time_based",
                "label": "Good morning! Check system status",
                "intent": "get_system_status",
                "params": {"resource": "all"},
                "confidence": 0.5,
            })

        # 3. Preference-based suggestions
        if self.preferences.get("voice.wake_word_enabled"):
            suggestions.append({
                "type": "preference",
                "label": f"Voice ready: say '{self.preferences.get('voice.wake_word')}'",
                "intent": "voice_status",
                "confidence": 0.4,
            })

        # Sort by confidence descending
        suggestions.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        return suggestions[:limit]

    def get_context_summary(self) -> Dict[str, Any]:
        """Return a summary for augmenting intent planner queries."""
        return {
            "recent_queries": [r.query for r in self.history.recent[:5]],
            "frequent_intents": self.history.get_frequent_intents(limit=3),
            "preferences": {
                "dark_mode": self.preferences.get("system.dark_mode"),
                "brightness": self.preferences.get("display.brightness"),
                "volume": self.preferences.get("audio.volume"),
                "wake_word": self.preferences.get("voice.wake_word_enabled"),
            },
            "history_count": self.history.count,
        }
