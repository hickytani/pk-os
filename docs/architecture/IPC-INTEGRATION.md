# PK-OS Shell & Intelligence Integration Contract (Stage 5)

## 1. Overview

This document specifies the inter-process communication (IPC) protocol between the PK-OS Shell (`pk-shell`) and the PK Intelligence Daemon (`pk-intelligenced`).

Communication occurs via a local Unix domain socket (`/run/user/$UID/pk-os/ipc.sock`) using length-delimited JSON-RPC 2.0 messages.

## 2. Interface Definitions

### 2.1 Voice HUD State Synchronization

When the wake-word engine or a keyboard shortcut (`Super+Space`) activates the voice subsystem, `pk-intelligenced` emits state events to `pk-shell`:

```json
{
  "jsonrpc": "2.0",
  "method": "hud.state_changed",
  "params": {
    "state": "LISTENING",
    "transcript": "Launch terminal and monitor CPU",
    "confidence": 0.98
  }
}
```

### 2.2 Interactive Consequential Action Confirmation

When an intent requires consequential approval (e.g., deleting a file, modifying network configuration, system restart):

```json
{
  "jsonrpc": "2.0",
  "method": "hud.request_approval",
  "id": "req-98231",
  "params": {
    "tool_name": "filesystem.delete_path",
    "capability": "CONSEQUENTIAL",
    "description": "Delete temporary cache directory '/tmp/workspace_cache'?",
    "parameters": {
      "target_path": "/tmp/workspace_cache",
      "recursive": true
    },
    "timeout_seconds": 15
  }
}
```

The Shell displays the approval dialog and responds with the user's decision:

```json
{
  "jsonrpc": "2.0",
  "id": "req-98231",
  "result": {
    "approved": true,
    "user_identity": "root_or_session_owner"
  }
}
```

### 2.3 Application Discovery and Window Interaction

`pk-intelligenced` invokes shell services to query or focus running windows:

- `shell.list_applications()`: Returns installed desktop applications parsed from `/usr/share/applications/*.desktop`.
- `shell.launch_application(app_id)`: Dispatches execution via systemd transient scope (`systemd-run --user --scope`).
- `shell.focus_window(app_id)`: Sends compositor protocol request to bring window to focus.
- `shell.show_notification(title, message, priority)`: Renders desktop notification banner.
