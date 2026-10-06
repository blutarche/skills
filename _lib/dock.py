"""The floating dock shared by the brief and the walkthrough: markup, styles, and script.

The dock holds Send feedback, a toast, the blocked-clipboard popover, and (when the page has a sheet)
Back to sheet. Its script is spliced into the page script after notes.js, so it works without
sheet.css or sheet.js.

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

from pathlib import Path

import pagelib

HERE = Path(__file__).resolve().parent


def render_dock(project: str, branch: str | None, back_to_sheet: bool) -> str:
    """The fixed bottom-right dock. `project` and `branch` ride on data attributes for the script."""
    back = '<button type="button" class="tosheet" hidden>↑ Back to sheet</button>' if back_to_sheet else ""
    attrs = f' data-project="{pagelib.esc(project)}"' + (f' data-branch="{pagelib.esc(branch)}"' if branch else "")
    return (
        f'<div class="dock"{attrs}>'
        '<div class="dock-pop" hidden><pre data-export-preview></pre>'
        '<button type="button" class="btn" data-pop-close>Close</button></div>'
        '<div class="dock-toast" role="status" aria-live="polite" data-export-status hidden></div>'
        f'<div class="dock-row">{back}'
        '<button type="button" class="send" data-export title="Notes stay in this browser until you send them.">'
        'Send feedback</button></div></div>'
    )


def assets() -> tuple[str, str]:
    return (HERE / "dock.css").read_text(encoding="utf-8"), (HERE / "dock.js").read_text(encoding="utf-8")
