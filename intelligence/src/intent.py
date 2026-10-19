"""
PK Intelligence Intent Planner
Maps transcribed natural language queries into strictly typed JSON task requests.
Protects against adversarial prompt injections and arbitrary shell execution.
"""

from typing import Dict, Any, Optional
import re
import json


class IntentPlanner:
    # Adversarial patterns that attempt to escape tool boundaries or invoke shell
    INJECTION_PATTERNS = [
        r"ignore.*previous.*instructions",
        r"run.*bash.*script",
        r"rm\s+-rf",
        r"sudo\s+rm",
        r"curl.*\|.*sh",
        r"wget.*\|.*sh",
        r"/bin/(sh|bash)",
        r"powershell",
        r"eval\("
    ]

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parses query into structured task.
        Returns:
          {
            "status": "VALID" | "AMBIGUOUS" | "REJECTED_SECURITY",
            "tool_name": str | None,
            "parameters": dict | None,
            "explanation": str
          }
        """
        cleaned = query.strip()

        # Check for adversarial prompt injection
        for pat in self.INJECTION_PATTERNS:
            if re.search(pat, cleaned, re.IGNORECASE):
                return {
                    "status": "REJECTED_SECURITY",
                    "tool_name": None,
                    "parameters": None,
                    "explanation": f"Security violation: Query contains forbidden pattern matching '{pat}'"
                }

        lower = cleaned.lower()

        # Intent 1: Launch Application
        if "launch" in lower or "open" in lower:
            for app_id in ["terminal", "browser", "settings", "files", "editor"]:
                if app_id in lower:
                    return {
                        "status": "VALID",
                        "tool_name": "launch_application",
                        "parameters": {"app_id": app_id},
                        "explanation": f"Launching application: {app_id}"
                    }

        # Intent 2: System Status
        if any(term in lower for term in ["status", "memory", "ram", "battery", "disk", "uptime"]):
            res = "all"
            if "memory" in lower or "ram" in lower:
                res = "memory"
            elif "disk" in lower:
                res = "disk"
            elif "battery" in lower:
                res = "battery"
            elif "uptime" in lower:
                res = "uptime"

            return {
                "status": "VALID",
                "tool_name": "get_system_status",
                "parameters": {"resource": res},
                "explanation": f"Querying system metric: {res}"
            }

        # Intent 3: Adjust Settings
        if "brightness" in lower or "volume" in lower or "dark mode" in lower:
            if "brightness" in lower:
                match = re.search(r"(\d+)", lower)
                val = int(match.group(1)) if match else 50
                return {
                    "status": "VALID",
                    "tool_name": "adjust_setting",
                    "parameters": {"key": "display.brightness", "value": val},
                    "explanation": f"Setting brightness to {val}%"
                }
            elif "volume" in lower:
                match = re.search(r"(\d+)", lower)
                val = int(match.group(1)) if match else 50
                return {
                    "status": "VALID",
                    "tool_name": "adjust_setting",
                    "parameters": {"key": "audio.volume", "value": val},
                    "explanation": f"Setting volume to {val}%"
                }

        # Intent 4: Delete Path (Consequential)
        if "delete" in lower or "remove file" in lower:
            match = re.search(r"(?:delete|remove)\s+(?:file\s+)?([/\w\.-]+)", cleaned, re.IGNORECASE)
            if match:
                path = match.group(1)
                return {
                    "status": "VALID",
                    "tool_name": "delete_path",
                    "parameters": {"target_path": path},
                    "explanation": f"Requesting deletion of: {path}"
                }

        # Intent 5: List Directory
        if any(term in lower for term in ["list", "show files", "browse", "what's in", "ls ", "directory"]):
            path_match = re.search(r"(?:list|show files|browse|ls|directory)\s+(?:in\s+|of\s+)?([/\w\.-]+)", cleaned, re.IGNORECASE)
            path = path_match.group(1) if path_match else "/home/pkos"
            show_hidden = "hidden" in lower or "all" in lower
            return {
                "status": "VALID",
                "tool_name": "list_directory",
                "parameters": {"path": path, "show_hidden": show_hidden},
                "explanation": f"Listing directory: {path}"
            }

        # Ambiguous query fallback
        return {
            "status": "AMBIGUOUS",
            "tool_name": None,
            "parameters": None,
            "explanation": f"Unable to unambiguously map query to an allowlisted tool: '{query}'"
        }
