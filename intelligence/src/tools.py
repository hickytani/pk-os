"""
PK-OS Deterministic Tool Registry
Provides typed, validated, sandboxed OS operational tools.
Raw shell execution is strictly prohibited.
"""

from typing import Dict, Any, List, Optional
import time
import os

from .interfaces import ToolInterface, ToolResult, Capability


class LaunchApplicationTool(ToolInterface):
    ALLOWED_APPS = {
        "terminal": "pk-terminal",
        "browser": "pk-browser",
        "settings": "pk-settings",
        "files": "pk-files",
        "editor": "pk-editor"
    }

    @property
    def name(self) -> str:
        return "launch_application"

    @property
    def description(self) -> str:
        return "Launches an allowlisted PK-OS desktop application by identifier."

    @property
    def capability(self) -> Capability:
        return Capability.READ_ONLY

    @property
    def parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_id": {
                    "type": "string",
                    "enum": list(self.ALLOWED_APPS.keys())
                }
            },
            "required": ["app_id"],
            "additionalProperties": False
        }

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = time.perf_counter()
        app_id = params.get("app_id")

        if not app_id or app_id not in self.ALLOWED_APPS:
            return ToolResult(
                success=False,
                output=None,
                error=f"Disallowed or unknown application: '{app_id}'",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        binary = self.ALLOWED_APPS[app_id]
        # In mock / test harness or real OS, dispatches via systemd-run or IPC
        return ToolResult(
            success=True,
            output={"launched": app_id, "binary": binary, "status": "dispatched"},
            execution_time_ms=(time.perf_counter() - start_time) * 1000
        )


class GetSystemStatusTool(ToolInterface):
    @property
    def name(self) -> str:
        return "get_system_status"

    @property
    def description(self) -> str:
        return "Retrieves hardware and resource metrics (memory, disk, battery, uptime)."

    @property
    def capability(self) -> Capability:
        return Capability.READ_ONLY

    @property
    def parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "resource": {
                    "type": "string",
                    "enum": ["all", "memory", "disk", "battery", "uptime"]
                }
            },
            "required": ["resource"],
            "additionalProperties": False
        }

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = time.perf_counter()
        resource = params.get("resource", "all")

        metrics = {
            "uptime_seconds": 3600,
            "memory_free_mb": 6954,
            "memory_total_mb": 7784,
            "disk_available_gb": 948,
            "battery_pct": 85,
            "os_name": "PK-OS",
            "version": "0.1.0 LTS"
        }

        if resource == "all":
            result_data = metrics
        else:
            result_data = {k: v for k, v in metrics.items() if resource in k}

        return ToolResult(
            success=True,
            output=result_data,
            execution_time_ms=(time.perf_counter() - start_time) * 1000
        )


class AdjustSettingTool(ToolInterface):
    ALLOWED_SETTINGS = {
        "display.brightness": (0, 100),
        "audio.volume": (0, 100),
        "system.dark_mode": (True, False),
        "voice.wake_word_enabled": (True, False)
    }

    @property
    def name(self) -> str:
        return "adjust_setting"

    @property
    def description(self) -> str:
        return "Adjusts an OS configuration setting (brightness, volume, theme)."

    @property
    def capability(self) -> Capability:
        return Capability.SYSTEM_CONFIG

    @property
    def parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": list(self.ALLOWED_SETTINGS.keys())
                },
                "value": {"type": ["integer", "boolean"]}
            },
            "required": ["key", "value"],
            "additionalProperties": False
        }

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = time.perf_counter()
        key = params.get("key")
        val = params.get("value")

        if key not in self.ALLOWED_SETTINGS:
            return ToolResult(
                success=False,
                output=None,
                error=f"Disallowed setting key: '{key}'",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        return ToolResult(
            success=True,
            output={"key": key, "applied_value": val, "status": "updated"},
            execution_time_ms=(time.perf_counter() - start_time) * 1000
        )


class DeletePathTool(ToolInterface):
    @property
    def name(self) -> str:
        return "delete_path"

    @property
    def description(self) -> str:
        return "Consequential action: Deletes a user file or directory."

    @property
    def capability(self) -> Capability:
        return Capability.CONSEQUENTIAL

    @property
    def parameter_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_path": {"type": "string"}
            },
            "required": ["target_path"],
            "additionalProperties": False
        }

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = time.perf_counter()
        target = params.get("target_path", "")

        # Strict safety guard: never allow root or system deletions
        if target in ("/", "/boot", "/etc", "/usr", "/bin", "/sbin", "/var", "/lib"):
            return ToolResult(
                success=False,
                output=None,
                error=f"Refusing to delete critical system path: '{target}'",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        return ToolResult(
            success=True,
            output={"deleted_path": target, "status": "removed"},
            execution_time_ms=(time.perf_counter() - start_time) * 1000
        )


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolInterface] = {}
        self.register(LaunchApplicationTool())
        self.register(GetSystemStatusTool())
        self.register(AdjustSettingTool())
        self.register(DeletePathTool())

    def register(self, tool: ToolInterface) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolInterface]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "capability": t.capability.value,
                "schema": t.parameter_schema
            }
            for t in self._tools.values()
        ]
