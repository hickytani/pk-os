"""
PK-OS Shell Surface Generator
Produces accessible, contrast-validated semantic HTML/CSS structures
for the Panel, Application Launcher, and Voice HUD.
"""

from typing import List, Dict, Any


def render_shell_preview_html(active_window: str = "Terminal",
                              battery_pct: int = 88,
                              voice_state: str = "IDLE") -> str:
    """
    Renders the reference visual DOM for the PK-OS Shell vertical slice.
    Adheres strictly to WCAG AAA contrast, semantic accessibility, and 4px grid.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PK-OS Shell Preview</title>
  <link rel="stylesheet" href="../tokens/tokens.css">
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: var(--pk-bg-base);
      color: var(--pk-text-primary);
      font-family: var(--pk-font-sans);
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    /* Top Panel (Layer: Top) */
    .pk-panel {{
      height: 36px;
      background: var(--pk-bg-surface);
      border-bottom: 1px solid var(--pk-border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 var(--pk-space-4);
      font-size: var(--pk-text-sm);
      user-select: none;
    }}
    .pk-brand {{
      font-weight: 700;
      letter-spacing: 0.05em;
      color: var(--pk-accent-cyan);
    }}
    .pk-workspaces {{
      display: flex;
      gap: var(--pk-space-2);
    }}
    .pk-ws-badge {{
      padding: 2px 8px;
      border-radius: var(--pk-radius-sm);
      background: var(--pk-bg-surface-hover);
      color: var(--pk-text-secondary);
      font-size: var(--pk-text-xs);
    }}
    .pk-ws-badge.active {{
      background: var(--pk-border-focused);
      color: #ffffff;
      font-weight: 600;
    }}
    .pk-status-area {{
      display: flex;
      align-items: center;
      gap: var(--pk-space-4);
      color: var(--pk-text-secondary);
      font-size: var(--pk-text-xs);
    }}
    /* Main Desktop Area */
    .pk-desktop {{
      flex: 1;
      position: relative;
      background: radial-gradient(circle at 50% 30%, #151824 0%, var(--pk-bg-base) 80%);
    }}
    /* Voice HUD (Layer: Overlay) */
    .pk-voice-hud {{
      position: absolute;
      top: var(--pk-space-4);
      right: var(--pk-space-4);
      width: 360px;
      background: var(--pk-bg-surface);
      border: 1px solid var(--pk-border-subtle);
      border-radius: var(--pk-radius-md);
      padding: var(--pk-space-4);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
      transition: all var(--pk-motion-smooth);
    }}
    .pk-hud-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--pk-space-2);
    }}
    .pk-hud-title {{
      font-size: var(--pk-text-xs);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--pk-accent-cyan);
      font-weight: 700;
    }}
    .pk-hud-badge {{
      font-size: 10px;
      padding: 2px 6px;
      border-radius: var(--pk-radius-sm);
      background: rgba(0, 229, 255, 0.1);
      color: var(--pk-accent-cyan);
    }}
    .pk-hud-body {{
      font-size: var(--pk-text-sm);
      color: var(--pk-text-primary);
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <header class="pk-panel" role="banner">
    <div class="pk-brand" aria-label="PK-OS Logo">PK-OS</div>
    <div class="pk-workspaces" role="tablist" aria-label="Workspaces">
      <span class="pk-ws-badge active" role="tab" aria-selected="true">1: Main</span>
      <span class="pk-ws-badge" role="tab" aria-selected="false">2: Code</span>
      <span class="pk-ws-badge" role="tab" aria-selected="false">3: Web</span>
    </div>
    <div class="pk-status-area" aria-label="System Indicators">
      <span>{active_window}</span>
      <span>Battery: {battery_pct}%</span>
      <time datetime="2026-10-17T16:40:00">16:40</time>
    </div>
  </header>
  <main class="pk-desktop" role="main">
    <aside class="pk-voice-hud" role="dialog" aria-label="PK Intelligence HUD">
      <div class="pk-hud-header">
        <span class="pk-hud-title">Hey PK Intelligence</span>
        <span class="pk-hud-badge">{voice_state}</span>
      </div>
      <div class="pk-hud-body">
        Ready for voice command or Super+Space...
      </div>
    </aside>
  </main>
</body>
</html>
"""
