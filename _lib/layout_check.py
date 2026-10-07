#!/usr/bin/env python3
"""Headless layout check for built report pages (brief, walkthrough).

Opens a page in headless Chrome at several widths, reads the element boxes that
layout_probe.js collects, and fails on layout defects: sideways scroll, panel header
children that stop short of the header edge, header padding, header overflow, and files
panel columns that do not line up. Needs a local Chrome and an unsandboxed shell.

    python3 _lib/layout_check.py PAGE.html [PAGE.html ...] [--widths 1280,900,720,390]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE_JS = HERE / "layout_probe.js"
DEFAULT_WIDTHS = (1280, 900, 720, 390)
TOLERANCE = 1.0
PROBE_RE = re.compile(r'<script[^>]*\bid="layout-probe"[^>]*>(.*?)</script>', re.S)
PLAYWRIGHT_GLOB = ("~/Library/Caches/ms-playwright/chromium_headless_shell-*/"
                   "chrome-headless-shell-*/chrome-headless-shell")
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class BrowserError(RuntimeError):
    """The browser could not start, or it did not return the probe data."""


def find_browser() -> str | None:
    env = os.environ.get("LAYOUT_CHROME")
    if env:
        return env
    found = glob.glob(os.path.expanduser(PLAYWRIGHT_GLOB))
    if found:
        return max(found, key=_build_number)
    for name in ("chrome-headless-shell", "chromium", "google-chrome"):
        path = shutil.which(name)
        if path:
            return path
    return MAC_CHROME if os.path.exists(MAC_CHROME) else None


def _build_number(path: str) -> tuple[int, ...]:
    m = re.search(r"chromium_headless_shell-(\d+)", path)
    return (int(m.group(1)),) if m else (0,)


def inline_probe(page: str, script: str) -> str:
    i = page.rfind("</body>")
    tag = f"<script>{script}</script>"
    return page + tag if i < 0 else page[:i] + tag + page[i:]


def parse_probe(dom: str) -> dict:
    m = PROBE_RE.search(dom)
    if not m:
        raise BrowserError("the page returned no layout-probe data")
    try:
        return json.loads(m.group(1))
    except ValueError as e:
        raise BrowserError(f"layout-probe data is not valid JSON: {e}") from e


def probe(html_path: str | Path, width: int, browser: str) -> dict:
    try:
        page = Path(html_path).read_text(encoding="utf-8")
    except OSError as e:
        raise BrowserError(f"cannot read {html_path}: {e}") from e
    script = PROBE_JS.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(dir=tempfile.gettempdir()) as tmp:
        copy = Path(tmp) / "page.html"
        copy.write_text(inline_probe(page, script), encoding="utf-8")
        cmd = [browser, "--headless", "--disable-gpu", "--hide-scrollbars",
               f"--window-size={width},900", "--virtual-time-budget=3000",
               "--dump-dom", copy.as_uri()]
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BrowserError(f"could not run {browser}: {e}") from e
    if run.returncode != 0:
        raise BrowserError(f"{browser} exited {run.returncode}: {run.stderr.strip()[-400:]}")
    return parse_probe(run.stdout)


def _spread(values: list[float]) -> float:
    return max(values) - min(values) if values else 0.0


def check(boxes: dict, width: int) -> list[str]:
    fails: list[str] = []
    vp = boxes["viewport"]
    if vp["scrollWidth"] > vp["innerWidth"]:
        fails.append(f"{width}px: page scrolls sideways (scrollWidth {vp['scrollWidth']} > "
                     f"innerWidth {vp['innerWidth']})")
    for h in boxes["headers"]:
        top = h["top"] + h["borderTop"]
        bottom = h["bottom"] - h["borderBottom"]
        for c in h["children"]:
            for edge, got, want in (("top", c["top"], top), ("bottom", c["bottom"], bottom)):
                if abs(got - want) > TOLERANCE:
                    fails.append(f"{width}px: {h['id']} h2 .{c['name']} {edge} is {got:.1f}, "
                                 f"header inner {edge} is {want:.1f}")
        for side in ("Top", "Bottom"):
            if h[f"padding{side}"] != 0:
                fails.append(f"{width}px: {h['id']} h2 has padding-{side.lower()} "
                             f"{h[f'padding{side}']}px, expected 0")
        if h["scrollWidth"] > h["clientWidth"] + TOLERANCE:
            fails.append(f"{width}px: {h['id']} h2 content is wider than the header "
                         f"({h['scrollWidth']} > {h['clientWidth']})")
    for f in boxes["files"]:
        for key, label in (("bar", "bar left"), ("add", "+N right"), ("del", "−N right")):
            vals = [r[key] for r in f["rows"] if r.get(key) is not None]
            if _spread(vals) > TOLERANCE:
                fails.append(f"{width}px: {f['id']} files {label} edges differ by "
                             f"{_spread(vals):.1f}px across rows")
    return fails


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Headless layout check for built report pages.")
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--widths", default=",".join(map(str, DEFAULT_WIDTHS)))
    args = ap.parse_args(argv)
    try:
        widths = [int(w) for w in args.widths.split(",") if w.strip()]
    except ValueError:
        ap.error("--widths must be comma-separated integers")
    browser = find_browser()
    if not browser:
        print("layout_check: no Chrome found. Set LAYOUT_CHROME or install Chrome or a "
              "Playwright headless shell.", file=sys.stderr)
        return 2
    fails: list[str] = []
    try:
        for page in args.pages:
            for w in widths:
                fails += [f"{page}: {line}" for line in check(probe(page, w, browser), w)]
    except BrowserError as e:
        print(f"layout_check: {e}\nA sandboxed shell can block Chrome; run this unsandboxed.",
              file=sys.stderr)
        return 2
    if fails:
        print("\n".join(fails))
        return 1
    print(f"layout ok: {len(args.pages)} page(s) × {len(widths)} widths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
